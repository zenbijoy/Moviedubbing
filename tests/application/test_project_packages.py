from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aidub.application.projects import (
    InvalidProjectPackageError,
    OpenedProject,
    ProjectAlreadyExistsError,
    ProjectManifestMismatchError,
    ProjectPackageService,
)
from aidub.domain.project import Project, ProjectSettings
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate
from aidub.infrastructure.catalog import ProjectCatalog
from aidub.infrastructure.locking import LockContendedError, LockState, ProjectLock
from aidub.infrastructure.persistence import JobRecord, JobState


def project_settings() -> ProjectSettings:
    return ProjectSettings(
        video_rate=RationalRate(numerator=24_000, denominator=1_001),
        source_language="en-US",
    )


def source_authorization() -> SourceAuthorization:
    return SourceAuthorization(
        acknowledged=True,
        acknowledged_by="producer@example.test",
        acknowledged_at=datetime(2026, 8, 14, tzinfo=UTC),
        authority_basis="Licensed multinational localization production",
        evidence_reference="contract-2026-08",
    )


def create_project(tmp_path: Path) -> OpenedProject:
    return ProjectPackageService().create(
        tmp_path / "Feature Film",
        name="Feature Film",
        settings=project_settings(),
        source_authorization=source_authorization(),
        localization_locales=("bn-BD", "hi-IN"),
        actor_id="producer@example.test",
    )


def test_create_publishes_complete_portable_project_atomically(tmp_path: Path) -> None:
    opened = create_project(tmp_path)

    assert opened.paths.root.name == "Feature Film.aidub"
    assert opened.paths.manifest.is_file()
    assert opened.paths.database.is_file()
    assert (opened.paths.localizations / "bn-BD").is_dir()
    assert (opened.paths.localizations / "hi-IN").is_dir()
    assert opened.artifact_reconciliation.clean

    manifest = Project.model_validate_json(opened.paths.manifest.read_text(encoding="utf-8"))
    stored = opened.database.get_project(manifest.project_id)
    assert stored is not None
    assert stored.name == "Feature Film"
    assert stored.source_language == "en-US"
    events = opened.database.audit_events(manifest.project_id)
    assert [event.action for event in events] == ["PROJECT_CREATED"]


def test_open_recovers_interrupted_jobs_and_audits_recovery(tmp_path: Path) -> None:
    opened = create_project(tmp_path)
    opened.database.create_job(
        JobRecord(
            id="job_interrupted_asr",
            project_id=opened.project.project_id,
            job_type="asr",
            idempotency_key="asr/source/v1",
        )
    )
    opened.database.transition_job("job_interrupted_asr", JobState.PREPARING)
    opened.database.transition_job("job_interrupted_asr", JobState.RUNNING)

    recovered = ProjectPackageService().open(opened.paths.root)

    assert recovered.recovered_job_ids == ("job_interrupted_asr",)
    job = recovered.database.get_job("job_interrupted_asr")
    assert job is not None and job.state is JobState.FAILED
    recovered_actions = [
        event.action for event in recovered.database.audit_events(opened.project.project_id)
    ]
    assert recovered_actions == [
        "PROJECT_CREATED",
        "INTERRUPTED_JOBS_RECOVERED",
    ]


def test_creation_never_overwrites_existing_target(tmp_path: Path) -> None:
    existing = tmp_path / "Existing.aidub"
    existing.mkdir()
    marker = existing / "owned-by-user.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ProjectAlreadyExistsError):
        ProjectPackageService().create(
            existing,
            name="Existing",
            settings=project_settings(),
            source_authorization=source_authorization(),
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_open_rejects_manifest_database_disagreement(tmp_path: Path) -> None:
    opened = create_project(tmp_path)
    tampered = opened.project.model_copy(update={"name": "Tampered Name"})
    opened.paths.manifest.write_text(tampered.model_dump_json(), encoding="utf-8")

    with pytest.raises(ProjectManifestMismatchError, match="name"):
        ProjectPackageService().open(opened.paths.root)


def test_open_rejects_incomplete_or_wrong_suffix_package(tmp_path: Path) -> None:
    directory = tmp_path / "not-a-project"
    directory.mkdir()

    with pytest.raises(InvalidProjectPackageError):
        ProjectPackageService().open(directory)


def test_localization_directories_require_unique_language_tags(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        ProjectPackageService().create(
            tmp_path / "Duplicate Locales",
            name="Duplicate Locales",
            settings=project_settings(),
            source_authorization=source_authorization(),
            localization_locales=("bn-BD", "BN-bd"),
        )


def test_editing_session_holds_exclusive_lock_until_closed(tmp_path: Path) -> None:
    opened = create_project(tmp_path)
    session = ProjectPackageService().open_session(opened.paths.root)
    try:
        assert session.holds_exclusive_lock
        assert ProjectLock(opened.paths.root).inspect().state is LockState.HELD
        with pytest.raises(LockContendedError):
            ProjectPackageService().open(opened.paths.root)
    finally:
        session.close()

    assert ProjectLock(opened.paths.root).inspect().state is LockState.UNLOCKED
    assert not (opened.paths.root / ".aidub.lock.json").exists()
    ProjectPackageService().open(opened.paths.root)


def test_successful_open_updates_separate_recent_project_catalog(tmp_path: Path) -> None:
    opened = create_project(tmp_path)
    catalog = ProjectCatalog((tmp_path / "catalog" / "catalog.db").resolve())

    registered = ProjectPackageService(catalog=catalog).open(opened.paths.root)

    assert registered.catalog_registered
    assert registered.warnings == ()
    recent = catalog.list_recent()
    assert [(item.project_id, item.name, item.path) for item in recent] == [
        (opened.project.project_id, "Feature Film", opened.paths.root)
    ]
