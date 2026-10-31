"""
Voice age transformation: child/young/elderly acoustic morphing.
Transforms fundamental pitch, vocal tract formant ratio, and speech cadence.
"""
from __future__ import annotations

import numpy as np

from aidub.application.voice.formant_shifter import FormantShifter
from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine


class VoiceAgeTransformer:
    """
    Transforms vocal age by modulating fundamental pitch, formant resonance, and speech rate.
    """

    PRESETS = {
        "child": {"pitch_shift_semitones": 7.0, "rate_multiplier": 1.1, "formant_ratio": 1.15},
        "young_adult": {"pitch_shift_semitones": 0.0, "rate_multiplier": 1.0, "formant_ratio": 1.0},
        "elderly": {"pitch_shift_semitones": -3.0, "rate_multiplier": 0.9, "formant_ratio": 0.9},
    }

    @classmethod
    def get(cls, age_group: str) -> dict[str, float]:
        return dict(cls.PRESETS.get(age_group, cls.PRESETS["young_adult"]))

    @classmethod
    def list_groups(cls) -> list[str]:
        return list(cls.PRESETS.keys())

    @classmethod
    def transform(cls, clip: AudioClipData, age_group: str) -> AudioClipData:
        """Applies age-specific acoustic transformations to dialogue speech."""
        if clip.samples.size == 0:
            return clip

        preset = cls.get(age_group)
        pitch_semitones = float(preset.get("pitch_shift_semitones", 0.0))
        formant_ratio = float(preset.get("formant_ratio", 1.0))
        rate_mult = float(preset.get("rate_multiplier", 1.0))
        sr = clip.sample_rate

        current = clip.clone()

        # 1. Pitch shift
        if abs(pitch_semitones) > 0.05 and current.samples.size >= 256:
            pitch_factor = 2.0 ** (pitch_semitones / 12.0)
            orig_len = current.samples.size
            stretched_len = max(16, int(orig_len / pitch_factor))
            indices = np.linspace(0, orig_len - 1, stretched_len)
            resampled = np.interp(indices, np.arange(orig_len), current.samples).astype(np.float32)
            restored = ProAudioDspEngine.time_stretch(resampled, sr, float(orig_len / stretched_len))
            if restored.size != orig_len:
                restored = np.resize(restored, orig_len)
            current = AudioClipData(samples=restored, sample_rate=sr)

        # 2. Formant shift (vocal tract length scaling)
        if abs(formant_ratio - 1.0) > 0.02:
            current = FormantShifter.shift(current, formant_ratio=formant_ratio)

        # 3. Speech rate modulation via WSOLA
        if abs(rate_mult - 1.0) > 0.02 and current.samples.size >= 512:
            stretched = ProAudioDspEngine.time_stretch(current.samples, sr, rate_mult)
            current = AudioClipData(samples=stretched, sample_rate=sr)

        return current


__all__ = ["VoiceAgeTransformer"]
