"""Bangla emotion presets for dubbing."""
from __future__ import annotations

from aidub.application.voice.pro_emotion_engine import PADVector, MicroInflections


class BanglaEmotionPresets:
    PRESETS = {
        "romantic": (PADVector(0.7, 0.4, 0.2), MicroInflections(breathiness_pct=40.0)),
        "tragic": (PADVector(-0.6, 0.5, -0.3), MicroInflections(tremble_pct=35.0, vocal_fry_pct=20.0)),
        "angry": (PADVector(-0.7, 0.85, 0.7), MicroInflections(throat_tension_pct=60.0)),
        "comedic": (PADVector(0.6, 0.6, 0.1), MicroInflections(breathiness_pct=15.0)),
        "fearful": (PADVector(-0.5, 0.9, -0.7), MicroInflections(tremble_pct=50.0, breathiness_pct=30.0)),
        "heroic": (PADVector(0.3, 0.7, 0.9), MicroInflections(throat_tension_pct=30.0)),
        "neutral": (PADVector(0.0, 0.35, 0.0), MicroInflections()),
    }

    @classmethod
    def list(cls) -> list[str]:
        return list(cls.PRESETS.keys())

    @classmethod
    def get(cls, name: str):
        return cls.PRESETS.get(name, cls.PRESETS["neutral"])


__all__ = ["BanglaEmotionPresets"]
