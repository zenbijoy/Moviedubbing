"""
High-density audio waveform downsampling & peak rendering data provider.

Generates normalized min/max peak arrays per pixel for 60 FPS multitrack timeline rendering.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel


class WaveformPeakData(ContractModel):
    """Downsampled waveform rendering peaks for a single audio clip."""

    clip_id: str
    sample_rate: int = Field(default=48_000, ge=8_000)
    duration_ms: int = Field(ge=0)
    min_peaks: list[float] = Field(default_factory=list)  # Normalized [-1.0, 0.0]
    max_peaks: list[float] = Field(default_factory=list)  # Normalized [0.0, 1.0]


class WaveformGenerator:
    """
    Computes waveform display peaks from raw audio samples.
    """

    @staticmethod
    def downsample_audio(
        clip_id: str,
        audio_samples: Sequence[float],
        sample_rate: int,
        target_peaks: int = 400,
    ) -> WaveformPeakData:
        """
        Downsample raw float audio samples into target_peaks min/max pairs.
        """
        if not audio_samples:
            return WaveformPeakData(clip_id=clip_id, sample_rate=sample_rate, duration_ms=0)

        total_samples = len(audio_samples)
        duration_ms = int((total_samples / sample_rate) * 1000.0)
        chunk_size = max(1, total_samples // target_peaks)

        min_peaks: list[float] = []
        max_peaks: list[float] = []

        for i in range(0, total_samples, chunk_size):
            chunk = audio_samples[i : i + chunk_size]
            min_peaks.append(round(max(-1.0, min(chunk)), 3))
            max_peaks.append(round(min(1.0, max(chunk)), 3))

        return WaveformPeakData(
            clip_id=clip_id,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
            min_peaks=min_peaks,
            max_peaks=max_peaks,
        )


__all__ = [
    "WaveformGenerator",
    "WaveformPeakData",
]
