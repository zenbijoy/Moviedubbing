"""
Model-Agnostic Opaque Speaker Embedding Domain Model.

Does NOT hardcode embedding dimensions (e.g. 512, 192, 256).
Treats speaker embeddings as opaque vectors with model metadata,
allowing seamless model swapping (SpeechBrain ECAPA, PyAnnote, WeSpeaker) without schema breakages.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class SpeakerEmbedding(ContractModel):
    """Model-agnostic opaque speaker embedding container."""

    embedding_id: Identifier
    model_id: str = Field(
        min_length=1
    )  # e.g. "speechbrain/spkrec-ecapa-voxceleb" or "pyannote/embedding"
    model_version: str = Field(default="1.0.0", min_length=1)
    dimension: int = Field(gt=0)  # e.g. 192, 256, 512
    vector: list[float] = Field(min_length=1)  # Serialized float array
    normalized: bool = True
    source_artifact_id: Identifier
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)

    def to_numpy(self) -> np.ndarray:
        """Convert vector float list to numpy array."""
        arr = np.array(self.vector, dtype=np.float32)
        if self.normalized and np.linalg.norm(arr) > 0:
            arr = arr / np.linalg.norm(arr)
        return arr

    def compute_cosine_similarity(self, other: SpeakerEmbedding) -> float:
        """Calculate cosine similarity with another speaker embedding."""
        if self.dimension != other.dimension:
            raise ValueError(
                f"cannot compare embeddings with mismatching dimensions ({self.dimension} vs {other.dimension})"
            )
        vec_a = self.to_numpy()
        vec_b = other.to_numpy()
        dot = float(np.dot(vec_a, vec_b))
        return round(max(-1.0, min(1.0, dot)), 4)


__all__ = [
    "SpeakerEmbedding",
]
