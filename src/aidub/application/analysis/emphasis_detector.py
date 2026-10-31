"""Detect emphasized words in a transcript based on audio energy."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Emphasis:
    word: str
    start_s: float
    end_s: float
    energy_db: float
    emphasized: bool


class EmphasisDetector:
    def __init__(self, threshold_db: float = -20.0) -> None:
        self.threshold_db = threshold_db

    def detect(self, words: list[tuple[str, float, float]], samples: np.ndarray, sr: int) -> list[Emphasis]:
        out = []
        for w, s, e in words:
            i0 = max(0, int(s * sr))
            i1 = min(samples.size, int(e * sr))
            chunk = samples[i0:i1]
            rms = float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0
            db = 20 * __import__("math").log10(max(rms, 1e-9))
            out.append(Emphasis(word=w, start_s=s, end_s=e, energy_db=round(db, 2), emphasized=db > self.threshold_db))
        return out


__all__ = ["Emphasis", "EmphasisDetector"]
