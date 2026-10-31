"""
Organic human breath synthesis and dialogue pause insertion engine.
Generates acoustic vocal tract air turbulence with physiological inhalation envelopes.
"""
from __future__ import annotations

import math
import numpy as np
from scipy import signal

from aidub.media.pro_audio_editor import AudioClipData


class BreathInsertionEngine:
    """
    Organic vocal breath synthesis and dialogue insertion engine.
    Replaces sterile TTS dead air with physiological vocal tract inhalation acoustics.
    """

    @classmethod
    def synthesize_breath(
        cls,
        duration_s: float = 0.25,
        sample_rate: int = 44100,
        breath_amp: float = 0.05,
        seed: int = 42,
    ) -> np.ndarray:
        """
        Synthesizes an organic human breath intake.
        Filters pink/turbulent noise through vocal tract glottal/pharyngeal formants (~1.6kHz & 2.5kHz)
        and applies an asymmetric human inhalation envelope.
        """
        n = max(8, int(duration_s * sample_rate))
        rng = np.random.default_rng(seed)

        # 1. Base turbulence (pinkish noise via 1st-order integration)
        white = rng.standard_normal(n).astype(np.float32)
        # 1-pole lowpass filter to produce pink acoustic spectrum
        b_pink = [0.15]
        a_pink = [1.0, -0.85]
        pink = signal.lfilter(b_pink, a_pink, white).astype(np.float32)

        # 2. Resonant bandpass filter modeling pharyngeal/glottal cavity (1.2 kHz - 2.8 kHz)
        nyq = sample_rate / 2.0
        low = min(0.9, 1000.0 / nyq)
        high = min(0.95, 3200.0 / nyq)

        if high > low and low > 0.0:
            try:
                sos = signal.butter(2, [low, high], btype="bandpass", output="sos")
                filtered = signal.sosfilt(sos, pink)
            except Exception:
                filtered = pink
        else:
            filtered = pink

        # Normalize energy
        std = float(np.std(filtered)) if filtered.size else 1.0
        if std > 1e-6:
            filtered = (filtered / std) * breath_amp

        # 3. Asymmetric inhalation envelope:
        # Attack ~25% (inhale starts), Sustain ~50% (main intake), Release ~25% (glottal seal)
        att_len = max(2, int(0.25 * n))
        rel_len = max(2, int(0.25 * n))
        sus_len = max(1, n - att_len - rel_len)

        att = (0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, att_len)))).astype(np.float32)
        sus = np.ones(sus_len, dtype=np.float32)
        rel = (0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, rel_len)))).astype(np.float32)
        env = np.concatenate([att, sus, rel])[:n]

        return (filtered * env).astype(np.float32)

    @classmethod
    def insert_breath(
        cls,
        clip: AudioClipData,
        breath_duration_s: float = 0.25,
        breath_amp: float = 0.05,
    ) -> AudioClipData:
        """Appends an organic breath to the tail of the audio clip."""
        if clip.samples.size == 0:
            return clip
        breath = cls.synthesize_breath(
            duration_s=breath_duration_s,
            sample_rate=clip.sample_rate,
            breath_amp=breath_amp,
        )
        out = np.concatenate([clip.samples, breath]).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)

    @classmethod
    def insert_breath_before(
        cls,
        clip: AudioClipData,
        breath_duration_s: float = 0.25,
        breath_amp: float = 0.05,
    ) -> AudioClipData:
        """Prepends a natural preparatory breath intake before dialogue begins."""
        if clip.samples.size == 0:
            return clip
        breath = cls.synthesize_breath(
            duration_s=breath_duration_s,
            sample_rate=clip.sample_rate,
            breath_amp=breath_amp,
        )
        out = np.concatenate([breath, clip.samples]).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)

    @staticmethod
    def insert_silence(clip: AudioClipData, silence_s: float) -> AudioClipData:
        """Inserts true digital silence padding."""
        n = max(0, int(silence_s * clip.sample_rate))
        sil = np.zeros(n, dtype=np.float32)
        out = np.concatenate([clip.samples, sil]).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)


__all__ = ["BreathInsertionEngine"]
