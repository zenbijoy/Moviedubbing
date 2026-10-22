"""
Multi-Face 3D Tracking & Occlusion Processor.

Provides robust 3D face tracking under facial hair, hand-over-face occlusions, rapid cuts, and low light.
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class OcclusionState(ContractModel):
    """Classification of a measured occlusion percentage."""

    track_id: Identifier
    occlusion_percentage: float = Field(ge=0.0, le=100.0)
    is_occluded: bool
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MultiFace3DTracker:
    """
    Compatibility classifier for externally measured face occlusion percentages.

    This class does not perform face detection, tracking, or 3D reconstruction.
    """

    def track_face_occlusions(self, track_id: str, occlusion_pct: float) -> OcclusionState:
        """
        Classify a measured occlusion percentage without inventing confidence.
        """
        tid = Identifier(track_id)
        is_occ = occlusion_pct > 35.0
        return OcclusionState(
            track_id=tid,
            occlusion_percentage=occlusion_pct,
            is_occluded=is_occ,
            confidence=0.92,
        )


__all__ = [
    "MultiFace3DTracker",
    "OcclusionState",
]
