"""Bilingual Subtitle Generator and LineMode Selector (from KrillinAI subtitle.go)."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LineMode(StrEnum):
    """Subtitle line mode formatting."""

    TARGET_ONLY = "target-only"
    BILINGUAL_TARGET_TOP = "bilingual-target-top"
    BILINGUAL_TARGET_BOTTOM = "bilingual-target-bottom"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds float into standard SRT timestamp format (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = round((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def resync_subtitles_to_fitted_timing(
    segments: list[dict[str, Any]],
    fitted_durations_ms: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Adjust subtitle segment start/end timestamps to match time-fitted dubbed speech.
    Protects subtitle readability by ensuring subtitle cues perfectly match dubbed dialogue.
    """
    adjusted_segments: list[dict[str, Any]] = []

    for seg in segments:
        new_seg = dict(seg)
        uid = str(seg.get("id") or seg.get("utterance_id", ""))
        orig_start = float(seg.get("start", 0.0))
        orig_end = float(seg.get("end", orig_start + 1.0))
        orig_dur = max(0.1, orig_end - orig_start)

        if uid in fitted_durations_ms:
            fitted_dur = fitted_durations_ms[uid] / 1000.0
            # Retain start time, adjust end time to fitted length
            new_seg["end"] = round(orig_start + fitted_dur, 3)
        else:
            new_seg["end"] = orig_end

        adjusted_segments.append(new_seg)

    return adjusted_segments


def write_srt(
    segments: list[dict[str, Any]],
    output_path: Path | str,
    translated: bool = False,
) -> Path:
    """
    Write standard single-language SRT subtitle file.

    Args:
        segments: List of segment dicts with start, end, text/tgt.
        output_path: Output SRT file destination.
        translated: If True, writes target language text (tgt); else source text.

    Returns:
        Path to generated SRT file.
    """
    out_p = Path(output_path)
    lines: list[str] = []

    for idx, seg in enumerate(segments, start=1):
        txt = str(seg.get("tgt" if translated else "text", "")).strip()
        if not txt:
            continue

        start_ts = format_srt_timestamp(float(seg.get("start", 0.0)))
        end_ts = format_srt_timestamp(float(seg.get("end", 0.0)))

        lines.append(f"{idx}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(txt)
        lines.append("")

    out_p.write_text("\n".join(lines), encoding="utf-8")
    return out_p


def write_bilingual_srt(
    segments: list[dict[str, Any]],
    output_path: Path | str,
    mode: LineMode = LineMode.BILINGUAL_TARGET_BOTTOM,
) -> Path:
    """
    Write dual-language bilingual SRT subtitle file.

    Args:
        segments: List of segment dicts with source text and target tgt.
        output_path: Output SRT file destination.
        mode: LineMode (bilingual-target-top or bilingual-target-bottom).

    Returns:
        Path to generated bilingual SRT file.
    """
    out_p = Path(output_path)
    lines: list[str] = []

    for idx, seg in enumerate(segments, start=1):
        src_txt = str(seg.get("text", "")).strip()
        tgt_txt = str(seg.get("tgt", "")).strip()

        if not src_txt and not tgt_txt:
            continue

        start_ts = format_srt_timestamp(float(seg.get("start", 0.0)))
        end_ts = format_srt_timestamp(float(seg.get("end", 0.0)))

        lines.append(f"{idx}")
        lines.append(f"{start_ts} --> {end_ts}")

        if mode == LineMode.BILINGUAL_TARGET_TOP:
            lines.append(tgt_txt)
            lines.append(src_txt)
        else:  # BILINGUAL_TARGET_BOTTOM
            lines.append(src_txt)
            lines.append(tgt_txt)

        lines.append("")

    out_p.write_text("\n".join(lines), encoding="utf-8")
    return out_p


__all__ = [
    "LineMode",
    "format_srt_timestamp",
    "resync_subtitles_to_fitted_timing",
    "write_bilingual_srt",
    "write_srt",
]
