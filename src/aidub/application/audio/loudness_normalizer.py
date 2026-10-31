"""Loudness normalization utility (peak/RMS based)."""
from __future__ import annotations

import math

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class LoudnessNormalizer:
    @staticmethod
    def normalize_peak(clip: AudioClipData, target_peak_dbfs: float = -1.0) -> AudioClipData:
        if clip.samples.size == 0:
            return clip
        peak = float(np.max(np.abs(clip.samples)))
        if peak < 1e-9:
            return clip
        target = 10.0 ** (target_peak_dbfs / 20.0)
        scale = target / peak
        out = np.clip(clip.samples * scale, -1.0, 1.0).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)

    @staticmethod
    def normalize_rms(clip: AudioClipData, target_rms_dbfs: float = -20.0) -> AudioClipData:
        if clip.samples.size == 0:
            return clip
        rms = float(np.sqrt(np.mean(clip.samples ** 2)))
        if rms < 1e-9:
            return clip
        target = 10.0 ** (target_rms_dbfs / 20.0)
        scale = target / rms
        out = np.clip(clip.samples * scale, -1.0, 1.0).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)

    @staticmethod
    def current_peak_dbfs(clip: AudioClipData) -> float:
        if clip.samples.size == 0:
            return -120.0
        peak = float(np.max(np.abs(clip.samples)))
        if peak < 1e-9:
            return -120.0
        return 20.0 * math.log10(peak)


__all__ = ["LoudnessNormalizer"]
