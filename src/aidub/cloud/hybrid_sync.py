"""
Cloud-Hybrid Project Synchronization Engine.

Manages differential chunk hashing, offline snapshot queuing, bandwidth throttling,
and secure cloud object storage (S3 / Azure Blob / GCS) synchronization for projects and render caches.
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class CloudSyncUnavailableError(RuntimeError):
    """Raised when no real cloud object-storage adapter has been configured."""


class SyncChunk(ContractModel):
    """Differential data chunk container with SHA-256 integrity validation."""

    chunk_id: Identifier
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    uploaded: bool = False


class CloudSyncManifest(ContractModel):
    """Cloud synchronization manifest tracking remote project state."""

    manifest_id: Identifier
    project_id: Identifier
    remote_version: int = Field(default=0, ge=0)
    chunks: list[SyncChunk] = Field(default_factory=list)
    bandwidth_limit_kbps: int = Field(default=5000, gt=0)


class CloudHybridSyncEngine:
    """
    Orchestrates differential chunk synchronization between local workstation and cloud storage.
    """

    def create_sync_manifest(self, project_id: str, local_version: int = 1) -> CloudSyncManifest:
        """Reject cloud sync until a storage provider and local project source exist."""
        raise CloudSyncUnavailableError(
            "Cloud sync is unavailable: configure an S3, Azure Blob, or GCS storage adapter "
            "before creating a remote manifest. No upload was attempted."
        )

    def synchronize_project(self, manifest: CloudSyncManifest) -> CloudSyncManifest:
        """Reject upload rather than marking local chunks as remotely uploaded."""
        raise CloudSyncUnavailableError(
            "Cloud sync is unavailable: no cloud storage adapter is configured. "
            "The manifest was not uploaded."
        )


__all__ = [
    "CloudHybridSyncEngine",
    "CloudSyncManifest",
    "CloudSyncUnavailableError",
    "SyncChunk",
]
