"""Emotion transfer: apply reference emotion to target synthesis params."""
from __future__ import annotations

from aidub.application.voice.pro_emotion_engine import PADVector, MicroInflections


class EmotionTransferEngine:
    @staticmethod
    def transfer(ref_pad: PADVector, ref_micro: MicroInflections, base_pitch: float = 0.0) -> dict:
        # map PAD to synthesis controls
        pitch_shift = base_pitch + ref_pad.valence * 2.0 + ref_pad.arousal * 1.5
        rate = 1.0 + ref_pad.arousal * 0.3 - (1.0 - ref_pad.dominance) * 0.1
        volume = 0.8 + ref_pad.arousal * 0.4
        return {
            "pitch_shift_semitones": round(pitch_shift, 2),
            "rate_multiplier": round(rate, 3),
            "volume": round(min(1.5, volume), 3),
            "pad": ref_pad.to_dict(),
            "micro": {
                "tremble_pct": ref_micro.tremble_pct,
                "breathiness_pct": ref_micro.breathiness_pct,
                "vocal_fry_pct": ref_micro.vocal_fry_pct,
                "throat_tension_pct": ref_micro.throat_tension_pct,
            },
        }


__all__ = ["EmotionTransferEngine"]
