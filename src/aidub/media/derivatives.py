"""Bounded FFmpeg execution and atomic publication of derived media."""

from __future__ import annotations

import contextlib
import hashlib
import os
import queue
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO, Literal, Protocol, cast
from uuid import uuid4

from .commands import (
    DerivativeKind,
    DerivativeSpec,
    FFmpegCommandPlan,
    build_ffmpeg_command,
    derivative_cache_key,
)
from .probe import ContainerInfo, MediaProbeError


class DerivativeError(RuntimeError):
    """Base class for media derivative failures."""


class DerivativeOutputExistsError(DerivativeError):
    """Raised when publication would replace any existing filesystem entry."""


class DerivativeCancelledError(DerivativeError):
    """Raised after a cancelled process has been stopped and staged bytes removed."""


class DerivativeTimeoutError(DerivativeError):
    """Raised after an over-time process has been stopped and staged bytes removed."""


class DerivativeProcessError(DerivativeError):
    """Raised when FFmpeg fails or violates an execution/output boundary."""


class CancellationSignal(Protocol):
    """Small protocol implemented by ``threading.Event`` and worker tokens."""

    def is_set(self) -> bool: ...


class ProgressCallback(Protocol):
    def __call__(self, update: FFmpegProgress) -> None: ...


@dataclass(frozen=True, slots=True)
class FFmpegProgress:
    """One record emitted by FFmpeg's machine-readable progress protocol."""

    state: str
    frame: int | None = None
    fps: Decimal | None = None
    out_time_microseconds: int | None = None
    speed: Decimal | None = None
    raw_fields: tuple[tuple[str, str], ...] = ()


class FFmpegProgressParser:
    """Incremental parser for ``-progress pipe:1`` key/value records."""

    def __init__(self, *, maximum_fields: int = 128) -> None:
        if maximum_fields < 1:
            raise ValueError("maximum_fields must be positive")
        self._maximum_fields = maximum_fields
        self._fields: dict[str, str] = {}

    def feed_line(self, line: str) -> FFmpegProgress | None:
        """Consume one decoded line and return a completed progress record."""

        normalized = line.rstrip("\r\n")
        if not normalized or "=" not in normalized:
            return None
        key, value = normalized.split("=", 1)
        if not key or len(key) > 64 or len(value) > 8_192:
            raise DerivativeProcessError("FFmpeg emitted an invalid progress record")
        if key not in self._fields and len(self._fields) >= self._maximum_fields:
            raise DerivativeProcessError("FFmpeg progress record exceeded the field limit")
        self._fields[key] = value
        if key != "progress":
            return None
        fields = self._fields
        self._fields = {}
        return FFmpegProgress(
            state=value,
            frame=_optional_int(fields.get("frame")),
            fps=_optional_decimal(fields.get("fps")),
            out_time_microseconds=_optional_int(
                fields.get("out_time_us", fields.get("out_time_ms"))
            ),
            speed=_speed_decimal(fields.get("speed")),
            raw_fields=tuple(sorted(fields.items())),
        )


@dataclass(frozen=True, slots=True)
class CommandResult:
    return_code: int
    stderr_tail: str


class CommandRunner(Protocol):
    """Injectable execution seam used by production and deterministic tests."""

    def run(
        self,
        plan: FFmpegCommandPlan,
        *,
        cancellation: CancellationSignal,
        timeout_seconds: float,
        on_progress: ProgressCallback | None = None,
    ) -> CommandResult: ...


class MediaProbeLike(Protocol):
    """Subset of the probe adapter required for post-generation validation."""

    def probe(self, source: Path | str) -> ContainerInfo: ...


_StreamName = Literal["stdout", "stderr"]
_StreamMessage = tuple[_StreamName, bytes | None]


