"""
Continuous Multimodal Emotion and Prosody Domain Models.

Uses continuous Valence-Arousal-Dominance (PAD/VAD) representation to map nuanced performance
without locking into discrete emotion categories. Distinguishes:
  - SourceEmotionObservation (detected from original actor via Emotion2Vec+)
  - TargetPerformanceIntent / EmotionSpec (requested by director)
  - EmotionCurve / Keyframe trajectory across utterance time
  - VocalizationMarker (sighs, gasps, breaths, chuckles)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class VocalizationMarkerType(StrEnum):
    BREATH = "breath"
    GASP = "gasp"
    SIGH = "sigh"
    CHUCKLE = "chuckle"
    GROAN = "groan"
    PAUSE = "pause"


@dataclass
class VocalizationMarker:
    """Non-speech vocalization anchor inserted into dialogue."""

    marker_type: VocalizationMarkerType
    timestamp_s: float
    level_db: float = -6.0
    duration_s: float = 0.25
    marker_id: str = field(default_factory=lambda: f"voc_{uuid4().hex[:8]}")


@dataclass
class EmotionSpec:
    """Holistic directorial emotion specification."""

    primary_category: str = "Neutral"  # Neutral, Angry, Joy, Sorrow, Fear, Whisper, Heroic, Shout
    intensity: float = 1.0  # 0.0 to 2.0 (100% is standard)
    valence: float = 0.0  # -1.0 to +1.0
    arousal: float = 0.35  # 0.0 to +1.0
    dominance: float = 0.0  # -1.0 to +1.0
    breathiness: float = 0.0  # 0.0 to 1.0
    tremble: float = 0.0  # 0.0 to 1.0
    throat_tension: float = 0.0  # 0.0 to 1.0
    vocal_fry: float = 0.0  # 0.0 to 1.0
    markers: list[VocalizationMarker] = field(default_factory=list)


@dataclass
class EmotionKeyframe:
    """Single point in an emotion time trajectory."""

    time_s: float
    valence: float
    arousal: float
    dominance: float
    intensity: float = 1.0


@dataclass
class EmotionCurve:
    """Continuous multi-keyframe emotion trajectory across utterance duration."""

    utterance_id: str
    duration_s: float
    keyframes: list[EmotionKeyframe] = field(default_factory=list)

    def sample_at(self, time_s: float) -> tuple[float, float, float, float]:
        """Interpolates (valence, arousal, dominance, intensity) at time_s."""
        if not self.keyframes:
            return (0.0, 0.35, 0.0, 1.0)
        if len(self.keyframes) == 1 or time_s <= self.keyframes[0].time_s:
            k = self.keyframes[0]
            return (k.valence, k.arousal, k.dominance, k.intensity)
        if time_s >= self.keyframes[-1].time_s:
            k = self.keyframes[-1]
            return (k.valence, k.arousal, k.dominance, k.intensity)

        # Linear interpolation between adjacent keyframes
        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i + 1]
            if k1.time_s <= time_s <= k2.time_s:
                dt = max(1e-4, k2.time_s - k1.time_s)
                alpha = (time_s - k1.time_s) / dt
                v = k1.valence + alpha * (k2.valence - k1.valence)
                a = k1.arousal + alpha * (k2.arousal - k1.arousal)
                d = k1.dominance + alpha * (k2.dominance - k1.dominance)
                intensity = k1.intensity + alpha * (k2.intensity - k1.intensity)
                return (v, a, d, intensity)

        k = self.keyframes[-1]
        return (k.valence, k.arousal, k.dominance, k.intensity)


class EmotionObservation(ContractModel):
    """Continuous 3D VAD Emotion Observation."""

    dominant_category: str = Field(default="neutral", max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    secondary_emotions: dict[str, float] = Field(default_factory=dict)

    def to_ui_label(self) -> str:
        """Map continuous VAD space to UI category label."""
        if self.intensity < 0.2:
            return "Neutral"
        if self.valence > 0.3 and self.arousal > 0.3:
            return "Joy / Excited"
        if self.valence < -0.3 and self.arousal > 0.3 and self.dominance > 0.2:
            return "Anger / Frustration"
        if self.valence < -0.3 and self.arousal > 0.3 and self.dominance <= 0.2:
            return "Fear / Anxious"
        if self.valence < -0.3 and self.arousal < -0.2:
            return "Sadness / Dramatic"
        if self.arousal > 0.4:
            return "High Intensity / Suspense"
        return "Neutral"


class PerformanceEmotionState(ContractModel):
    """Container holding source, target, and mapped synthesis emotion states."""

    utterance_id: Identifier
    source_observation: EmotionObservation
    target_intent: EmotionObservation
    actual_parameters: dict[str, float] = Field(default_factory=dict)


__all__ = [
    "EmotionCurve",
    "EmotionKeyframe",
    "EmotionObservation",
    "EmotionSpec",
    "PerformanceEmotionState",
    "VocalizationMarker",
    "VocalizationMarkerType",
]
