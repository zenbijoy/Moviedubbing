"""
CapCut & DaVinci Resolve style speed ramp and time-stretch engine.
Supports both WSOLA pitch-preserving dialogue stretch and dynamic acceleration ramping.
"""
from __future__ import annotations

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine


class SpeedRamp:
    """
    Time-stretch and speed ramping engine.
    Supports constant rate stretch (with optional pitch preservation) and dynamic speed ramping.
    """

    @classmethod
    def stretch(
        cls,
        clip: AudioClipData,
        speed: float,
        preserve_pitch: bool = False,
    ) -> AudioClipData:
        """
        Stretches or compresses audio clip duration by speed factor.
        speed > 1.0 accelerates (shortens duration); speed < 1.0 decelerates (lengthens duration).
        `preserve_pitch`: if True, maintains original pitch using WSOLA.
        """
        if clip.samples.size == 0 or speed <= 0:
            return clip
        if abs(speed - 1.0) < 1e-6:
            return clip.clone()

        sr = clip.sample_rate
        new_len = max(1, int(round(clip.samples.size / speed)))

        if preserve_pitch and clip.samples.size >= 512:
            # WSOLA pitch-preserving stretch (tempo_factor is inverse of speed)
            tempo_factor = float(speed)
            stretched = ProAudioDspEngine.time_stretch(clip.samples, sr, tempo_factor)
            return AudioClipData(samples=stretched, sample_rate=sr)

        # High-quality linear interpolation resampling
        orig_indices = np.linspace(0.0, float(clip.samples.size - 1), new_len, dtype=np.float32)
        out = np.interp(orig_indices, np.arange(clip.samples.size), clip.samples).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=sr)

    @classmethod
    def ramp(
        cls,
        clip: AudioClipData,
        start_speed: float = 1.0,
        end_speed: float = 2.0,
        curve: str = "linear",
    ) -> AudioClipData:
        """
        Dynamically ramps speed across the clip (e.g. from 1.0x to 2.5x).
        Supports 'linear' and 's_curve' acceleration curves.
        """
        if clip.samples.size == 0:
            return clip
        start_speed = max(0.2, min(5.0, start_speed))
        end_speed = max(0.2, min(5.0, end_speed))

        n_in = clip.samples.size
        # Mean speed determines total duration
        avg_speed = (start_speed + end_speed) / 2.0
        n_out = max(2, int(round(n_in / avg_speed)))

        t = np.linspace(0.0, 1.0, n_out, dtype=np.float32)
        if curve == "s_curve":
            # Smooth cosine acceleration curve
            progress = (1.0 - np.cos(t * np.pi)) / 2.0
        else:
            progress = t

        # Instantaneous speed curve
        speed_curve = start_speed + (end_speed - start_speed) * progress
        # Integrate speed to find sampling position in source audio
        dt = 1.0 / n_out
        cum_time = np.cumsum(speed_curve) * (n_in / float(np.sum(speed_curve)))
        cum_time = np.clip(cum_time, 0.0, float(n_in - 1))

        out = np.interp(cum_time, np.arange(n_in), clip.samples).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=clip.sample_rate)


__all__ = ["SpeedRamp"]
