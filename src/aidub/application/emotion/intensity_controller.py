"""Emotion intensity controller: scale 0-200%."""
from __future__ import annotations

from aidub.application.voice.pro_emotion_engine import PADVector, MicroInflections


class EmotionIntensityController:
    @staticmethod
    def scale_pad(pad: PADVector, intensity: float) -> PADVector:
        intensity = max(0.0, min(2.0, intensity))
        return PADVector(
            valence=pad.valence * intensity,
            arousal=min(1.0, pad.arousal * intensity),
            dominance=pad.dominance * intensity,
        ).clamped()

    @staticmethod
    def scale_micro(micro: MicroInflections, intensity: float) -> MicroInflections:
        intensity = max(0.0, min(2.0, intensity))
        return MicroInflections(
            tremble_pct=micro.tremble_pct * intensity,
            breathiness_pct=micro.breathiness_pct * (0.5 + 0.5 * intensity),
            vocal_fry_pct=micro.vocal_fry_pct * intensity,
            throat_tension_pct=micro.throat_tension_pct * intensity,
        ).clamped()


__all__ = ["EmotionIntensityController"]
