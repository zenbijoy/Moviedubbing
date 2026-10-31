from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from aidub.infrastructure.artifacts import (
    ArtifactHashMismatchError,
    ArtifactStore,
    CorruptArtifactError,
    InvalidArtifactHashError,
    ValidationState,
)


def test_publish_fsync_hash_atomic_path_and_deduplication(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    content = b"immutable movie artifact"
    expected_hash = hashlib.sha256(content).hexdigest()

    first = store.publish_bytes(content, expected_sha256=expected_hash)
    second = store.publish_bytes(content)

    assert first.sha256 == expected_hash
    assert first.byte_length == len(content)
    assert first.relative_path == f"sha256/{expected_hash[:2]}/{expected_hash}"
    assert first.path.read_bytes() == content
    assert not first.deduplicated
    assert second.deduplicated
    assert not any(store.staging_directory.iterdir())


def test_expected_hash_mismatch_never_publishes(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    staged = store.stage_bytes(b"actual")

    with pytest.raises(ArtifactHashMismatchError):
        store.publish(staged, expected_sha256="0" * 64)

    assert staged.path.is_file()
    assert not any(store.objects_directory.rglob("?" * 64))
    store.discard_stage(staged)


@pytest.mark.parametrize("digest", ["", "../escape", "A" * 64, "0" * 63, "g" * 64])
def test_hash_input_cannot_control_paths(tmp_path: Path, digest: str) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    with pytest.raises(InvalidArtifactHashError):
        store.path_for(digest)


def test_validation_detects_content_tampering(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    artifact = store.publish_bytes(b"trusted")
    artifact.path.chmod(stat.S_IREAD | stat.S_IWRITE)
    artifact.path.write_bytes(b"altered")

    validation = store.validate(artifact.sha256, expected_size=artifact.byte_length)

    assert validation.state in {ValidationState.SIZE_MISMATCH, ValidationState.HASH_MISMATCH}
    with pytest.raises(CorruptArtifactError), store.open(artifact.sha256):
        pass


def test_reconciliation_reports_missing_orphan_and_removes_only_known_stages(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    artifact = store.publish_bytes(b"orphan")
    stage = store.stage_bytes(b"abandoned")
    os.utime(stage.path, (10.0, 10.0))
    unknown = store.staging_directory / "manual.part"
    unknown.write_bytes(b"must not be deleted")
    missing = hashlib.sha256(b"missing").hexdigest()

    report = store.reconcile(
        {missing: 7},
        staging_ttl_seconds=60,
        now=10_000,
    )

    assert report.missing_objects == (missing,)
    assert report.orphan_objects == (artifact.sha256,)
    assert stage.path.name in report.staged_removed
    assert not stage.path.exists()
    assert unknown.is_file()
    assert ".staging/manual.part" in {entry.replace("\\", "/") for entry in report.unsafe_entries}


def test_reconcile_detects_corrupt_expected_object(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    artifact = store.publish_bytes(b"original")
    artifact.path.chmod(stat.S_IREAD | stat.S_IWRITE)
    artifact.path.write_bytes(b"tampered")

    report = store.reconcile({artifact.sha256: len(b"tampered")})

    assert report.corrupt_objects == (artifact.sha256,)
    assert not report.clean
