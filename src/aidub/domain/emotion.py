"""
Continuous Multimodal Emotion Domain Model.

Uses continuous Valence-Arousal-Dominance (VAD) representation to map nuanced performance
without locking into discrete emotion categories. Distinguishes:
  - SourceEmotionObservation (detected from original actor)
  - TargetPerformanceIntent (requested by director)
  - ActualSynthesisParameters (mapped by TTS engine)
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class EmotionObservation(ContractModel):
    """Continuous 3D VAD Emotion Observation."""

    dominant_category: str = Field(default="neutral", max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1.0 (unpleasant) to +1.0 (pleasant)
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1.0 (calm) to +1.0 (excited)
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1.0 (submissive) to +1.0 (dominant)
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
    actual_parameters: dict[str, float] = Field(
        default_factory=dict
    )  # "pitch_scale", "speed_scale", "exaggeration"


__all__ = [
    "EmotionObservation",
    "PerformanceEmotionState",
]
