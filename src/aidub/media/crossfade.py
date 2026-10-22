"""
Automated crossfade & fade in/out curve calculation engine.

Curves supported:
  - LINEAR: Equal rate transition
  - EQUAL_POWER (3dB): Constant energy preservation (standard for audio crossfades)
  - EQUAL_GAIN (6dB): Constant amplitude sum (correlated signals)
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel


class FadeCurveShape(StrEnum):
    LINEAR = "linear"
    EQUAL_POWER = "equal_power"  # 3dB drop at center (constant energy)
    EQUAL_GAIN = "equal_gain"  # 6dB drop at center (constant amplitude)


class ClipFadeSettings(ContractModel):
    """Fade-in and Fade-out settings for a single audio clip."""

    clip_id: str
    fade_in_ms: int = Field(default=0, ge=0)
    fade_out_ms: int = Field(default=0, ge=0)
    curve_shape: FadeCurveShape = FadeCurveShape.EQUAL_POWER


class CrossfadeRegion(ContractModel):
    """Calculated crossfade region between two adjacent/overlapping audio clips."""

    left_clip_id: str
    right_clip_id: str
    overlap_start_ms: int = Field(ge=0)
    overlap_duration_ms: int = Field(ge=1)
    curve_shape: FadeCurveShape = FadeCurveShape.EQUAL_POWER


class CrossfadeCalculator:
    """
    Computes sample gain envelopes for audio clip fade-ins, fade-outs, and crossfades.
    """

    @staticmethod
    def calculate_gain(
        progress: float, shape: FadeCurveShape = FadeCurveShape.EQUAL_POWER
    ) -> tuple[float, float]:
        """
        Calculate (fade_out_gain, fade_in_gain) at normalized progress t in [0.0, 1.0].
        """
        t = max(0.0, min(1.0, progress))

        if shape == FadeCurveShape.LINEAR:
            return (1.0 - t, t)

        if shape == FadeCurveShape.EQUAL_GAIN:
            # 6dB drop at center: linear sum = 1.0
            return (1.0 - t, t)

        # Default EQUAL_POWER (3dB drop at center: sum of squares = 1.0)
        out_gain = math.cos(t * math.pi * 0.5)
        in_gain = math.sin(t * math.pi * 0.5)
        return (round(out_gain, 4), round(in_gain, 4))

    @staticmethod
    def detect_crossfade(
        left_clip_start_ms: int,
        left_clip_dur_ms: int,
        right_clip_start_ms: int,
        right_clip_dur_ms: int,
        left_id: str,
        right_id: str,
    ) -> CrossfadeRegion | None:
        """
        Detect if two clips on the same track overlap and create a crossfade region.
        """
        left_end = left_clip_start_ms + left_clip_dur_ms
        if right_clip_start_ms < left_end and right_clip_start_ms > left_clip_start_ms:
            overlap_ms = left_end - right_clip_start_ms
            return CrossfadeRegion(
                left_clip_id=left_id,
                right_clip_id=right_id,
                overlap_start_ms=right_clip_start_ms,
                overlap_duration_ms=overlap_ms,
            )
        return None


__all__ = [
    "ClipFadeSettings",
    "CrossfadeCalculator",
    "CrossfadeRegion",
    "FadeCurveShape",
]