class SubprocessCommandRunner:
    """Run an FFmpeg plan with bounded pipes and responsive cancellation."""

    def __init__(
        self,
        *,
        maximum_pipe_bytes: int = 1_048_576,
        maximum_stderr_tail_bytes: int = 65_536,
        terminate_grace_seconds: float = 2.0,
    ) -> None:
        if maximum_pipe_bytes < 8_192:
            raise ValueError("maximum_pipe_bytes is too small")
        if maximum_stderr_tail_bytes < 1_024:
            raise ValueError("maximum_stderr_tail_bytes is too small")
        if terminate_grace_seconds <= 0:
            raise ValueError("terminate_grace_seconds must be positive")
        self.maximum_pipe_bytes = maximum_pipe_bytes
        self.maximum_stderr_tail_bytes = maximum_stderr_tail_bytes
        self.terminate_grace_seconds = terminate_grace_seconds

    def run(
        self,
        plan: FFmpegCommandPlan,
        *,
        cancellation: CancellationSignal,
        timeout_seconds: float,
        on_progress: ProgressCallback | None = None,
    ) -> CommandResult:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        try:
            # The executable is an absolute, validated path and argv is a tuple.
            # No command interpreter is involved.
            process = subprocess.Popen(
                plan.argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise DerivativeProcessError(f"could not start FFmpeg: {exc}") from exc

        assert process.stdout is not None
        assert process.stderr is not None
        messages: queue.Queue[_StreamMessage] = queue.Queue(maxsize=512)
        overflowed = threading.Event()
        stdout_thread = _start_pipe_reader(
            "stdout",
            process.stdout,
            messages,
            overflowed,
            self.maximum_pipe_bytes,
        )
        stderr_thread = _start_pipe_reader(
            "stderr",
            process.stderr,
            messages,
            overflowed,
            self.maximum_pipe_bytes,
        )
        deadline = time.monotonic() + timeout_seconds
        parser = FFmpegProgressParser()
        stdout_buffer = bytearray()
        stderr_tail: deque[bytes] = deque()
        stderr_size = 0
        eof_streams: set[_StreamName] = set()
        failure: DerivativeError | None = None

        try:
            while process.poll() is None or len(eof_streams) < 2 or not messages.empty():
                if cancellation.is_set():
                    failure = DerivativeCancelledError("media derivative was cancelled")
                    break
                if time.monotonic() >= deadline:
                    failure = DerivativeTimeoutError(
                        f"media derivative exceeded {timeout_seconds:g} seconds"
                    )
                    break
                if overflowed.is_set():
                    failure = DerivativeProcessError("FFmpeg pipe output exceeded the safe limit")
                    break
                try:
                    stream_name, chunk = messages.get(timeout=0.05)
                except queue.Empty:
                    continue
                if chunk is None:
                    eof_streams.add(stream_name)
                elif stream_name == "stdout":
                    stdout_buffer.extend(chunk)
                    _emit_complete_progress_lines(stdout_buffer, parser, on_progress)
                else:
                    stderr_tail.append(chunk)
                    stderr_size += len(chunk)
                    while stderr_size > self.maximum_stderr_tail_bytes and stderr_tail:
                        stderr_size -= len(stderr_tail.popleft())

            if failure is not None:
                _stop_process(process, grace_seconds=self.terminate_grace_seconds)
                _raise_failure(failure)
            return_code = process.wait(timeout=self.terminate_grace_seconds)
            _emit_complete_progress_lines(stdout_buffer, parser, on_progress, final=True)
            return CommandResult(
                return_code=return_code,
                stderr_tail=b"".join(stderr_tail).decode("utf-8", errors="replace"),
            )
        except BaseException:
            if process.poll() is None:
                _stop_process(process, grace_seconds=self.terminate_grace_seconds)
            raise
        finally:
            process.stdout.close()
            process.stderr.close()
            stdout_thread.join(timeout=self.terminate_grace_seconds)
            stderr_thread.join(timeout=self.terminate_grace_seconds)


class FFprobeDerivativeValidator:
    """Optional structural validation using the existing bounded probe adapter."""

    def __init__(self, probe: MediaProbeLike) -> None:
        self.probe = probe

    def __call__(self, path: Path, kind: DerivativeKind) -> None:
        try:
            metadata = self.probe.probe(path)
        except (FileNotFoundError, MediaProbeError) as exc:
            raise DerivativeProcessError(
                f"FFprobe rejected the staged {kind.value} output: {exc}"
            ) from exc
        if not metadata.video_streams:
            raise DerivativeProcessError(
                f"staged {kind.value} output contains no decodable video/image stream"
            )


@dataclass(frozen=True, slots=True)
class DerivativeResult:
    kind: DerivativeKind
    path: Path
    cache_key: str
    sha256: str
    byte_length: int


class DerivativeGenerator:
    """Execute into a private staging name, validate, then publish once."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        *,
        output_validator: Callable[[Path, DerivativeKind], None] | None = None,
    ) -> None:
        self.runner = runner or SubprocessCommandRunner()
        self.output_validator = output_validator

    def generate(
        self,
        *,
        ffmpeg_executable: Path | str,
        ffmpeg_version: str,
        source: Path | str,
        source_sha256: str,
        target: Path | str,
        spec: DerivativeSpec,
        cancellation: CancellationSignal | None = None,
        timeout_seconds: float = 3_600.0,
        on_progress: ProgressCallback | None = None,
    ) -> DerivativeResult:
        """Generate one immutable derivative without replacing prior output."""

        source_path = Path(source).expanduser().resolve(strict=True)
        target_path = Path(target).expanduser().resolve(strict=False)
        if source_path == target_path:
            raise ValueError("source and target must be different files")
        if target_path.suffix.lower() != spec.expected_suffix:
            raise ValueError(f"{spec.kind.value} output must use the {spec.expected_suffix} suffix")
        if _lexists(target_path):
            raise DerivativeOutputExistsError(f"output already exists: {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path = target_path.with_name(f".{target_path.name}.{uuid4().hex}.part")
        if _lexists(staged_path):
            raise DerivativeProcessError("unique staging path unexpectedly exists")

        plan = build_ffmpeg_command(ffmpeg_executable, source_path, staged_path, spec)
        cancel_signal = cancellation or _NeverCancelled()
        key = derivative_cache_key(
            source_sha256,
            spec,
            ffmpeg_version=ffmpeg_version,
        )
        try:
            result = self.runner.run(
                plan,
                cancellation=cancel_signal,
                timeout_seconds=timeout_seconds,
                on_progress=on_progress,
            )
            if result.return_code != 0:
                detail = result.stderr_tail[-8_192:]
                raise DerivativeProcessError(
                    f"FFmpeg failed with exit code {result.return_code}: {detail}"
                )
            _raise_if_cancelled(cancel_signal)
            byte_length = _validate_staged_output(staged_path)
            if self.output_validator is not None:
                self.output_validator(staged_path, spec.kind)
            _raise_if_cancelled(cancel_signal)
            output_hash = _sha256_file(staged_path, cancellation=cancel_signal)
            _flush_file(staged_path)
            _raise_if_cancelled(cancel_signal)
            try:
                # A same-directory hard link is an atomic create-if-absent operation.
                # Unlike os.replace/rename it cannot overwrite a racing publisher.
                os.link(staged_path, target_path)
            except FileExistsError as exc:
                raise DerivativeOutputExistsError(
                    f"output was published by another operation: {target_path}"
                ) from exc
            except OSError as exc:
                raise DerivativeProcessError(
                    f"could not publish derivative atomically: {exc}"
                ) from exc
            staged_path.unlink()
            return DerivativeResult(
                kind=spec.kind,
                path=target_path,
                cache_key=key,
                sha256=output_hash,
                byte_length=byte_length,
            )
        finally:
            with contextlib.suppress(FileNotFoundError):
                staged_path.unlink()


class _NeverCancelled:
    def is_set(self) -> bool:
        return False


def _start_pipe_reader(
    name: _StreamName,
    stream: IO[bytes],
    messages: queue.Queue[_StreamMessage],
    overflowed: threading.Event,
    maximum_bytes: int,
) -> threading.Thread:
    def read_pipe() -> None:
        consumed = 0
        try:
            while chunk := os.read(stream.fileno(), 4_096):
                consumed += len(chunk)
                if consumed > maximum_bytes:
                    overflowed.set()
                    return
                try:
                    messages.put((name, chunk), timeout=0.5)
                except queue.Full:
                    overflowed.set()
                    return
        finally:
            with contextlib.suppress(queue.Full):
                messages.put((name, None), timeout=0.1)

    thread = threading.Thread(
        target=read_pipe,
        name=f"aidub-ffmpeg-{name}",
        daemon=True,
    )
    thread.start()
    return thread


def _emit_complete_progress_lines(
    buffer: bytearray,
    parser: FFmpegProgressParser,
    callback: ProgressCallback | None,
    *,
    final: bool = False,
) -> None:
    if len(buffer) > 65_536 and b"\n" not in buffer:
        raise DerivativeProcessError("FFmpeg progress line exceeded the safe limit")
    lines = bytes(buffer).split(b"\n")
    remainder = lines.pop()
    if final and remainder:
        lines.append(remainder)
        remainder = b""
    buffer.clear()
    buffer.extend(remainder)
    for encoded_line in lines:
        update = parser.feed_line(encoded_line.decode("utf-8", errors="replace"))
        if update is not None and callback is not None:
            callback(update)


def _signal_process_group(process_id: int, signal_number: int) -> None:
    kill_group = getattr(os, "killpg", None)
    if not callable(kill_group):
        raise OSError("process-group signalling is unavailable")
    cast("Callable[[int, int], None]", kill_group)(process_id, signal_number)


def _stop_process(process: subprocess.Popen[bytes], *, grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            _signal_process_group(process.pid, int(signal.SIGTERM))
        process.wait(timeout=grace_seconds)
    except (OSError, subprocess.TimeoutExpired):
        pass
    else:
        return
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.kill()
        else:
            _signal_process_group(
                process.pid,
                int(getattr(signal, "SIGKILL", signal.SIGTERM)),
            )
    except OSError:
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=grace_seconds)


def _validate_staged_output(path: Path) -> int:
    if not _lexists(path) or path.is_symlink() or not path.is_file():
        raise DerivativeProcessError("FFmpeg did not produce a regular output file")
    byte_length = path.stat().st_size
    if byte_length <= 0:
        raise DerivativeProcessError("FFmpeg produced an empty output file")
    return byte_length


def _raise_failure(failure: DerivativeError) -> None:
    raise failure


def _flush_file(path: Path) -> None:
    # Windows' ``_commit`` requires a writable descriptor; opening without
    # truncation makes the durability step portable while leaving bytes intact.
    with path.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path, *, cancellation: CancellationSignal) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            _raise_if_cancelled(cancellation)
            digest.update(chunk)
    return digest.hexdigest()


def _raise_if_cancelled(cancellation: CancellationSignal) -> None:
    if cancellation.is_set():
        raise DerivativeCancelledError("media derivative was cancelled before publication")


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _speed_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return _optional_decimal(value.removesuffix("x"))


__all__ = [
    "CancellationSignal",
    "CommandResult",
    "CommandRunner",
    "DerivativeCancelledError",
    "DerivativeError",
    "DerivativeGenerator",
    "DerivativeOutputExistsError",
    "DerivativeProcessError",
    "DerivativeResult",
    "DerivativeTimeoutError",
    "FFmpegProgress",
    "FFmpegProgressParser",
    "FFprobeDerivativeValidator",
    "MediaProbeLike",
    "ProgressCallback",
    "SubprocessCommandRunner",
]
