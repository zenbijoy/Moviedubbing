from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aidub.infrastructure.catalog import (
    CatalogConflictError,
    CatalogIntegrityError,
    CatalogPathState,
    InvalidCatalogPathError,
    NewerCatalogSchemaError,
    ProjectCatalog,
    UnrecognizedCatalogError,
    inspect_project_path,
    validate_project_path,
)


@pytest.fixture
def catalog(tmp_path: Path) -> ProjectCatalog:
    result = ProjectCatalog((tmp_path / "application" / "catalog.db").resolve())
    result.initialize()
    return result


def _package(tmp_path: Path, name: str) -> Path:
    path = (tmp_path / f"{name}.aidub").resolve()
    path.mkdir()
    return path


def test_catalog_initialization_is_safe_idempotent_and_wal(tmp_path: Path) -> None:
    path = (tmp_path / "catalog.db").resolve()
    catalog = ProjectCatalog(path, busy_timeout_ms=3456)

    catalog.initialize()
    catalog.initialize()

    with catalog.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA application_id").fetchone()[0] == 0x41494442
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 3456
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM recent_projects")
    catalog.assert_integrity()


def test_unicode_recent_projects_order_move_and_pin(
    catalog: ProjectCatalog, tmp_path: Path
) -> None:
    early = datetime(2026, 8, 1, tzinfo=UTC)
    late = early + timedelta(days=1)
    bangla = _package(tmp_path, "বাংলা-চলচ্চিত্র")
    hindi = _package(tmp_path, "हिन्दी-फ़िल्म")

    first = catalog.upsert_project(
        project_id="prj_bangla",
        name="বাংলা চলচ্চিত্র",
        path=bangla,
        opened_at=early,
    )
    catalog.upsert_project(
        project_id="prj_hindi",
        name="हिन्दी फ़िल्म",
        path=hindi,
        opened_at=late,
    )
    catalog.set_pinned("prj_bangla", pinned=True)

    recent = catalog.list_recent()
    assert [item.project_id for item in recent] == ["prj_bangla", "prj_hindi"]
    assert recent[0].name == "বাংলা চলচ্চিত্র"
    assert recent[0].last_opened_at == early
    assert catalog.get_project_by_path(bangla) == recent[0]

    moved = _package(tmp_path, "Moved বাংলা")
    updated = catalog.upsert_project(
        project_id="prj_bangla",
        name="বাংলা চলচ্চিত্র — moved",
        path=moved,
        opened_at=late + timedelta(days=1),
    )
    assert updated.created_at == first.created_at
    assert updated.pinned
    assert catalog.get_project_by_path(bangla) is None
    assert catalog.get_project_by_path(moved) == updated


def test_catalog_path_conflict_rolls_back(catalog: ProjectCatalog, tmp_path: Path) -> None:
    package = _package(tmp_path, "Shared")
    original = catalog.upsert_project(project_id="prj_original", name="Original", path=package)

    with pytest.raises(CatalogConflictError, match="already registered"):
        catalog.upsert_project(project_id="prj_other", name="Other", path=package)

    assert catalog.list_recent() == (original,)


def test_remove_only_catalog_row_never_project_files(
    catalog: ProjectCatalog, tmp_path: Path
) -> None:
    package = _package(tmp_path, "KeepMe")
    source = package / "original.mkv"
    source.write_bytes(b"irreplaceable")
    catalog.upsert_project(project_id="prj_keep", name="Keep Me", path=package)

    assert catalog.remove_project("prj_keep")
    assert not catalog.remove_project("prj_keep")
    assert source.read_bytes() == b"irreplaceable"
    assert package.is_dir()


def test_missing_paths_require_explicit_registration_and_have_health(
    catalog: ProjectCatalog, tmp_path: Path
) -> None:
    missing = (tmp_path / "OfflineArchive.aidub").resolve()
    with pytest.raises(InvalidCatalogPathError, match="does not exist"):
        catalog.upsert_project(project_id="prj_offline", name="Offline", path=missing)

    stored = catalog.upsert_project(
        project_id="prj_offline",
        name="Offline",
        path=missing,
        require_exists=False,
    )
    assert stored.path == missing
    assert inspect_project_path(stored.path).state is CatalogPathState.MISSING


def test_available_and_non_directory_health_states(tmp_path: Path) -> None:
    available = _package(tmp_path, "Available")
    assert inspect_project_path(available).available
    file_path = (tmp_path / "FormerProject.aidub").resolve()
    file_path.write_bytes(b"file")
    inspection = inspect_project_path(file_path)
    assert inspection.state is CatalogPathState.NOT_DIRECTORY
    assert not inspection.available


