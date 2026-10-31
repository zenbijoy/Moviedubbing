"""
Cinematic & CapCut-style voice changer presets with real-time DSP transformation.
Applies pitch shifting, formant modification, ring modulation, and acoustics.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np

from aidub.application.voice.formant_shifter import FormantShifter
from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine


class VoiceChanger:
    """
    Transforms speech audio into stylized character voices.
    Provides preset configurations and DSP transformation engines.
    """

    PRESETS: dict[str, dict[str, Any]] = {
        "chipmunk": {"pitch": 7.0, "formant": 1.25, "dsp": "none"},
        "deep": {"pitch": -5.0, "formant": 0.85, "dsp": "warmth"},
        "robot": {"pitch": 0.0, "formant": 1.0, "dsp": "ring_mod"},
        "echo": {"pitch": 0.0, "formant": 1.0, "dsp": "delay"},
        "female": {"pitch": 4.0, "formant": 1.12, "dsp": "none"},
        "male": {"pitch": -3.0, "formant": 0.92, "dsp": "none"},
        "telephone": {"pitch": 0.0, "formant": 1.0, "dsp": "tele"},
        "megaphone": {"pitch": 1.0, "formant": 1.05, "dsp": "megaphone"},
    }

    @classmethod
    def list_presets(cls) -> list[str]:
        return list(cls.PRESETS.keys())

    @classmethod
    def get(cls, name: str) -> dict[str, Any]:
        return dict(cls.PRESETS.get(name, {"pitch": 0.0, "formant": 1.0, "dsp": "none"}))

    @classmethod
    def apply(cls, clip: AudioClipData, preset_name: str) -> AudioClipData:
        """Applies the chosen voice changer preset to the audio clip."""
        if clip.samples.size == 0:
            return clip

        preset = cls.get(preset_name)
        pitch_semitones = float(preset.get("pitch", 0.0))
        formant_ratio = float(preset.get("formant", 1.0))
        dsp_mode = str(preset.get("dsp", "none"))
        sr = clip.sample_rate

        current = clip.clone()

        # 1. Pitch shift (if configured)
        if abs(pitch_semitones) > 0.05 and current.samples.size >= 256:
            pitch_factor = 2.0 ** (pitch_semitones / 12.0)
            orig_len = current.samples.size
            stretched_len = max(16, int(orig_len / pitch_factor))
            indices = np.linspace(0, orig_len - 1, stretched_len)
            resampled = np.interp(indices, np.arange(orig_len), current.samples).astype(np.float32)
            # WSOLA time stretch back to original duration
            restored = ProAudioDspEngine.time_stretch(resampled, sr, float(orig_len / stretched_len))
            if restored.size != orig_len:
                restored = np.resize(restored, orig_len)
            current = AudioClipData(samples=restored, sample_rate=sr)

        # 2. Formant shift (vocal tract length scaling)
        if abs(formant_ratio - 1.0) > 0.02:
            current = FormantShifter.shift(current, formant_ratio=formant_ratio)

        # 3. DSP Special Effects
        samples = current.samples.astype(np.float32)

        if dsp_mode == "ring_mod":
            # Robotic ring modulation carrier at 50 Hz
            t = np.arange(samples.size) / sr
            carrier = np.sin(2 * np.pi * 50.0 * t).astype(np.float32)
            samples = 0.5 * samples + 0.5 * (samples * carrier)

        elif dsp_mode == "delay":
            # Cinematic slapback echo (160ms delay, 35% feedback)
            delay_samples = int(sr * 0.16)
            echoed = np.zeros_like(samples)
            if delay_samples < samples.size:
                echoed[delay_samples:] = samples[:-delay_samples] * 0.38
            samples = np.clip(samples + echoed, -1.0, 1.0)

        elif dsp_mode == "tele":
            # Bandpass telephone filter (400 Hz - 3200 Hz) + drive
            samples = ProAudioDspEngine.apply_eq_4band(
                samples, sr, low_mid_gain_db=-18.0, high_mid_gain_db=4.0, air_gain_db=-24.0
            )
            samples = np.tanh(samples * 1.5).astype(np.float32)

        elif dsp_mode == "megaphone":
            # Resonant mid-range honk (1.5 kHz - 2.5 kHz) + aggressive clipping
            samples = ProAudioDspEngine.apply_eq_4band(
                samples, sr, low_mid_gain_db=-12.0, high_mid_gain_db=8.0, air_gain_db=-18.0
            )
            samples = np.clip(samples * 2.2, -0.9, 0.9).astype(np.float32)

        elif dsp_mode == "warmth":
            # Soft tube saturation for deep authority
            samples = np.tanh(samples * 1.35) / 1.15

        return AudioClipData(samples=np.clip(samples, -1.0, 1.0).astype(np.float32), sample_rate=sr)


__all__ = ["VoiceChanger"]
