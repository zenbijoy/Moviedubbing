"""Durable metadata checkpoints for studio project stages.

These checkpoints record metadata and its integrity digest. They are not database
backups and cannot restore project media or application state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class RecoveryUnavailableError(RuntimeError):
    """Raised when a full project recovery operation has no implementation."""


class CheckpointSnapshot(ContractModel):
    """Integrity-checked metadata checkpoint descriptor."""

    snapshot_id: Identifier
    project_id: Identifier
    stage_name: str = Field(min_length=1)
    timestamp_utc: str = Field(min_length=1)
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata_json: str = Field(default="{}")


class CrashRecoveryEngine:
    """Persist and list metadata checkpoints without claiming to restore projects."""

    def __init__(self, storage_dir: str = "storage/snapshots") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _metadata_digest(
        snapshot_id: str,
        project_id: str,
        stage_name: str,
        timestamp_utc: str,
        metadata_json: str,
    ) -> str:
        payload = {
            "metadata_json": metadata_json,
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "stage_name": stage_name,
            "timestamp_utc": timestamp_utc,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def create_snapshot(
        self,
        project_id: str,
        stage_name: str,
        metadata: dict[str, str] | None = None,
    ) -> CheckpointSnapshot:
        """Atomically persist a metadata checkpoint with a real SHA-256 digest."""
        pid = Identifier(project_id)
        sid = Identifier(f"snap_{uuid4().hex}")
        now_str = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        digest = self._metadata_digest(sid, pid, stage_name, now_str, metadata_json)

        snapshot = CheckpointSnapshot(
            snapshot_id=sid,
            project_id=pid,
            stage_name=stage_name,
            timestamp_utc=now_str,
            metadata_sha256=digest,
            metadata_json=metadata_json,
        )

        out_path = self.storage_dir / f"{pid}_{sid}.json"
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_dir,
                prefix=f".{sid}_",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(snapshot.model_dump_json(indent=2))
                temp_file.flush()
                os.fsync(temp_file.fileno())
            temp_path.replace(out_path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

        logger.info(
            "recovery: created metadata checkpoint %s for project %s at stage %s",
            sid,
            pid,
            stage_name,
        )
        return snapshot

    def list_snapshots(self, project_id: str) -> list[CheckpointSnapshot]:
        """List valid metadata checkpoints for a project, newest first."""
        pid = Identifier(project_id)
        snapshots: list[CheckpointSnapshot] = []
        for file in self.storage_dir.glob(f"{pid}_snap_*.json"):
            try:
                snap = CheckpointSnapshot.model_validate_json(file.read_text(encoding="utf-8"))
                expected_digest = self._metadata_digest(
                    snap.snapshot_id,
                    snap.project_id,
                    snap.stage_name,
                    snap.timestamp_utc,
                    snap.metadata_json,
                )
                if snap.project_id != pid or snap.metadata_sha256 != expected_digest:
                    logger.warning("recovery: checkpoint integrity check failed for %s", file.name)
                    continue
                snapshots.append(snap)
            except Exception as err:
                logger.warning("recovery: failed reading checkpoint %s: %s", file.name, err)

        snapshots.sort(key=lambda snap: snap.timestamp_utc, reverse=True)
        return snapshots

    def detect_unclean_shutdown(self, project_id: str) -> bool:
        """Unclean shutdown detection needs a durable process journal, which is not configured."""
        Identifier(project_id)
        raise RecoveryUnavailableError(
            "Unclean shutdown detection is unavailable: no process journal or database WAL "
            "is configured. Metadata checkpoints alone cannot establish shutdown state."
        )

    def recover_latest_valid_snapshot(self, project_id: str) -> CheckpointSnapshot | None:
        """Fail closed because these metadata checkpoints do not contain restorable project data."""
        if not self.list_snapshots(project_id):
            return None
        raise RecoveryUnavailableError(
            "Project recovery is unavailable: stored checkpoints contain metadata only and "
            "cannot restore project media or application state."
        )


__all__ = [
    "CheckpointSnapshot",
    "CrashRecoveryEngine",
    "RecoveryUnavailableError",
]