def test_catalog_argument_validation_and_missing_rows(
    catalog: ProjectCatalog, tmp_path: Path
) -> None:
    package = _package(tmp_path, "Arguments")
    with pytest.raises(ValueError, match="project_id"):
        catalog.upsert_project(project_id="invalid", name="Movie", path=package)
    with pytest.raises(ValueError, match="project name"):
        catalog.upsert_project(project_id="prj_valid", name="  ", path=package)
    with pytest.raises(ValueError, match="limit"):
        catalog.list_recent(limit=0)
    with pytest.raises(ValueError, match="project_id"):
        catalog.get_project("bad")
    with pytest.raises(KeyError):
        catalog.set_pinned("prj_missing", pinned=True)
    assert catalog.get_project("prj_missing") is None


def test_path_validation_rejects_relative_suffix_file_and_symlink(tmp_path: Path) -> None:
    with pytest.raises(InvalidCatalogPathError, match="absolute"):
        validate_project_path("relative.aidub")
    with pytest.raises(InvalidCatalogPathError, match=r"\.aidub"):
        validate_project_path((tmp_path / "movie.txt").resolve(), require_exists=False)
    file_path = (tmp_path / "file.aidub").resolve()
    file_path.write_bytes(b"not a directory")
    with pytest.raises(InvalidCatalogPathError, match="not a directory"):
        validate_project_path(file_path)

    target = _package(tmp_path, "Real")
    link = (tmp_path / "Linked.aidub").resolve()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this host")
    with pytest.raises(InvalidCatalogPathError, match="link/reparse"):
        validate_project_path(link)
    assert inspect_project_path(link).state is CatalogPathState.UNSAFE


def test_newer_catalog_is_refused_before_any_write(tmp_path: Path) -> None:
    path = (tmp_path / "future.db").resolve()
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE future_marker(value TEXT NOT NULL)")
    connection.execute("INSERT INTO future_marker VALUES ('preserve me')")
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()
    original = path.read_bytes()

    with pytest.raises(NewerCatalogSchemaError) as captured:
        ProjectCatalog(path).initialize()

    assert captured.value.found_version == 99
    assert path.read_bytes() == original
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT value FROM future_marker").fetchone()[0] == "preserve me"
    finally:
        connection.close()


def test_unversioned_nonempty_database_is_not_adopted(tmp_path: Path) -> None:
    path = (tmp_path / "other.db").resolve()
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE customer_data(value TEXT)")
    connection.commit()
    connection.close()

    with pytest.raises(UnrecognizedCatalogError):
        ProjectCatalog(path).initialize()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'customer_data'"
        ).fetchone()
    finally:
        connection.close()


def test_version_one_wrong_application_identity_is_refused_before_wal(tmp_path: Path) -> None:
    path = (tmp_path / "lookalike.db").resolve()
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE recent_projects("
        "project_id TEXT, project_path TEXT, path_key TEXT, project_name TEXT, "
        "last_opened_at TEXT, pinned INTEGER, created_at TEXT, updated_at TEXT)"
    )
    connection.execute("PRAGMA user_version = 1")
    connection.execute("PRAGMA application_id = 123")
    connection.commit()
    connection.close()

    with pytest.raises(CatalogIntegrityError, match="identity"):
        ProjectCatalog(path).initialize()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA application_id").fetchone()[0] == 123
    finally:
        connection.close()


def test_invalid_sqlite_catalog_is_rejected(tmp_path: Path) -> None:
    path = (tmp_path / "invalid.db").resolve()
    path.write_bytes(b"not sqlite data")

    with pytest.raises(CatalogIntegrityError, match="valid SQLite"):
        ProjectCatalog(path).initialize()


def test_catalog_constructor_validates_database_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidCatalogPathError, match="absolute"):
        ProjectCatalog("catalog.db")
    with pytest.raises(ValueError, match="busy_timeout"):
        ProjectCatalog((tmp_path / "catalog.db").resolve(), busy_timeout_ms=-1)
    directory = (tmp_path / "directory.db").resolve()
    directory.mkdir()
    with pytest.raises(InvalidCatalogPathError, match="regular file"):
        ProjectCatalog(directory)


def test_multiple_catalog_instances_serialize_short_writes(tmp_path: Path) -> None:
    database_path = (tmp_path / "catalog.db").resolve()
    ProjectCatalog(database_path).initialize()
    packages = [_package(tmp_path, f"Movie-{index:02d}") for index in range(24)]

    def register(index: int) -> str:
        instance = ProjectCatalog(database_path)
        result = instance.upsert_project(
            project_id=f"prj_movie_{index:02d}",
            name=f"Movie {index:02d}",
            path=packages[index],
        )
        return result.project_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        identifiers = tuple(executor.map(register, range(len(packages))))

    assert len(set(identifiers)) == len(packages)
    catalog = ProjectCatalog(database_path)
    assert len(catalog.list_recent()) == len(packages)
    catalog.assert_integrity()
