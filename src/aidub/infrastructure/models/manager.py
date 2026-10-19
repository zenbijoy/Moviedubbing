"""Model registry, verification and lifecycle manager."""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelKind(StrEnum):
    """Categorical kind of AI model."""

    ASR = "asr"
    TTS = "tts"
    SEPARATION = "separation"
    DIARIZATION = "diarization"
    VAD = "vad"
    TRANSLATION = "translation"
    LIP_SYNC = "lip_sync"
    EMOTION = "emotion"
    OTHER = "other"


class ModelStatus(StrEnum):
    """Lifecycle status of a model in the manager."""

    UNKNOWN = "unknown"
    REGISTERED = "registered"
    CACHED = "cached"
    LOADED = "loaded"
    EVICTED = "evicted"
    FAILED = "failed"


class ModelIntegrityError(RuntimeError):
    """Raised when loading unverified or checksum-corrupted model weights."""


class ModelDescriptor(BaseModel):
    """Immutable specification for a verifiable model asset."""

    model_id: str
    model_kind: ModelKind
    version: str = "1.0.0"
    weights_sha256: str
    vram_mb: int = Field(default=0, ge=0)
    ram_mb: int = Field(default=0, ge=0)
    cache_path: str
    load_priority: int = Field(default=10, ge=0)


class ModelEntry(BaseModel):
    """Stateful record tracking model verification and residency."""

    descriptor: ModelDescriptor
    verified: bool = False
    status: ModelStatus = ModelStatus.REGISTERED


class ModelManager:
    """Manages model registration, cryptographic verification, and memory residency."""

    def __init__(self) -> None:
        self._entries: dict[str, ModelEntry] = {}
        self._loaded: dict[str, ModelDescriptor] = {}

    def register(self, descriptor: ModelDescriptor) -> None:
        """Register a new model descriptor."""
        self._entries[descriptor.model_id] = ModelEntry(
            descriptor=descriptor,
            verified=False,
            status=ModelStatus.REGISTERED,
        )

    def get_entry(self, model_id: str) -> ModelEntry | None:
        """Retrieve the tracking entry for a registered model."""
        return self._entries.get(model_id)

    def verify(self, model_id: str) -> bool:
        """Cryptographically verify model weight file against registered sha256."""
        entry = self.get_entry(model_id)
        if entry is None:
            return False

        path = Path(entry.descriptor.cache_path)
        if not path.is_file():
            entry.verified = False
            entry.status = ModelStatus.FAILED
            return False

        try:
            hasher = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            computed_sha = hasher.hexdigest()

            if computed_sha == entry.descriptor.weights_sha256:
                entry.verified = True
                entry.status = ModelStatus.CACHED
                return True
            else:
                entry.verified = False
                entry.status = ModelStatus.FAILED
                return False
        except OSError:
            entry.verified = False
            entry.status = ModelStatus.FAILED
            return False

    def load(self, model_id: str) -> ModelDescriptor:
        """Mark model loaded in memory after verifying integrity."""
        entry = self.get_entry(model_id)
        if entry is None:
            raise KeyError(f"model {model_id!r} is not registered")

        if not entry.verified:
            raise ModelIntegrityError(f"model {model_id!r} has not been verified or failed verification")

        entry.status = ModelStatus.LOADED
        self._loaded[model_id] = entry.descriptor
        return entry.descriptor

    def unload(self, model_id: str) -> None:
        """Unload model from active residency."""
        if model_id in self._loaded:
            del self._loaded[model_id]
        entry = self.get_entry(model_id)
        if entry is not None:
            entry.status = ModelStatus.CACHED

    def registered_vram_mb(self) -> int:
        """Return total VRAM consumed by currently loaded models."""
        return sum(d.vram_mb for d in self._loaded.values())

    def loaded_models(self) -> list[ModelDescriptor]:
        """Return list of all currently loaded model descriptors."""
        return list(self._loaded.values())


__all__ = [
    "ModelDescriptor",
    "ModelEntry",
    "ModelIntegrityError",
    "ModelKind",
    "ModelManager",
    "ModelStatus",
]
