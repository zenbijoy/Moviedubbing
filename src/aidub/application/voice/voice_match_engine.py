"""Voice matching utilities to align TTS voice to a reference actor."""
from __future__ import annotations

import math


class VoiceMatchEngine:
    @staticmethod
    def semitone_difference(ref_freq_hz: float, target_freq_hz: float) -> float:
        if ref_freq_hz <= 0 or target_freq_hz <= 0:
            return 0.0
        return 12.0 * math.log2(target_freq_hz / ref_freq_hz)

    @staticmethod
    def match_params(ref_pitch_hz: float, ref_rate: float, tgt_pitch_hz: float, tgt_rate: float) -> dict[str, float]:
        pitch_shift = VoiceMatchEngine.semitone_difference(ref_pitch_hz, tgt_pitch_hz)
        rate_factor = tgt_rate / max(1e-6, ref_rate)
        return {"pitch_shift_semitones": round(pitch_shift, 2), "rate_multiplier": round(rate_factor, 3)}

    @staticmethod
    def blend_params(a: dict[str, float], b: dict[str, float], ratio: float) -> dict[str, float]:
        ratio = max(0.0, min(1.0, ratio))
        out = {}
        for k in set(a) | set(b):
            va = a.get(k, 0.0)
            vb = b.get(k, 0.0)
            out[k] = va * (1 - ratio) + vb * ratio
        return out


__all__ = ["VoiceMatchEngine"]
