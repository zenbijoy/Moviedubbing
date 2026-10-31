"""CapCut-style auto-captioner: segment audio into word-ish chunks."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Caption:
    start_s: float
    end_s: float
    text: str


class AutoCaptioner:
    def __init__(self, frame_ms: int = 30, energy_threshold: float = 0.02) -> None:
        self.frame_ms = frame_ms
        self.energy_threshold = energy_threshold

    def segment(self, samples: np.ndarray, sr: int, words: list[str] | None = None) -> list[Caption]:
        if samples.size == 0:
            return []
        frame = max(1, int(self.frame_ms / 1000.0 * sr))
        # find voiced frames
        voiced = []
        for i in range(0, samples.size - frame, frame):
            chunk = samples[i:i + frame]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            voiced.append(rms > self.energy_threshold)
        # group contiguous voiced
        groups = []
        cur_start = None
        for idx, v in enumerate(voiced):
            t = idx * frame / sr
            if v and cur_start is None:
                cur_start = t
            if (not v or idx == len(voiced) - 1) and cur_start is not None:
                groups.append((cur_start, (idx + 1) * frame / sr))
                cur_start = None
        if words:
            # distribute words across groups
            out = []
            wi = 0
            per = max(1, len(words) // max(1, len(groups)))
            for s, e in groups:
                chunk_words = words[wi:wi + per]
                wi += per
                out.append(Caption(s, e, " ".join(chunk_words)))
            if wi < len(words):
                if out:
                    out[-1].text += " " + " ".join(words[wi:])
            return out
        return [Caption(s, e, "") for s, e in groups]


__all__ = ["Caption", "AutoCaptioner"]
