"""Emotion curve: per-time intensity curve for a cue."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EmotionCurvePoint:
    t: float  # 0..1
    intensity: float


class EmotionCurve:
    def __init__(self, points: list[EmotionCurvePoint] | None = None) -> None:
        self.points = sorted(points or [EmotionCurvePoint(0.0, 1.0), EmotionCurvePoint(1.0, 1.0)], key=lambda p: p.t)

    def evaluate(self, t: float) -> float:
        t = max(0.0, min(1.0, t))
        if t <= self.points[0].t:
            return self.points[0].intensity
        if t >= self.points[-1].t:
            return self.points[-1].intensity
        for i in range(len(self.points) - 1):
            a, b = self.points[i], self.points[i + 1]
            if a.t <= t <= b.t:
                frac = (t - a.t) / max(1e-9, b.t - a.t)
                return a.intensity + (b.intensity - a.intensity) * frac
        return 1.0

    def to_array(self, n: int = 32) -> np.ndarray:
        return np.array([self.evaluate(i / (n - 1)) for i in range(n)], dtype=np.float32)


__all__ = ["EmotionCurve", "EmotionCurvePoint"]
