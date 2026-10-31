"""Reverb matcher: estimate RT60 and suggest decay."""
from __future__ import annotations

import numpy as np


class ReverbMatcher:
    @staticmethod
    def estimate_rt60(samples: np.ndarray, sr: int) -> float:
        if samples.size == 0:
            return 0.0
        # Schroeder backward integration
        sq = samples.astype(np.float64) ** 2
        energy = np.cumsum(sq[::-1])[::-1]
        if energy[0] <= 0:
            return 0.0
        energy_db = 10 * np.log10(energy / energy[0] + 1e-12)
        # find -60 dB point
        idx = np.where(energy_db <= -60)[0]
        if idx.size == 0:
            return 0.0
        return float(idx[0] / sr)

    @staticmethod
    def suggested_decay(rt60: float) -> float:
        return max(0.1, min(5.0, rt60))


__all__ = ["ReverbMatcher"]
