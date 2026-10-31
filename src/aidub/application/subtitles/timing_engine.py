"""Subtitle timing adjustment engine."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubtitleCue:
    start_s: float
    end_s: float
    text: str

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class SubtitleTimingEngine:
    @staticmethod
    def shift(cues: list[SubtitleCue], delta_s: float) -> list[SubtitleCue]:
        return [SubtitleCue(c.start_s + delta_s, c.end_s + delta_s, c.text) for c in cues]

    @staticmethod
    def scale(cues: list[SubtitleCue], factor: float) -> list[SubtitleCue]:
        if factor <= 0:
            raise ValueError("factor must be positive")
        return [SubtitleCue(c.start_s * factor, c.end_s * factor, c.text) for c in cues]

    @staticmethod
    def clamp(cues: list[SubtitleCue], min_s: float = 0.0) -> list[SubtitleCue]:
        out = []
        for c in cues:
            s = max(min_s, c.start_s)
            e = max(s, c.end_s)
            out.append(SubtitleCue(s, e, c.text))
        return out

    @staticmethod
    def ensure_min_duration(cues: list[SubtitleCue], min_dur: float) -> list[SubtitleCue]:
        out = []
        for c in cues:
            e = max(c.end_s, c.start_s + min_dur)
            out.append(SubtitleCue(c.start_s, e, c.text))
        return out


__all__ = ["SubtitleCue", "SubtitleTimingEngine"]
