"""Speaker similarity / consistency utilities."""
from __future__ import annotations

import math


class SpeakerSimilarity:
    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def consistent(a: list[float], b: list[float], threshold: float = 0.85) -> bool:
        return SpeakerSimilarity.cosine(a, b) >= threshold


__all__ = ["SpeakerSimilarity"]
