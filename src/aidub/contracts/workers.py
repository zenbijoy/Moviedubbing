"""Worker lifecycle and capability contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .base import ContractModel, HealthState, Identifier, utc_now

__all__ = [
    "ContractModel",
    "HealthState",
    "Identifier",
    "ProtocolVersion",
    "WorkerCapability",
    "WorkerHandshake",
    "WorkerHeartbeat",
    "utc_now",
]


class WorkerCapability(StrEnum):
    MEDIA_PROBE = "media_probe"
    PROXY = "proxy"
    WAVEFORM = "waveform"
    THUMBNAIL = "thumbnail"
    ASR = "asr"
    DIARIZATION = "diarization"
    TRANSLATION = "translation"
    VOICE = "voice"
    SEPARATION = "separation"
    VISION = "vision"
    LIPSYNC = "lipsync"
    MIX = "mix"
    RENDER = "render"


class ProtocolVersion(ContractModel):
    major: int = Field(ge=1)
    minor: int = Field(ge=0)

    def is_compatible_with(self, other: ProtocolVersion) -> bool:
        return self.major == other.major and self.minor >= other.minor


class WorkerHandshake(ContractModel):
    worker_id: Identifier
    worker_version: str = Field(min_length=1, max_length=120)
    engine_id: Identifier
    protocol: ProtocolVersion
    process_id: int = Field(gt=0)
    capabilities: frozenset[WorkerCapability]
    gpu_ids: tuple[int, ...] = ()
    model_ids: tuple[Identifier, ...] = ()
    started_at: datetime = Field(default_factory=utc_now)


class WorkerHeartbeat(ContractModel):
    worker_id: Identifier
    state: HealthState
    observed_at: datetime = Field(default_factory=utc_now)
    active_job_id: Identifier | None = None
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    ram_mb: int | None = Field(default=None, ge=0)
    vram_mb: int | None = Field(default=None, ge=0)
    queue_depth: int = Field(default=0, ge=0)
