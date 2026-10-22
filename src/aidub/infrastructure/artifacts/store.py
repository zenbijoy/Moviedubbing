"""Crash-safe, content-addressed storage for immutable binary artifacts."""

from __future__ import annotations

import hashlib
import io
import os
import re
import stat
import tempfile
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from typing import BinaryIO

from .errors import (
    ArtifactHashMismatchError,
    ArtifactSizeMismatchError,
    ArtifactStoreError,
    CorruptArtifactError,
    InvalidArtifactHashError,
    UnknownStageError,
    UnsafeArtifactPathError,
)
from .models import (
    ArtifactValidation,
    PublishedArtifact,
    ReconciliationReport,
    StagedArtifact,
    ValidationState,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STAGE_TOKEN = re.compile(r"^[0-9a-f]{32}$")
_STAGE_FILENAME = re.compile(r"^[0-9a-f]{32}\.[A-Za-z0-9_-]+\.part$")
_COPY_CHUNK_SIZE = 4 * 1024 * 1024


def _validate_sha256(value: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InvalidArtifactHashError("artifact hash must be 64 lowercase SHA-256 hex characters")
    return value


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _fsync_directory(path: Path) -> None:
    """Persist directory metadata where the host exposes directory fsync."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        # Windows does not expose portable directory handles through os.open.
        if os.name == "nt":
            return
        raise
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _close_descriptor(descriptor: int) -> None:
    """Best-effort cleanup for a descriptor already adopted by ``fdopen``."""

    with suppress(OSError):
        os.close(descriptor)


class ArtifactStore:
    """Store bytes at ``sha256/<prefix>/<digest>`` without overwriting objects.

    Publication is stage -> file fsync -> SHA-256 -> atomic hard-link publish ->
    directory fsync. The caller records the returned descriptor in SQLite only
    after publication. If that database commit fails, reconciliation reports the
    unreferenced object as an orphan; valid immutable bytes remain reusable.
    """

    def __init__(self, root: Path | str) -> None:
        candidate = Path(root).expanduser()
        if candidate.exists() and _is_link_or_reparse(candidate):
            raise UnsafeArtifactPathError(f"artifact-store root cannot be a link: {candidate}")
        self.root = candidate.resolve()
        self.objects_directory = self.root / "sha256"
        self.staging_directory = self.root / ".staging"
        self._publish_lock = threading.Lock()
        self.initialize()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_directory(self.root)
        self._ensure_directory(self.objects_directory)
        self._ensure_directory(self.staging_directory)

    def _ensure_directory(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeArtifactPathError(f"path escapes artifact store: {path}") from exc
        current = self.root
        if current.exists():
            if _is_link_or_reparse(current) or not current.is_dir():
                raise UnsafeArtifactPathError(f"unsafe artifact-store directory: {current}")
        else:
            current.mkdir()
        for component in relative.parts:
            if component in {"", ".", ".."}:
                raise UnsafeArtifactPathError(f"unsafe path component: {component!r}")
            current = current / component
            with suppress(FileExistsError):
                current.mkdir()
            if _is_link_or_reparse(current) or not current.is_dir():
                raise UnsafeArtifactPathError(f"unsafe artifact-store directory: {current}")

    def _object_path(self, digest: str, *, create_parent: bool) -> Path:
        digest = _validate_sha256(digest)
        parent = self.objects_directory / digest[:2]
        if create_parent:
            self._ensure_directory(parent)
        elif parent.exists() and (_is_link_or_reparse(parent) or not parent.is_dir()):
            raise UnsafeArtifactPathError(f"unsafe artifact prefix directory: {parent}")
        target = parent / digest
        # This is both a containment check and defense against unexpected path rules.
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeArtifactPathError("computed artifact path escaped its root") from exc
        return target

    def relative_path(self, digest: str) -> str:
        return self._object_path(digest, create_parent=False).relative_to(self.root).as_posix()

    def path_for(self, digest: str) -> Path:
        """Return the deterministic path; this does not assert the object exists."""

        return self._object_path(digest, create_parent=False)

    def stage(self, source: BinaryIO, *, expected_size: int | None = None) -> StagedArtifact:
        if expected_size is not None and expected_size < 0:
            raise ValueError("expected_size must not be negative")
        self._ensure_directory(self.staging_directory)
        token = uuid.uuid4().hex
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f"{token}.", suffix=".part", dir=self.staging_directory
        )
        path = Path(raw_path)
        with ExitStack() as cleanup:
            cleanup.callback(path.unlink, missing_ok=True)
            cleanup.callback(_close_descriptor, descriptor)
            byte_length = self._copy_and_sync(source, descriptor)
            self._assert_expected_size(byte_length, expected_size)
            _fsync_directory(self.staging_directory)
            cleanup.pop_all()
            return StagedArtifact(token=token, path=path, byte_length=byte_length)

    @staticmethod
    def _copy_and_sync(source: BinaryIO, descriptor: int) -> int:
        byte_length = 0
        with os.fdopen(descriptor, "wb", closefd=True) as destination:
            while True:
                chunk = source.read(_COPY_CHUNK_SIZE)
                if not chunk:
                    break
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise TypeError("binary artifact source returned non-bytes data")
                destination.write(chunk)
                byte_length += len(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        return byte_length

    @staticmethod
    def _assert_expected_size(byte_length: int, expected_size: int | None) -> None:
        if expected_size is not None and byte_length != expected_size:
            raise ArtifactSizeMismatchError(f"staged {byte_length} bytes, expected {expected_size}")

    def stage_bytes(self, content: bytes | bytearray | memoryview) -> StagedArtifact:
        data = bytes(content)
        return self.stage(io.BytesIO(data), expected_size=len(data))

    def stage_file(
        self,
        source: Path | str,
        *,
        allow_symlink_source: bool = False,
    ) -> StagedArtifact:
        path = Path(source)
        if _is_link_or_reparse(path) and not allow_symlink_source:
            raise UnsafeArtifactPathError(f"source link requires explicit opt-in: {path}")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ArtifactStoreError(f"artifact source is not a regular file: {path}")
        with path.open("rb") as stream:
            return self.stage(stream, expected_size=info.st_size)

    def _stage_path(self, staged: StagedArtifact) -> Path:
        if _STAGE_TOKEN.fullmatch(staged.token) is None:
            raise UnknownStageError("invalid stage token")
        path = staged.path.resolve(strict=False)
        try:
            path.relative_to(self.staging_directory)
        except ValueError as exc:
            raise UnknownStageError("stage is outside this artifact store") from exc
        if not path.name.startswith(f"{staged.token}.") or path.suffix != ".part":
            raise UnknownStageError("stage filename does not match its token")
        if _is_link_or_reparse(path):
            raise UnsafeArtifactPathError(f"staged artifact cannot be a link: {path}")
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise UnknownStageError(f"staged artifact no longer exists: {path}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise UnsafeArtifactPathError(f"stage is not a regular file: {path}")
        if info.st_size != staged.byte_length:
            raise ArtifactSizeMismatchError(
                f"stage changed after creation: {info.st_size} != {staged.byte_length}"
            )
        return path

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        byte_length = 0
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise UnsafeArtifactPathError(f"artifact is not a regular file: {path}")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                while chunk := stream.read(_COPY_CHUNK_SIZE):
                    digest.update(chunk)
                    byte_length += len(chunk)
        finally:
            os.close(descriptor)
        return digest.hexdigest(), byte_length

    def publish(
        self,
        staged: StagedArtifact,
        *,
        expected_sha256: str | None = None,
    ) -> PublishedArtifact:
        """Hash and atomically publish a fully-fsynced stage."""

        if expected_sha256 is not None:
            expected_sha256 = _validate_sha256(expected_sha256)
        stage_path = self._stage_path(staged)
        digest, byte_length = self._hash_file(stage_path)
        if byte_length != staged.byte_length:
            raise ArtifactSizeMismatchError("stage length changed while it was being hashed")
        if expected_sha256 is not None and digest != expected_sha256:
            raise ArtifactHashMismatchError(
                f"staged artifact hash {digest} does not match expected {expected_sha256}"
            )
        target = self._object_path(digest, create_parent=True)
        deduplicated = False
        newly_published = False
        with self._publish_lock:
            if target.exists() or _is_link_or_reparse(target):
                self._assert_existing_object(target, digest, byte_length)
                deduplicated = True
            else:
                try:
                    # Hard-link creation is an atomic, no-clobber publication on the
                    # same filesystem. It avoids os.replace overwriting immutable data.
                    os.link(stage_path, target, follow_symlinks=False)
                except FileExistsError:
                    self._assert_existing_object(target, digest, byte_length)
                    deduplicated = True
                except OSError as exc:
                    raise ArtifactStoreError(
                        "filesystem cannot atomically publish content via a hard link"
                    ) from exc
                if not deduplicated:
                    newly_published = True
                    # The staged inode was fsynced before hashing; the hard link
                    # names that same durable inode. Read-only Windows handles do
                    # not support os.fsync, so only directory metadata remains.
                    _fsync_directory(target.parent)
            stage_path.unlink()
            # chmod changes every hard-link name on Windows. Apply it only after
            # removing the staging name, otherwise Windows refuses that unlink.
            if newly_published:
                target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            _fsync_directory(self.staging_directory)
        return PublishedArtifact(
            sha256=digest,
            byte_length=byte_length,
            relative_path=target.relative_to(self.root).as_posix(),
            path=target,
            deduplicated=deduplicated,
        )

    def publish_bytes(
        self,
        content: bytes | bytearray | memoryview,
        *,
        expected_sha256: str | None = None,
    ) -> PublishedArtifact:
        return self.publish(self.stage_bytes(content), expected_sha256=expected_sha256)

    def publish_file(
        self,
        source: Path | str,
        *,
        expected_sha256: str | None = None,
        allow_symlink_source: bool = False,
    ) -> PublishedArtifact:
        return self.publish(
            self.stage_file(source, allow_symlink_source=allow_symlink_source),
            expected_sha256=expected_sha256,
        )

    def discard_stage(self, staged: StagedArtifact) -> None:
        path = self._stage_path(staged)
        path.unlink()
        _fsync_directory(self.staging_directory)

    def _assert_existing_object(self, path: Path, digest: str, expected_size: int) -> None:
        if _is_link_or_reparse(path):
            raise UnsafeArtifactPathError(f"content object cannot be a link: {path}")
        validation = self.validate(digest, expected_size=expected_size, full_hash=True)
        if not validation.valid:
            raise CorruptArtifactError(
                f"existing object at {path} failed validation: {validation.state.value}"
            )

    def validate(
        self,
        digest: str,
        *,
        expected_size: int | None = None,
        full_hash: bool = True,
    ) -> ArtifactValidation:
        digest = _validate_sha256(digest)
        if expected_size is not None and expected_size < 0:
            raise ValueError("expected_size must not be negative")
        try:
            path = self._object_path(digest, create_parent=False)
        except UnsafeArtifactPathError as exc:
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.UNSAFE,
                path=self.objects_directory / digest[:2] / digest,
                expected_size=expected_size,
                detail=str(exc),
            )
        if not path.exists() and not path.is_symlink():
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.MISSING,
                path=path,
                expected_size=expected_size,
            )
        if _is_link_or_reparse(path):
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.UNSAFE,
                path=path,
                expected_size=expected_size,
                detail="artifact is a link or reparse point",
            )
        try:
            info = path.lstat()
        except OSError as exc:
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.UNSAFE,
                path=path,
                expected_size=expected_size,
                detail=str(exc),
            )
        if not stat.S_ISREG(info.st_mode):
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.NOT_REGULAR_FILE,
                path=path,
                expected_size=expected_size,
                actual_size=info.st_size,
            )
        if expected_size is not None and info.st_size != expected_size:
            return ArtifactValidation(
                sha256=digest,
                state=ValidationState.SIZE_MISMATCH,
                path=path,
                expected_size=expected_size,
                actual_size=info.st_size,
            )
        if full_hash:
            try:
                actual_hash, actual_size = self._hash_file(path)
            except (OSError, UnsafeArtifactPathError) as exc:
                return ArtifactValidation(
                    sha256=digest,
                    state=ValidationState.UNSAFE,
                    path=path,
                    expected_size=expected_size,
                    actual_size=info.st_size,
                    detail=str(exc),
                )
            if actual_hash != digest:
                return ArtifactValidation(
                    sha256=digest,
                    state=ValidationState.HASH_MISMATCH,
                    path=path,
                    expected_size=expected_size,
                    actual_size=actual_size,
                    actual_sha256=actual_hash,
                )
        return ArtifactValidation(
            sha256=digest,
            state=ValidationState.VALID,
            path=path,
            expected_size=expected_size,
            actual_size=info.st_size,
            actual_sha256=digest if full_hash else None,
        )

    @contextmanager
    def open(
        self,
        digest: str,
        *,
        expected_size: int | None = None,
        verify: bool = True,
    ) -> Iterator[BinaryIO]:
        validation = self.validate(digest, expected_size=expected_size, full_hash=verify)
        if not validation.valid:
            raise CorruptArtifactError(
                f"artifact {digest} is not readable: {validation.state.value}"
            )
        stream = validation.path.open("rb")
        try:
            yield stream
        finally:
            stream.close()

    def read_bytes(self, digest: str, *, verify: bool = True) -> bytes:
        with self.open(digest, verify=verify) as stream:
            return stream.read()

    def reconcile(
        self,
        expected: Mapping[str, int] | None = None,
        *,
        staging_ttl_seconds: float = 24 * 60 * 60,
        remove_abandoned_stages: bool = True,
        full_hash: bool = True,
        now: float | None = None,
    ) -> ReconciliationReport:
        """Validate objects and safely clean expired, unpublished stage files.

        Content objects are never deleted here. Objects absent from ``expected``
        are reported as orphans for a later reachability/retention policy.
        """

        if staging_ttl_seconds < 0:
            raise ValueError("staging_ttl_seconds must not be negative")
        expected_inventory: dict[str, int] | None = None
        if expected is not None:
            expected_inventory = {}
            for digest, size in expected.items():
                expected_inventory[_validate_sha256(digest)] = int(size)
                if int(size) < 0:
                    raise ValueError("expected artifact size must not be negative")

        clock = time.time() if now is None else now
        valid, corrupt, unsafe, errors, found = self._scan_objects(
            expected_inventory, full_hash=full_hash
        )
        staged_removed, staged_retained = self._reconcile_stages(
            cutoff=clock - staging_ttl_seconds,
            remove_abandoned=remove_abandoned_stages,
            unsafe=unsafe,
            errors=errors,
        )
        if staged_removed:
            _fsync_directory(self.staging_directory)

        missing = (
            set(expected_inventory).difference(found) if expected_inventory is not None else set()
        )
        orphans = found.difference(expected_inventory) if expected_inventory is not None else set()
        return ReconciliationReport(
            valid_objects=tuple(sorted(valid)),
            missing_objects=tuple(sorted(missing)),
            corrupt_objects=tuple(sorted(corrupt)),
            orphan_objects=tuple(sorted(orphans)),
            staged_removed=tuple(staged_removed),
            staged_retained=tuple(staged_retained),
            unsafe_entries=tuple(sorted(set(unsafe))),
            errors=tuple(errors),
        )

    def _scan_objects(
        self,
        expected: Mapping[str, int] | None,
        *,
        full_hash: bool,
    ) -> tuple[set[str], set[str], list[str], list[str], set[str]]:
        valid: set[str] = set()
        corrupt: set[str] = set()
        unsafe: list[str] = []
        errors: list[str] = []
        found: set[str] = set()
        self._ensure_directory(self.objects_directory)
        for prefix in sorted(self.objects_directory.iterdir(), key=lambda item: item.name):
            if (
                _is_link_or_reparse(prefix)
                or not prefix.is_dir()
                or re.fullmatch(r"[0-9a-f]{2}", prefix.name) is None
            ):
                unsafe.append(str(prefix.relative_to(self.root)))
                continue
            for entry in sorted(prefix.iterdir(), key=lambda item: item.name):
                relative = str(entry.relative_to(self.root))
                if _SHA256.fullmatch(entry.name) is None or entry.name[:2] != prefix.name:
                    unsafe.append(relative)
                    continue
                digest = entry.name
                found.add(digest)
                size = expected.get(digest) if expected is not None else None
                try:
                    result = self.validate(digest, expected_size=size, full_hash=full_hash)
                except ArtifactStoreError as exc:
                    corrupt.add(digest)
                    errors.append(f"{relative}: {exc}")
                    continue
                if result.valid:
                    valid.add(digest)
                else:
                    corrupt.add(digest)
                    if result.state in {ValidationState.UNSAFE, ValidationState.NOT_REGULAR_FILE}:
                        unsafe.append(relative)
        return valid, corrupt, unsafe, errors, found

    def _reconcile_stages(
        self,
        *,
        cutoff: float,
        remove_abandoned: bool,
        unsafe: list[str],
        errors: list[str],
    ) -> tuple[list[str], list[str]]:
        removed: list[str] = []
        retained: list[str] = []
        self._ensure_directory(self.staging_directory)
        for entry in sorted(self.staging_directory.iterdir(), key=lambda item: item.name):
            relative = str(entry.relative_to(self.root))
            if _is_link_or_reparse(entry):
                unsafe.append(relative)
                continue
            try:
                info = entry.lstat()
            except OSError as exc:
                errors.append(f"{relative}: {exc}")
                continue
            if not stat.S_ISREG(info.st_mode) or _STAGE_FILENAME.fullmatch(entry.name) is None:
                unsafe.append(relative)
                continue
            if info.st_mtime <= cutoff and remove_abandoned:
                try:
                    entry.unlink()
                    removed.append(entry.name)
                except OSError as exc:
                    errors.append(f"{relative}: {exc}")
            else:
                retained.append(entry.name)
        return removed, retained
