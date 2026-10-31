"""
Domain models for Voice Editing, DSP Chains, and ADR Comping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class FadeType(StrEnum):
    LINEAR = "linear"
    S_CURVE = "s_curve"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"


class DspEffectType(StrEnum):
    PARAMETRIC_EQ = "parametric_eq"
    DE_ESSER = "de_esser"
    LEVELER_LIMITER = "leveler_limiter"
    REVERB_MATCH = "reverb_match"
    PITCH_SHIFT = "pitch_shift"
    TIME_STRETCH = "time_stretch"
    FORMANT_SHIFT = "formant_shift"


@dataclass
class AudioSelection:
    """Sample-accurate selection within an audio clip."""

    start_sample: int
    end_sample: int
    sample_rate: int = 48000
    channel: int = 0  # 0 = mono/left, 1 = right

    @property
    def sample_count(self) -> int:
        return max(0, self.end_sample - self.start_sample)

    @property
    def start_s(self) -> float:
        return self.start_sample / max(1, self.sample_rate)

    @property
    def end_s(self) -> float:
        return self.end_sample / max(1, self.sample_rate)

    @property
    def duration_s(self) -> float:
        return self.sample_count / max(1, self.sample_rate)


@dataclass
class FadeSpec:
    """Fade In or Fade Out specification."""

    duration_s: float
    fade_type: FadeType = FadeType.S_CURVE
    is_fade_in: bool = True


@dataclass
class GainSpec:
    """Gain adjustment or normalization specification."""

    gain_db: float = 0.0
    normalize_peak_dbfs: float | None = None


@dataclass
class DspEffectNode:
    """Single effect in the DSP processing rack."""

    effect_type: DspEffectType
    parameters: dict[str, Any] = field(default_factory=dict)
    bypass: bool = False
    node_id: str = field(default_factory=lambda: f"node_{uuid4().hex[:8]}")


@dataclass
class EffectRack:
    """Ordered rack of DSP effects applied non-destructively to audio."""

    effects: list[DspEffectNode] = field(default_factory=list)
    master_bypass: bool = False

    def add_effect(self, effect_type: DspEffectType, **params: Any) -> DspEffectNode:
        node = DspEffectNode(effect_type=effect_type, parameters=params)
        self.effects.append(node)
        return node

    def get_active_effects(self) -> list[DspEffectNode]:
        if self.master_bypass:
            return []
        return [e for e in self.effects if not e.bypass]


@dataclass
class Take:
    """A single recorded or generated audio take for a dialogue cue."""

    take_id: str
    cue_id: str
    audio_path: str
    duration_s: float
    created_at_s: float
    is_selected: bool = False
    is_comped: bool = False
    loudness_lufs: float = -23.0
    true_peak_dbfs: float = -1.0
    notes: str = ""


@dataclass
class CompingRegion:
    """A crossfaded snippet from a specific take assembled into the master track."""

    take_id: str
    cue_id: str
    start_s: float
    end_s: float
    crossfade_duration_s: float = 0.025  # 25ms crossfade
    gain_db: float = 0.0


__all__ = [
    "AudioSelection",
    "CompingRegion",
    "DspEffectNode",
    "DspEffectType",
    "EffectRack",
    "FadeSpec",
    "FadeType",
    "GainSpec",
    "Take",
]
