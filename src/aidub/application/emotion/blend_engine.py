"""Emotion blending: mix multiple emotion PAD vectors."""
from __future__ import annotations

from aidub.application.voice.pro_emotion_engine import PADVector, MicroInflections


class EmotionBlendEngine:
    @staticmethod
    def blend_pads(pads: list[PADVector], weights: list[float] | None = None) -> PADVector:
        if not pads:
            return PADVector()
        if weights is None:
            weights = [1.0] * len(pads)
        total = sum(weights) or 1.0
        v = sum(p.valence * w for p, w in zip(pads, weights)) / total
        a = sum(p.arousal * w for p, w in zip(pads, weights)) / total
        d = sum(p.dominance * w for p, w in zip(pads, weights)) / total
        return PADVector(valence=v, arousal=a, dominance=d).clamped()

    @staticmethod
    def blend_micro(micros: list[MicroInflections], weights: list[float] | None = None) -> MicroInflections:
        if not micros:
            return MicroInflections()
        if weights is None:
            weights = [1.0] * len(micros)
        total = sum(weights) or 1.0
        return MicroInflections(
            tremble_pct=sum(m.tremble_pct * w for m, w in zip(micros, weights)) / total,
            breathiness_pct=sum(m.breathiness_pct * w for m, w in zip(micros, weights)) / total,
            vocal_fry_pct=sum(m.vocal_fry_pct * w for m, w in zip(micros, weights)) / total,
            throat_tension_pct=sum(m.throat_tension_pct * w for m, w in zip(micros, weights)) / total,
        ).clamped()


__all__ = ["EmotionBlendEngine"]
