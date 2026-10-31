from __future__ import annotations

import hashlib
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from aidub.domain.time import RationalRate
from aidub.media.commands import DerivativeKind, FFmpegCommandPlan, ProxySpec
from aidub.media.derivatives import (
    CancellationSignal,
    CommandResult,
    DerivativeCancelledError,
    DerivativeGenerator,
    DerivativeOutputExistsError,
    DerivativeTimeoutError,
    FFmpegProgress,
    ProgressCallback,
    SubprocessCommandRunner,
)


@pytest.fixture
def fake_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "fake ffmpeg ; literal.exe"
    executable.write_bytes(b"not invoked by the injectable runner")
    return executable


@dataclass
class FakeRunner:
    output: bytes = b"valid derivative bytes"
    cancel_after_partial: bool = False
    plans: list[FFmpegCommandPlan] = field(default_factory=list)

    def run(
        self,
        plan: FFmpegCommandPlan,
        *,
        cancellation: CancellationSignal,
        timeout_seconds: float,
        on_progress: ProgressCallback | None = None,
    ) -> CommandResult:
        del timeout_seconds, on_progress
        self.plans.append(plan)
        if self.cancel_after_partial:
            plan.staged_output.write_bytes(b"partial")
            if cancellation.is_set():
                raise DerivativeCancelledError("cancelled by test token")
        plan.staged_output.write_bytes(self.output)
        return CommandResult(return_code=0, stderr_tail="")


def _python_process_plan(tmp_path: Path, code: str) -> FFmpegCommandPlan:
    executable = Path(sys.executable).resolve(strict=True)
    source = tmp_path / "runner-source.bin"
    source.write_bytes(b"source")
    staged_output = (tmp_path / "runner-output.part").resolve()
    return FFmpegCommandPlan(
        kind=DerivativeKind.PROXY,
        executable=executable,
        source=source.resolve(),
        staged_output=staged_output,
        argv=(str(executable), "-c", code, str(staged_output)),
    )


def test_untrusted_looking_paths_are_literal_argv_and_output_is_published(
    tmp_path: Path,
    fake_executable: Path,
) -> None:
    source = tmp_path / "movie ; $(touch should-not-exist).mkv"
    source.write_bytes(b"source bytes")
    target = tmp_path / "proxy ; $(touch should-not-exist).mp4"
    runner = FakeRunner()
    generator = DerivativeGenerator(runner)

    result = generator.generate(
        ffmpeg_executable=fake_executable,
        ffmpeg_version="test-7.1",
        source=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        target=target,
        spec=ProxySpec(frame_rate=RationalRate(numerator=24_000, denominator=1_001)),
    )

    assert target.read_bytes() == runner.output
    assert result.sha256 == hashlib.sha256(runner.output).hexdigest()
    assert len(runner.plans) == 1
    argv = runner.plans[0].argv
    assert argv[argv.index("-i") + 1] == str(source.resolve())
    assert argv.count(str(source.resolve())) == 1
    assert argv[0] == str(fake_executable.resolve())


def test_cancellation_removes_staging_and_never_publishes_partial_output(
    tmp_path: Path,
    fake_executable: Path,
) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source bytes")
    target = tmp_path / "proxy.mp4"
    cancelled = threading.Event()
    cancelled.set()
    runner = FakeRunner(cancel_after_partial=True)

    with pytest.raises(DerivativeCancelledError):
        DerivativeGenerator(runner).generate(
            ffmpeg_executable=fake_executable,
            ffmpeg_version="test-7.1",
            source=source,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            target=target,
            spec=ProxySpec(),
            cancellation=cancelled,
        )

    assert not target.exists()
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_existing_target_is_never_overwritten_or_executed(
    tmp_path: Path,
    fake_executable: Path,
) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source bytes")
    target = tmp_path / "proxy.mp4"
    target.write_bytes(b"keep me")
    runner = FakeRunner()

    with pytest.raises(DerivativeOutputExistsError):
        DerivativeGenerator(runner).generate(
            ffmpeg_executable=fake_executable,
            ffmpeg_version="test-7.1",
            source=source,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            target=target,
            spec=ProxySpec(),
        )

    assert target.read_bytes() == b"keep me"
    assert runner.plans == []


def test_subprocess_runner_cancels_from_machine_progress_callback(tmp_path: Path) -> None:
    plan = _python_process_plan(
        tmp_path,
        "import sys,time; print('frame=1'); print('progress=continue'); "
        "sys.stdout.flush(); time.sleep(30)",
    )
    cancelled = threading.Event()
    updates: list[FFmpegProgress] = []

    def cancel_on_progress(update: FFmpegProgress) -> None:
        updates.append(update)
        cancelled.set()

    with pytest.raises(DerivativeCancelledError):
        SubprocessCommandRunner().run(
            plan,
            cancellation=cancelled,
            timeout_seconds=5,
            on_progress=cancel_on_progress,
        )

    assert updates[0].frame == 1
    assert updates[0].state == "continue"


def test_subprocess_runner_enforces_deadline_without_ffmpeg(tmp_path: Path) -> None:
    plan = _python_process_plan(tmp_path, "import time; time.sleep(30)")

    with pytest.raises(DerivativeTimeoutError):
        SubprocessCommandRunner().run(
            plan,
            cancellation=threading.Event(),
            timeout_seconds=0.2,
        )
