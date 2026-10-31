from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from aidub.infrastructure.artifacts import ArtifactStore
from aidub.infrastructure.persistence import (
    ArtifactRecord,
    JobRecord,
    JobState,
    ProjectDatabase,
    ProjectRecord,
)


@pytest.fixture
def project_storage(tmp_path: Path) -> tuple[ProjectDatabase, ArtifactStore]:
    package = tmp_path / "LocalizedFeature.aidub"
    database = ProjectDatabase(package / "project.db")
    database.initialize()
    database.create_project(
        ProjectRecord(id="prj_feature", name="Localized Feature", source_language="en")
    )
    return database, ArtifactStore(package / "artifacts")


def test_publish_then_database_commit_reconciles_cleanly(
    project_storage: tuple[ProjectDatabase, ArtifactStore],
) -> None:
    database, store = project_storage
    published = store.publish_bytes(b"generated voice take")
    database.record_artifact(
        ArtifactRecord(
            id="art_voice_take",
            project_id="prj_feature",
            sha256=published.sha256,
            byte_length=published.byte_length,
            relative_path=published.relative_path,
            logical_type="voice_take",
            engine_id="test-tts",
            engine_version="1.0.0",
            parameters={"seed": 42},
        )
    )

    report = store.reconcile(database.artifact_inventory("prj_feature"))

    assert report.clean
    assert report.orphan_objects == ()
    database.assert_integrity()


def test_failed_database_commit_leaves_recoverable_orphan(
    project_storage: tuple[ProjectDatabase, ArtifactStore],
) -> None:
    database, store = project_storage
    published = store.publish_bytes(b"worker output before catalog commit")

    with pytest.raises(sqlite3.IntegrityError):
        database.record_artifact(
            ArtifactRecord(
                id="art_uncommitted",
                project_id="prj_does_not_exist",
                sha256=published.sha256,
                byte_length=published.byte_length,
                relative_path=published.relative_path,
                logical_type="voice_take",
            )
        )

    report = store.reconcile(database.artifact_inventory("prj_feature"))
    assert report.orphan_objects == (published.sha256,)
    assert store.read_bytes(published.sha256) == b"worker output before catalog commit"


def test_startup_reconciles_abandoned_stages_and_interrupted_jobs(
    project_storage: tuple[ProjectDatabase, ArtifactStore],
) -> None:
    database, store = project_storage
    database.create_job(
        JobRecord(
            id="job_tts",
            project_id="prj_feature",
            job_type="tts",
            idempotency_key="tts-worker-attempt",
        )
    )
    database.transition_job("job_tts", JobState.PREPARING)
    database.transition_job("job_tts", JobState.RUNNING)
    stage = store.stage_bytes(b"partial worker payload")
    os.utime(stage.path, (1.0, 1.0))

    recovered_jobs = database.recover_interrupted_jobs()
    artifact_report = store.reconcile(
        database.artifact_inventory("prj_feature"),
        staging_ttl_seconds=0,
    )

    assert recovered_jobs == ("job_tts",)
    recovered = database.get_job("job_tts")
    assert recovered is not None and recovered.state is JobState.FAILED
    assert artifact_report.staged_removed == (stage.path.name,)
    assert not stage.path.exists()
