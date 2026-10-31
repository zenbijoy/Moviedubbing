"""Non-destructive fade application service for audio clips."""
from __future__ import annotations

import math

import numpy as np

from aidub.domain.audio_edit import FadeSpec, FadeType
from aidub.media.pro_audio_editor import AudioClipData


class FadeEngine:
    """Applies fade-in / fade-out envelopes to AudioClipData."""

    def apply_fade(self, clip: AudioClipData, fade: FadeSpec) -> AudioClipData:
        if clip.samples.size == 0:
            return clip

        samples = clip.samples.astype(np.float32).copy()
        sr = clip.sample_rate
        fade_samples = max(1, int(fade.duration_s * sr))
        fade_samples = min(fade_samples, samples.size)

        if fade.fade_type == FadeType.LINEAR:
            ramp = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        elif fade.fade_type == FadeType.S_CURVE:
            x = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            ramp = (1.0 - np.cos(x * math.pi)) / 2.0
            ramp = ramp.astype(np.float32)
        elif fade.fade_type == FadeType.EXPONENTIAL:
            x = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            ramp = x ** 2
            ramp = ramp.astype(np.float32)
        elif fade.fade_type == FadeType.LOGARITHMIC:
            x = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            ramp = np.sqrt(np.clip(x, 0.0, 1.0)).astype(np.float32)
        else:
            ramp = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)

        if fade.is_fade_in:
            envelope = np.ones(samples.size, dtype=np.float32)
            envelope[:fade_samples] = ramp
        else:
            envelope = np.ones(samples.size, dtype=np.float32)
            envelope[-fade_samples:] = ramp[::-1]

        processed = np.clip(samples * envelope, -1.0, 1.0).astype(np.float32)
        return AudioClipData(samples=processed, sample_rate=sr)

    def apply_fades(self, clip: AudioClipData, fades: list[FadeSpec]) -> AudioClipData:
        current = clip
        for f in fades:
            current = self.apply_fade(current, f)
        return current


__all__ = ["FadeEngine"]
