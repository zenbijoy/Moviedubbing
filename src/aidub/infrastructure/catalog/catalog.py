"""A small SQLite catalog kept separate from every project database."""

from __future__ import annotations

import os
import re
import sqlite3
import stat
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import (
    CatalogConflictError,
    CatalogIntegrityError,
    InvalidCatalogPathError,
    NewerCatalogSchemaError,
    UnrecognizedCatalogError,
)
from .models import CatalogPathInspection, CatalogPathState, CatalogProject

if TYPE_CHECKING:
    from collections.abc import Iterator


_SUPPORTED_SCHEMA_VERSION = 1
_APPLICATION_ID = 0x41494442  # ASCII "AIDB"
_PROJECT_ID = re.compile(r"^prj_[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
_WRITER_LOCKS: dict[str, threading.RLock] = {}
_WRITER_LOCKS_GUARD = threading.Lock()
_WRITER_CONTEXT = threading.local()

_SCHEMA_V1 = """
CREATE TABLE recent_projects (
    project_id TEXT PRIMARY KEY CHECK (
        project_id GLOB 'prj_*' AND length(project_id) BETWEEN 7 AND 68
    ),
    project_path TEXT NOT NULL CHECK (length(project_path) > 0),
    path_key TEXT NOT NULL UNIQUE CHECK (length(path_key) > 0),
    project_name TEXT NOT NULL CHECK (length(trim(project_name)) > 0),
    last_opened_at TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_recent_projects_order
    ON recent_projects(pinned DESC, last_opened_at DESC, project_name COLLATE NOCASE);
"""


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except (FileNotFoundError, PermissionError, OSError):
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _writer_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _WRITER_LOCKS_GUARD:
        return _WRITER_LOCKS.setdefault(key, threading.RLock())


def _format_utc(value: datetime | None = None) -> str:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("catalog timestamps must be timezone-aware")
    return instant.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise CatalogIntegrityError("catalog timestamp is not text")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CatalogIntegrityError(f"invalid catalog timestamp: {value!r}") from exc
    if instant.tzinfo is None or instant.utcoffset() != UTC.utcoffset(instant):
        raise CatalogIntegrityError("stored catalog timestamp must use UTC")
    return instant.astimezone(UTC)


def _validate_project_identity(project_id: str, name: str) -> tuple[str, str]:
    if _PROJECT_ID.fullmatch(project_id) is None:
        raise ValueError("project_id must be a valid prj_ identifier")
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 512:
        raise ValueError("project name must contain 1 to 512 non-whitespace characters")
    return project_id, normalized_name


def _validate_path_syntax(path: Path | str) -> Path:
    raw = os.fspath(path)
    if not raw or "\0" in raw:
        raise InvalidCatalogPathError("project path must not be empty or contain NUL")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise InvalidCatalogPathError("catalog project paths must be absolute")
    if candidate.suffix.casefold() != ".aidub":
        raise InvalidCatalogPathError("catalog path must identify a .aidub project directory")
    return candidate


def validate_project_path(path: Path | str, *, require_exists: bool = True) -> Path:
    """Normalize a project path and reject links/non-directories when present."""

    candidate = _validate_path_syntax(path)
    if _is_link_or_reparse(candidate):
        raise InvalidCatalogPathError(
            f"project package cannot be a link/reparse point: {candidate}"
        )
    if candidate.exists() and not candidate.is_dir():
        raise InvalidCatalogPathError(f"project package path is not a directory: {candidate}")
    if require_exists and not candidate.is_dir():
        raise InvalidCatalogPathError(f"project package does not exist: {candidate}")
    return candidate.resolve(strict=False)


def inspect_project_path(path: Path | str) -> CatalogPathInspection:
    """Inspect a stored package path without mutating or recursively traversing it."""

    try:
        candidate = _validate_path_syntax(path)
    except InvalidCatalogPathError as exc:
        candidate = Path(os.fspath(path))
        return CatalogPathInspection(
            path=candidate,
            state=CatalogPathState.INVALID_SUFFIX,
            detail=str(exc),
        )
    if _is_link_or_reparse(candidate):
        return CatalogPathInspection(
            path=candidate,
            state=CatalogPathState.UNSAFE,
            detail="project path is a link/reparse point",
        )
    if not candidate.exists():
        return CatalogPathInspection(path=candidate, state=CatalogPathState.MISSING)
    if not candidate.is_dir():
        return CatalogPathInspection(path=candidate, state=CatalogPathState.NOT_DIRECTORY)
    return CatalogPathInspection(path=candidate.resolve(), state=CatalogPathState.AVAILABLE)


def default_catalog_path() -> Path:
    """Return a stdlib-only, per-user catalog location without creating it."""

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "AIDubStudio" / "catalog.db"
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / "aidub-studio" / "catalog.db"


class ProjectCatalog:
    """Recent-project index; never stores project editorial/media data."""

    def __init__(self, path: Path | str, *, busy_timeout_ms: int = 5_000) -> None:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise InvalidCatalogPathError("catalog database path must be absolute")
        if _is_link_or_reparse(candidate):
            raise InvalidCatalogPathError("catalog database cannot be a link/reparse point")
        try:
            if candidate.exists() and not candidate.is_file():
                raise InvalidCatalogPathError("catalog database path is not a regular file")
        except (PermissionError, OSError):
            pass
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must not be negative")
        self.path = candidate.resolve(strict=False)
        self.busy_timeout_ms = busy_timeout_ms
        self._writer_lock = _writer_lock(self.path)

    @property
    def supported_schema_version(self) -> int:
        return _SUPPORTED_SCHEMA_VERSION

    def _open(self, *, read_only: bool) -> sqlite3.Connection:
        if _is_link_or_reparse(self.path):
            raise InvalidCatalogPathError("catalog database became a link/reparse point")
        if read_only:
            if not self.path.is_file():
                raise CatalogIntegrityError(f"catalog database does not exist: {self.path}")
            connection = sqlite3.connect(
                f"{self.path.as_uri()}?mode=ro",
                uri=True,
                isolation_level=None,
                timeout=self.busy_timeout_ms / 1000,
            )
        else:
            connection = sqlite3.connect(
                self.path,
                isolation_level=None,
                timeout=self.busy_timeout_ms / 1000,
            )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms:d}")
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        else:
            mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
            if mode != "wal":
                connection.close()
                raise CatalogIntegrityError(f"SQLite refused catalog WAL mode: {mode!r}")
            connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._open(read_only=True)
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        key = os.path.normcase(str(self.path))
        active: set[str] = getattr(_WRITER_CONTEXT, "active_paths", set())
        if key in active:
            raise CatalogIntegrityError("nested catalog write transactions are not supported")
        with self._writer_lock:
            active = set(active)
            active.add(key)
            _WRITER_CONTEXT.active_paths = active
            connection: sqlite3.Connection | None = None
            try:
                connection = self._open(read_only=False)
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except BaseException:
                if connection is not None and connection.in_transaction:
                    connection.rollback()
                raise
            finally:
                if connection is not None:
                    connection.close()
                active.remove(key)
                _WRITER_CONTEXT.active_paths = active

    def _preflight_version(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        try:
            connection = sqlite3.connect(
                f"{self.path.as_uri()}?mode=ro", uri=True, isolation_level=None
            )
            try:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise CatalogIntegrityError(f"catalog is not a valid SQLite database: {exc}") from exc
        if version > _SUPPORTED_SCHEMA_VERSION:
            raise NewerCatalogSchemaError(version, _SUPPORTED_SCHEMA_VERSION)
        if version == 0 and tables:
            raise UnrecognizedCatalogError(
                "non-empty SQLite database has no recognized catalog schema version"
            )
        if version == 1 and (application_id != _APPLICATION_ID or tables != {"recent_projects"}):
            raise CatalogIntegrityError("catalog schema identity/tables do not match version 1")

    def initialize(self) -> None:
        """Create/upgrade the catalog, refusing unknown or newer databases."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._preflight_version()
        with self._transaction() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > _SUPPORTED_SCHEMA_VERSION:
                raise NewerCatalogSchemaError(version, _SUPPORTED_SCHEMA_VERSION)
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if version == 0:
                if tables:
                    raise UnrecognizedCatalogError(
                        "non-empty SQLite database has no recognized catalog schema version"
                    )
                for statement in self._schema_statements():
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id = {_APPLICATION_ID:d}")
                connection.execute(f"PRAGMA user_version = {_SUPPORTED_SCHEMA_VERSION:d}")
            elif version == 1:
                application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
                if application_id != _APPLICATION_ID or tables != {"recent_projects"}:
                    raise CatalogIntegrityError(
                        "catalog schema identity/tables do not match version 1"
                    )
        self.assert_integrity()

    @staticmethod
    def _schema_statements() -> tuple[str, ...]:
        statements: list[str] = []
        buffer: list[str] = []
        for line in _SCHEMA_V1.splitlines(keepends=True):
            buffer.append(line)
            candidate = "".join(buffer).strip()
            if candidate and sqlite3.complete_statement(candidate):
                statements.append(candidate)
                buffer.clear()
        if "".join(buffer).strip():
            raise CatalogIntegrityError("catalog schema contains incomplete SQL")
        return tuple(statements)

    def assert_integrity(self) -> None:
        with self.connection() as connection:
            messages = tuple(str(row[0]) for row in connection.execute("PRAGMA integrity_check"))
            foreign_keys = tuple(connection.execute("PRAGMA foreign_key_check"))
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        if (
            messages != ("ok",)
            or foreign_keys
            or version != _SUPPORTED_SCHEMA_VERSION
            or application_id != _APPLICATION_ID
        ):
            raise CatalogIntegrityError(
                "catalog failed validation: "
                f"integrity={messages!r}, foreign_keys={foreign_keys!r}, "
                f"version={version}, application_id={application_id}"
            )

    def upsert_project(
        self,
        *,
        project_id: str,
        name: str,
        path: Path | str,
        opened_at: datetime | None = None,
        pinned: bool | None = None,
        require_exists: bool = True,
    ) -> CatalogProject:
        """Record a successful open while preserving pinned state by default."""

        project_id, name = _validate_project_identity(project_id, name)
        normalized_path = validate_project_path(path, require_exists=require_exists)
        path_text = str(normalized_path)
        path_key = os.path.normcase(path_text)
        opened_text = _format_utc(opened_at)
        now = _format_utc()
        with self._transaction() as connection:
            conflict = connection.execute(
                "SELECT project_id FROM recent_projects WHERE path_key = ? AND project_id <> ?",
                (path_key, project_id),
            ).fetchone()
            if conflict is not None:
                raise CatalogConflictError(
                    f"project path is already registered to {conflict['project_id']}"
                )
            existing = connection.execute(
                "SELECT pinned, created_at FROM recent_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if existing is None:
                effective_pinned = False if pinned is None else pinned
                created_at = now
                connection.execute(
                    "INSERT INTO recent_projects("
                    "project_id, project_path, path_key, project_name, last_opened_at, "
                    "pinned, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        project_id,
                        path_text,
                        path_key,
                        name,
                        opened_text,
                        int(effective_pinned),
                        created_at,
                        now,
                    ),
                )
            else:
                effective_pinned = bool(existing["pinned"]) if pinned is None else pinned
                created_at = str(existing["created_at"])
                connection.execute(
                    "UPDATE recent_projects SET project_path = ?, path_key = ?, project_name = ?, "
                    "last_opened_at = ?, pinned = ?, updated_at = ? WHERE project_id = ?",
                    (
                        path_text,
                        path_key,
                        name,
                        opened_text,
                        int(effective_pinned),
                        now,
                        project_id,
                    ),
                )
        return CatalogProject(
            project_id=project_id,
            name=name,
            path=normalized_path,
            last_opened_at=_parse_utc(opened_text),
            pinned=effective_pinned,
            created_at=_parse_utc(created_at),
            updated_at=_parse_utc(now),
        )

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> CatalogProject:
        try:
            path = _validate_path_syntax(str(row["project_path"]))
            project_id, name = _validate_project_identity(
                str(row["project_id"]), str(row["project_name"])
            )
            pinned_raw = int(row["pinned"])
            if pinned_raw not in {0, 1}:
                raise CatalogIntegrityError("stored pinned flag is not boolean")
            return CatalogProject(
                project_id=project_id,
                name=name,
                path=path,
                last_opened_at=_parse_utc(row["last_opened_at"]),
                pinned=bool(pinned_raw),
                created_at=_parse_utc(row["created_at"]),
                updated_at=_parse_utc(row["updated_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, CatalogIntegrityError):
                raise
            raise CatalogIntegrityError(f"stored catalog project is invalid: {exc}") from exc

    def get_project(self, project_id: str) -> CatalogProject | None:
        if _PROJECT_ID.fullmatch(project_id) is None:
            raise ValueError("project_id must be a valid prj_ identifier")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM recent_projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return None if row is None else self._project_from_row(row)

    def get_project_by_path(self, path: Path | str) -> CatalogProject | None:
        normalized = validate_project_path(path, require_exists=False)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM recent_projects WHERE path_key = ?",
                (os.path.normcase(str(normalized)),),
            ).fetchone()
        return None if row is None else self._project_from_row(row)

    def list_recent(self, *, limit: int = 100) -> tuple[CatalogProject, ...]:
        if not 1 <= limit <= 10_000:
            raise ValueError("catalog result limit must be between 1 and 10000")
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM recent_projects "
                "ORDER BY pinned DESC, last_opened_at DESC, project_name COLLATE NOCASE "
                "LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._project_from_row(row) for row in rows)

    def set_pinned(self, project_id: str, *, pinned: bool) -> CatalogProject:
        if _PROJECT_ID.fullmatch(project_id) is None:
            raise ValueError("project_id must be a valid prj_ identifier")
        with self._transaction() as connection:
            cursor = connection.execute(
                "UPDATE recent_projects SET pinned = ?, updated_at = ? WHERE project_id = ?",
                (int(pinned), _format_utc(), project_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(project_id)
            row = connection.execute(
                "SELECT * FROM recent_projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        assert row is not None
        return self._project_from_row(row)

    def remove_project(self, project_id: str) -> bool:
        """Remove only the catalog row; project files are never touched."""

        if _PROJECT_ID.fullmatch(project_id) is None:
            raise ValueError("project_id must be a valid prj_ identifier")
        with self._transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM recent_projects WHERE project_id = ?", (project_id,)
            )
        return cursor.rowcount == 1


__all__ = [
    "ProjectCatalog",
    "default_catalog_path",
    "inspect_project_path",
    "validate_project_path",
]
