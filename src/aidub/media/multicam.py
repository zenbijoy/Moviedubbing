"""
Multicam Editing & Nested Sequence Engine.

Provides multicam angle synchronization, nested timeline sequences, and adjustment layers.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class MulticamSyncUnavailableError(RuntimeError):
    """Raised because no audio waveform synchronizer is configured."""


class MulticamAngle(ContractModel):
    """Multicam camera angle descriptor."""

    angle_id: Identifier
    camera_label: str = Field(min_length=1)
    media_path: str = Field(min_length=1)


class MulticamEngine:
    """
    Multicam angle sync and switching engine.
    """

    def sync_camera_angles(self, angles: Sequence[MulticamAngle]) -> dict[str, int]:
        """
        Reject synchronization when only angle descriptors, without audio, are supplied.
        """
        del angles
        raise MulticamSyncUnavailableError(
            "Multicam synchronization is unavailable: no audio waveform alignment backend is "
            "configured. No zero-offset sync result was generated."
        )


__all__ = [
    "MulticamAngle",
    "MulticamEngine",
    "MulticamSyncUnavailableError",
]
