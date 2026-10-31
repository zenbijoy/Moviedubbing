"""
Broadcast Subtitle Exporter: exports SubRip (SRT) and WebVTT (VTT) files
with frame-accurate timestamp formatting and millisecond rollover protection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SubCue:
    index: int
    start_s: float
    end_s: float
    text: str

    def __init__(
        self,
        index: int = 1,
        start_s: float = 0.0,
        end_s: float = 0.0,
        text: str = "",
        idx: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.index = idx if idx is not None else index
        self.start_s = start_s
        self.end_s = end_s
        self.text = text

    @property
    def idx(self) -> int:
        return self.index

    @idx.setter
    def idx(self, val: int) -> None:
        self.index = val


class SubtitleExporter:
    """Exports dialogue cues to standard SRT and WebVTT subtitle deliverables."""

    @staticmethod
    def _fmt_srt(t: float) -> str:
        total_ms = max(0, int(round(t * 1000.0)))
        ms = total_ms % 1000
        total_s = total_ms // 1000
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _fmt_vtt(t: float) -> str:
        total_ms = max(0, int(round(t * 1000.0)))
        ms = total_ms % 1000
        total_s = total_ms // 1000
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    @classmethod
    def to_srt(cls, cues: list[Any]) -> str:
        lines: list[str] = []
        for idx, c in enumerate(cues, 1):
            cue_index = getattr(c, "index", idx)
            start_s = getattr(c, "start_s", 0.0)
            end_s = getattr(c, "end_s", 0.0)
            text = getattr(c, "text", "")

            lines.append(str(cue_index))
            lines.append(f"{cls._fmt_srt(start_s)} --> {cls._fmt_srt(end_s)}")
            lines.append(str(text))
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def to_vtt(cls, cues: list[Any]) -> str:
        lines: list[str] = ["WEBVTT", ""]
        for idx, c in enumerate(cues, 1):
            start_s = getattr(c, "start_s", 0.0)
            end_s = getattr(c, "end_s", 0.0)
            text = getattr(c, "text", "")

            lines.append(f"{cls._fmt_vtt(start_s)} --> {cls._fmt_vtt(end_s)}")
            lines.append(str(text))
            lines.append("")
        return "\n".join(lines)


__all__ = ["SubCue", "SubtitleExporter"]
