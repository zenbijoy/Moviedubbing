"""Beat sync: detect beat positions via energy peaks."""
from __future__ import annotations

import numpy as np


class BeatSync:
    @staticmethod
    def detect_beats(samples: np.ndarray, sr: int, hop: int = 512) -> list[float]:
        if samples.size == 0:
            return []
        # onset via frame energy difference
        frames = []
        for i in range(0, samples.size - hop, hop):
            chunk = samples[i:i + hop]
            frames.append(float(np.sqrt(np.mean(chunk ** 2))))
        frames = np.array(frames)
        diff = np.diff(frames)
        # peaks in diff
        thr = np.mean(diff) + 1.5 * np.std(diff)
        peaks = np.where(diff > thr)[0]
        times = [p * hop / sr for p in peaks]
        return times

    @staticmethod
    def snap_to_beat(t: float, beats: list[float]) -> float:
        if not beats:
            return t
        idx = min(range(len(beats)), key=lambda i: abs(beats[i] - t))
        return beats[idx]


__all__ = ["BeatSync"]
