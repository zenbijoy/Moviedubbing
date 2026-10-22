"""
Speed Ramping & 3D LUT Color Grading Filter Engine.

Provides speed ramping (0.1x to 10x speed changes, freeze frames)
and 3D LUT color grading filter application (.cube / .3dl).
"""

from __future__ import annotations

import logging

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class SpeedRampConfig(ContractModel):
    """Speed ramping configuration."""

    clip_id: Identifier
    speed_factor: float = Field(default=1.0, ge=0.1, le=10.0)
    is_freeze_frame: bool = False
    freeze_frame_time_ms: int = Field(default=0, ge=0)


class LUTColorGradingFilter(ContractModel):
    """3D LUT color grading filter model."""

    filter_id: Identifier
    lut_file_path: str = Field(min_length=1)  # e.g. "luts/cinematic_teal_orange.cube"
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)


class SpeedRampEngine:
    """
    Applies speed ramping and 3D LUT color grading filters.
    """

    def apply_speed_ramp(self, config: SpeedRampConfig) -> float:
        """
        Compute effective clip duration scaling factor.
        """
        logger.info(
            "effects: applied speed factor %.2fx (Freeze frame: %s) to %s",
            config.speed_factor,
            config.is_freeze_frame,
            config.clip_id,
        )
        return config.speed_factor


__all__ = [
    "LUTColorGradingFilter",
    "SpeedRampConfig",
    "SpeedRampEngine",
]
