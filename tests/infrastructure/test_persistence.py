from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from aidub.infrastructure.persistence import (
    ArtifactRecord,
    ArtifactStatus,
    AuditEventRecord,
    DatabaseNotInitializedError,
    InvalidStateTransitionError,
    JobRecord,
    JobState,
    MigrationIntegrityError,
    NewerSchemaError,
    PersistenceError,
    ProjectDatabase,
    ProjectRecord,
    discover_migrations,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations"

ALLOWED_JOB_TRANSITIONS = {
    JobState.QUEUED: {
        JobState.BLOCKED,
        JobState.PREPARING,
        JobState.CANCELLING,
        JobState.CANCELLED,
        JobState.STALE,
    },
    JobState.BLOCKED: {
        JobState.QUEUED,
        JobState.CANCELLING,
        JobState.CANCELLED,
        JobState.STALE,
    },
    JobState.PREPARING: {
        JobState.RUNNING,
        JobState.CANCELLING,
        JobState.FAILED,
        JobState.STALE,
    },
    JobState.RUNNING: {
        JobState.PAUSING,
        JobState.CANCELLING,
        JobState.FAILED,
        JobState.SUCCEEDED,
        JobState.STALE,
    },
    JobState.PAUSING: {
        JobState.PAUSED,
        JobState.CANCELLING,
        JobState.FAILED,
        JobState.STALE,
    },
    JobState.PAUSED: {
        JobState.QUEUED,
        JobState.PREPARING,
        JobState.CANCELLING,
        JobState.CANCELLED,
        JobState.STALE,
    },
    JobState.CANCELLING: {JobState.CANCELLED, JobState.FAILED},
    JobState.CANCELLED: {JobState.QUEUED, JobState.STALE},
    JobState.FAILED: {JobState.QUEUED, JobState.STALE},
    JobState.SUCCEEDED: {JobState.STALE},
    JobState.STALE: {JobState.QUEUED},
}


@pytest.fixture
def database(tmp_path: Path) -> ProjectDatabase:
    result = ProjectDatabase(tmp_path / "Movie.aidub" / "project.db")
    result.initialize()
    result.create_project(ProjectRecord(id="prj_test", name="Test Movie", source_language="en"))
    return result


def test_initialization_enables_safety_pragmas_and_is_idempotent(tmp_path: Path) -> None:
    database = ProjectDatabase(tmp_path / "project.db", busy_timeout_ms=3210)

    first = database.initialize()
    second = database.initialize()

    assert first.applied_versions == (1, 2, 3)
    assert second.applied_versions == ()
    assert [entry.version for entry in database.migration_history()] == [1, 2, 3]
    with database.connection(read_only=False) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 3210
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert database.verify_integrity().database_ok


def test_transaction_rolls_back_and_foreign_keys_are_enforced(database: ProjectDatabase) -> None:
    with pytest.raises(RuntimeError, match="force rollback"), database.transaction() as connection:
        connection.execute(
            "INSERT INTO projects(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("prj_rollback", "Rollback", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        raise RuntimeError("force rollback")
    assert database.get_project("prj_rollback") is None

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        database.create_job(
            JobRecord(
                id="job_orphan",
                project_id="prj_missing",
                job_type="test",
                idempotency_key="orphan-job-key",
            )
        )


def test_nested_write_transaction_is_rejected(database: ProjectDatabase) -> None:
    with (
        database.transaction(),
        pytest.raises(PersistenceError, match="nested"),
        database.transaction(),
    ):
        pass


def test_connection_open_failure_does_not_poison_writer_context(
    database: ProjectDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = database._open_connection
    attempts = 0

    def flaky_open(*, read_only: bool) -> sqlite3.Connection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("simulated open failure")
        return original_open(read_only=read_only)

    monkeypatch.setattr(database, "_open_connection", flaky_open)

    with pytest.raises(sqlite3.OperationalError, match="simulated"), database.transaction():
        pass
    with database.transaction() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1


def test_job_state_machine_and_interrupted_recovery(database: ProjectDatabase) -> None:
    database.create_job(
        JobRecord(
            id="job_render",
            project_id="prj_test",
            job_type="render",
            idempotency_key="render-attempt-one",
        )
    )
    preparing = database.transition_job("job_render", JobState.PREPARING)
    running = database.transition_job(
        "job_render", JobState.RUNNING, expected=JobState.PREPARING, progress=0.25
    )
    assert preparing.state is JobState.PREPARING
    assert running.started_at is not None
    assert running.progress == 0.25

    with pytest.raises(InvalidStateTransitionError):
        database.transition_job("job_render", JobState.QUEUED)

    assert database.recover_interrupted_jobs() == ("job_render",)
    recovered = database.get_job("job_render")
    assert recovered is not None
    assert recovered.state is JobState.FAILED
    assert recovered.error_category == "PROCESS_INTERRUPTED"
    assert recovered.completed_at is not None


@pytest.mark.parametrize("source", list(JobState))
@pytest.mark.parametrize("target", list(JobState))
def test_job_transition_api_exhaustively_matches_contract(
    database: ProjectDatabase,
    source: JobState,
    target: JobState,
) -> None:
    job_id = f"job_api_{source.value.lower()}_{target.value.lower()}"
    database.create_job(
        JobRecord(
            id=job_id,
            project_id="prj_test",
            job_type="state-test",
            idempotency_key=f"api-{source.value}-{target.value}",
            state=source,
        )
    )
    allowed = target is source or target in ALLOWED_JOB_TRANSITIONS[source]

    if allowed:
        assert database.transition_job(job_id, target).state is target
    else:
        with pytest.raises(InvalidStateTransitionError):
            database.transition_job(job_id, target)
        assert database.get_job(job_id).state is source  # type: ignore[union-attr]


def test_job_transition_database_trigger_exhaustively_matches_contract(
    database: ProjectDatabase,
) -> None:
    timestamp = "2026-08-14T00:00:00Z"
    with database.transaction() as connection:
        for source in JobState:
            for target in JobState:
                job_id = f"job_sql_{source.value.lower()}_{target.value.lower()}"
                connection.execute(
                    "INSERT INTO jobs("
                    "id, project_id, job_type, idempotency_key, state, created_at, updated_at"
                    ") VALUES (?, 'prj_test', 'state-test', ?, ?, ?, ?)",
                    (
                        job_id,
                        f"sql-{source.value}-{target.value}",
                        source.value,
                        timestamp,
                        timestamp,
                    ),
                )
                allowed = target is source or target in ALLOWED_JOB_TRANSITIONS[source]
                if allowed:
                    connection.execute(
                        "UPDATE jobs SET state = ? WHERE id = ?", (target.value, job_id)
                    )
                    actual = connection.execute(
                        "SELECT state FROM jobs WHERE id = ?", (job_id,)
                    ).fetchone()[0]
                    assert actual == target.value
                else:
                    with pytest.raises(sqlite3.IntegrityError, match="invalid job state"):
                        connection.execute(
                            "UPDATE jobs SET state = ? WHERE id = ?", (target.value, job_id)
                        )
                    actual = connection.execute(
                        "SELECT state FROM jobs WHERE id = ?", (job_id,)
                    ).fetchone()[0]
                    assert actual == source.value


def test_artifact_content_and_audit_events_are_immutable(database: ProjectDatabase) -> None:
    artifact = database.record_artifact(
        ArtifactRecord(
            id="art_test",
            project_id="prj_test",
            sha256="a" * 64,
            byte_length=12,
            relative_path=f"sha256/aa/{'a' * 64}",
            logical_type="waveform",
        )
    )
    database.mark_artifact_status(artifact.id, ArtifactStatus.MISSING)
    assert database.get_artifact(artifact.id).status is ArtifactStatus.MISSING  # type: ignore[union-attr]
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute("UPDATE artifacts SET sha256 = ? WHERE id = ?", ("b" * 64, artifact.id))

    database.append_audit_event(
        AuditEventRecord(
            id="evt_test",
            project_id="prj_test",
            action="artifact.registered",
            actor_type="system",
            artifact_id=artifact.id,
            details={"sha256": artifact.sha256},
        )
    )
    with (
        pytest.raises(sqlite3.IntegrityError, match="append-only"),
        database.transaction() as connection,
    ):
        connection.execute("DELETE FROM audit_events WHERE id = 'evt_test'")
    assert database.audit_events("prj_test")[0].details == {"sha256": artifact.sha256}


def test_existing_unversioned_database_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE customer_data(value TEXT NOT NULL)")
    connection.commit()
    connection.close()

    with pytest.raises(DatabaseNotInitializedError, match="schema_version"):
        ProjectDatabase(path).initialize()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'customer_data'"
        ).fetchone()
    finally:
        connection.close()


def test_changed_migration_is_rejected(tmp_path: Path) -> None:
    migration_copy = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, migration_copy)
    database = ProjectDatabase(tmp_path / "project.db", migrations_directory=migration_copy)
    database.initialize()
    with (migration_copy / "0001_initial.sql").open("a", encoding="utf-8") as stream:
        stream.write("\n-- tampered\n")

    with pytest.raises(MigrationIntegrityError, match="differs"):
        database.initialize()


def test_default_migrations_are_package_bundled_and_match_operator_copies() -> None:
    bundled = discover_migrations()
    operator_copies = discover_migrations(MIGRATIONS)

    assert bundled[0].source.parent.name == "migrations_sql"
    assert bundled[0].source.parent.parent.name == "persistence"
    assert [(item.version, item.name, item.checksum) for item in bundled] == [
        (item.version, item.name, item.checksum) for item in operator_copies
    ]


def test_migration_creates_backup_and_newer_schema_stays_readable(tmp_path: Path) -> None:
    migration_copy = tmp_path / "migrations"
    migration_copy.mkdir()
    shutil.copy2(MIGRATIONS / "0001_initial.sql", migration_copy)
    database = ProjectDatabase(tmp_path / "project.db", migrations_directory=migration_copy)
    database.initialize()
    shutil.copy2(MIGRATIONS / "0002_indexes_and_guards.sql", migration_copy)

    migrated = database.initialize()

    assert migrated.applied_versions == (2,)
    assert migrated.backup_path is not None
    assert Path(migrated.backup_path).is_file()
    backup_connection = sqlite3.connect(migrated.backup_path)
    try:
        assert (
            backup_connection.execute("SELECT max(version) FROM schema_version").fetchone()[0] == 1
        )
    finally:
        backup_connection.close()

    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO schema_version(version, name, checksum, applied_at) VALUES (3, ?, ?, ?)",
            ("future", "c" * 64, "2030-01-01T00:00:00Z"),
        )
    with pytest.raises(NewerSchemaError):
        database.initialize()
    with database.connection(read_only=True) as connection:
        assert connection.execute("SELECT max(version) FROM schema_version").fetchone()[0] == 3
