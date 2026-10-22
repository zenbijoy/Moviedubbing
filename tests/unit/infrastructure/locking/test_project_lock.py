from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aidub.infrastructure.locking import (
    ActiveLockCannotBeBrokenError,
    InvalidLockRecordError,
    LockBreakEvent,
    LockContendedError,
    LockNonceMismatchError,
    LockRecordNotFoundError,
    LockState,
    OrphanedLockRecordError,
    ProjectLock,
    UnsafeLockPathError,
)

ROOT = Path(__file__).resolve().parents[4]
_HOLD_SCRIPT = """
import os
import sys
import time
from pathlib import Path
from aidub.infrastructure.locking import ProjectLock

project, ready, release = map(Path, sys.argv[1:])
with ProjectLock(project):
    ready.write_text(str(os.getpid()), encoding="utf-8")
    deadline = time.monotonic() + 15
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("parent did not release lock holder")
        time.sleep(0.02)
"""
_CRASH_SCRIPT = """
import os
import sys
from pathlib import Path
from aidub.infrastructure.locking import ProjectLock

ProjectLock(Path(sys.argv[1])).acquire()
os._exit(73)
"""


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    source = str(ROOT / "src")
    environment["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    return environment


def _spawn_child(script: str, *arguments: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", script, *(str(argument) for argument in arguments)],
        env=_child_environment(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _wait_for_marker(marker: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"child exited before readiness with code {process.returncode}")
        time.sleep(0.02)
    assert marker.is_file(), "child did not publish readiness marker"


def test_context_manager_record_and_idempotent_release(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)

    with lock as entered:
        first = lock.acquire()
        assert entered is lock
        assert first is lock.record
        payload = json.loads(lock.record_path.read_text(encoding="utf-8"))
        assert payload == {
            "format_version": 1,
            "hostname": first.hostname,
            "nonce": first.nonce,
            "process_id": os.getpid(),
            "started_at": first.started_at,
        }
        assert lock.inspect().state is LockState.HELD

    assert not lock.held
    assert not lock.record_path.exists()
    assert lock.lock_path.is_file()  # stable OS-lock gate is intentionally retained
    lock.release()
    assert lock.inspect().state is LockState.UNLOCKED


def test_two_instances_in_one_process_contend(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    first = ProjectLock(project)
    second = ProjectLock(project)

    record = first.acquire()
    try:
        assert second.try_acquire() is None
        with pytest.raises(LockContendedError) as captured:
            second.acquire()
        assert captured.value.record == record
        called = False

        def audit(_event: LockBreakEvent) -> None:
            nonlocal called
            called = True

        with pytest.raises(ActiveLockCannotBeBrokenError):
            second.break_lock(
                expected_nonce=record.nonce,
                reason="operator requested",
                audit_callback=audit,
            )
        assert not called
    finally:
        first.release()


def test_two_spawned_processes_observe_os_lock_contention(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    ready = (tmp_path / "ready").resolve()
    release = (tmp_path / "release").resolve()
    process = _spawn_child(_HOLD_SCRIPT, project, ready, release)
    try:
        _wait_for_marker(ready, process)
        contender = ProjectLock(project)
        inspection = contender.inspect()
        assert inspection.state is LockState.HELD
        assert inspection.record is not None
        assert inspection.record.process_id == int(ready.read_text(encoding="utf-8"))
        assert contender.try_acquire() is None
    finally:
        release.write_text("release", encoding="utf-8")
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
    assert process.returncode == 0, f"child lock holder failed with code {process.returncode}"
    assert ProjectLock(project).inspect().state is LockState.UNLOCKED


def test_crash_leaves_orphan_that_requires_nonce_and_audit(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    process = _spawn_child(_CRASH_SCRIPT, project)
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(5)
        pytest.fail("crashing child did not terminate")
    assert process.returncode == 73, f"child did not crash as expected: {process.returncode}"

    lock = ProjectLock(project)
    inspection = lock.inspect()
    assert inspection.state is LockState.ORPHANED
    assert inspection.record is not None
    record = inspection.record
    assert record.process_id > 0

    # Dead PID and age are diagnostic only: normal acquire still refuses.
    with pytest.raises(OrphanedLockRecordError):
        lock.acquire()
    with pytest.raises(LockNonceMismatchError):
        lock.break_lock(
            expected_nonce="0" * 32,
            reason="wrong observation",
            audit_callback=lambda _event: None,
        )
    assert lock.record_path.exists()

    events: list[LockBreakEvent] = []
    event = lock.break_lock(
        expected_nonce=record.nonce,
        reason="confirmed worker crash",
        audit_callback=events.append,
    )
    assert events == [event]
    assert event.record == record
    assert event.reason == "confirmed worker crash"
    assert lock.inspect().state is LockState.UNLOCKED
    with lock:
        assert lock.held


def test_audit_failure_aborts_guarded_break(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)
    nonce = "a" * 32
    orphan: dict[str, object] = {
        "format_version": 1,
        "hostname": "former-host",
        "nonce": nonce,
        "process_id": 1,
        "started_at": "1999-01-01T00:00:00Z",
    }
    lock.record_path.write_text(json.dumps(orphan), encoding="utf-8")

    def failed_audit(_event: LockBreakEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    with pytest.raises(RuntimeError, match="audit sink"):
        lock.break_lock(
            expected_nonce=nonce,
            reason="manual recovery",
            audit_callback=failed_audit,
        )

    assert lock.record_path.is_file()
    assert lock.inspect().state is LockState.ORPHANED


def test_release_nonce_mismatch_preserves_foreign_record_and_releases_gate(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)
    record = lock.acquire()
    payload = json.loads(lock.record_path.read_text(encoding="utf-8"))
    payload["nonce"] = "b" * 32
    lock.record_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(LockNonceMismatchError, match="owner"):
        lock.release()

    assert not lock.held
    assert lock.record_path.is_file()
    inspection = ProjectLock(project).inspect()
    assert inspection.state is LockState.ORPHANED
    assert inspection.record is not None and inspection.record.nonce != record.nonce


def test_guarded_break_validates_request_and_requires_record(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)

    with pytest.raises(ValueError, match="expected_nonce"):
        lock.break_lock(
            expected_nonce="not-a-nonce",
            reason="operator request",
            audit_callback=lambda _event: None,
        )
    with pytest.raises(ValueError, match="reason"):
        lock.break_lock(
            expected_nonce="a" * 32,
            reason="   ",
            audit_callback=lambda _event: None,
        )
    with pytest.raises(LockRecordNotFoundError):
        lock.break_lock(
            expected_nonce="a" * 32,
            reason="operator request",
            audit_callback=lambda _event: None,
        )


def test_malformed_record_is_not_overwritten(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)
    lock.record_path.write_text('{"process_id":', encoding="utf-8")

    assert lock.inspect().state is LockState.INVALID
    with pytest.raises(InvalidLockRecordError):
        lock.acquire()
    assert lock.record_path.read_text(encoding="utf-8") == '{"process_id":'


@pytest.mark.parametrize(
    "record",
    [
        {},
        {
            "format_version": 2,
            "hostname": "host",
            "nonce": "a" * 32,
            "process_id": 1,
            "started_at": "2000-01-01T00:00:00Z",
        },
        {
            "format_version": 1,
            "hostname": "",
            "nonce": "a" * 32,
            "process_id": 1,
            "started_at": "2000-01-01T00:00:00Z",
        },
        {
            "format_version": 1,
            "hostname": "host",
            "nonce": "A" * 32,
            "process_id": 1,
            "started_at": "2000-01-01T00:00:00Z",
        },
        {
            "format_version": 1,
            "hostname": "host",
            "nonce": "a" * 32,
            "process_id": 0,
            "started_at": "2000-01-01T00:00:00Z",
        },
        {
            "format_version": 1,
            "hostname": "host",
            "nonce": "a" * 32,
            "process_id": 1,
            "started_at": "yesterday",
        },
        {
            "format_version": 1,
            "hostname": "host",
            "nonce": "a" * 32,
            "process_id": 1,
            "started_at": "2000-01-01T01:00:00+01:00",
        },
    ],
)
def test_invalid_structured_records_are_preserved(tmp_path: Path, record: object) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)
    lock.record_path.write_text(json.dumps(record), encoding="utf-8")

    assert lock.inspect().state is LockState.INVALID
    with pytest.raises(InvalidLockRecordError):
        lock.acquire()
    assert lock.record_path.exists()


def test_oversized_record_is_preserved(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    lock = ProjectLock(project)
    lock.record_path.write_bytes(b"x" * (16 * 1024 + 1))

    inspection = lock.inspect()
    assert inspection.state is LockState.INVALID
    assert inspection.detail is not None and "maximum" in inspection.detail
    with pytest.raises(InvalidLockRecordError):
        lock.acquire()


def test_project_lock_rejects_relative_missing_and_non_directory_paths(tmp_path: Path) -> None:
    with pytest.raises(UnsafeLockPathError, match="absolute"):
        ProjectLock(Path("relative.aidub"))
    with pytest.raises(UnsafeLockPathError, match="existing directory"):
        ProjectLock((tmp_path / "missing.aidub").resolve())
    file_path = (tmp_path / "file.aidub").resolve()
    file_path.write_text("not a package", encoding="utf-8")
    with pytest.raises(UnsafeLockPathError, match="directory"):
        ProjectLock(file_path)
    existing = (tmp_path / "not-a-project").resolve()
    existing.mkdir()
    with pytest.raises(UnsafeLockPathError, match=r"\.aidub"):
        ProjectLock(existing)


def test_lock_record_symlink_is_rejected_when_supported(tmp_path: Path) -> None:
    project = (tmp_path / "Movie.aidub").resolve()
    project.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("do not touch", encoding="utf-8")
    record_path = project / ".aidub.lock.json"
    try:
        record_path.symlink_to(outside)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this host")

    lock = ProjectLock(project)
    assert lock.inspect().state is LockState.INVALID
    with pytest.raises(UnsafeLockPathError):
        lock.acquire()
    assert outside.read_text(encoding="utf-8") == "do not touch"
