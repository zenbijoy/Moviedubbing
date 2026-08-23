"""
Production-grade SubRip (.srt) Subtitle Parser.

Features:
- Exact millisecond clock timestamp conversion helpers (srt_timestamp_to_ms, ms_to_srt_timestamp)
- Tolerant parsing for malformed SRT blocks
- Stutter & hesitation speech pattern detection (I… I…, ha… ha…, pause, ellipsis)
- Multi-speaker hyphen dialogue line detection (-, –, —)
- Tag stripping and clean text normalization
"""

from __future__ import annotations

import re
import logging
from aidub.subtitles.models import DialogueSegment
from aidub.subtitles.parser_base import SubtitleParser

logger = logging.getLogger(__name__)

# Timestamp format: 00:00:09,000 or 00:00:09.000
_SRT_TIMESTAMP_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,\.](?P<ms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{1,2}):(?P<em_>\d{2}):(?P<es>\d{2})[,\.](?P<ems>\d{3})"
)

# Stutter / Hesitation regex patterns
_STUTTER_RE = re.compile(r"\b(\w+)[…\.]{1,3}\s*\1\b|\b\w{1,3}[…\.]{1,3}\s*\w{1,3}[…\.]{1,3}", re.IGNORECASE | re.UNICODE)
_HESITATION_RE = re.compile(r"[…\.]{2,}|uh|um|er|ah|ha…|ha\.\.\.", re.IGNORECASE | re.UNICODE)

# Multi-speaker line prefix regex (hyphens / dashes)
_MULTI_SPEAKER_RE = re.compile(r"^\s*[\-\–\—]\s*\S+", re.MULTILINE)

# Basic HTML / SSA tag stripper
_TAG_RE = re.compile(r"<[^>]+>|\{[^}]+\}")


def srt_timestamp_to_ms(ts: str) -> int:
    """
    Convert SRT timestamp string ('00:00:09,000' or '00:00:09.000') to milliseconds integer.

    Example:
        srt_timestamp_to_ms("00:01:20,500") -> 80500
    """
    ts = ts.strip().replace(".", ",")
    parts = ts.split("-->")
    target = parts[0].strip() if parts else ts
    h_m_s_ms = re.split(r"[:,]", target)
    if len(h_m_s_ms) < 4:
        raise ValueError(f"Invalid SRT timestamp format: '{ts}'")
    h, m, s, ms = (int(x) for x in h_m_s_ms[:4])
    return (h * 3600 + m * 60 + s) * 1000 + ms


def ms_to_srt_timestamp(ms: int) -> str:
    """
    Convert milliseconds integer to standard SRT timestamp string ('00:00:09,000').

    Example:
        ms_to_srt_timestamp(80500) -> "00:01:20,500"
    """
    if ms < 0:
        ms = 0
    total_seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


class SRTParser(SubtitleParser):
    """SRT Subtitle format parser."""

    @property
    def format_name(self) -> str:
        return "srt"

    def parse_text(self, text_content: str) -> list[DialogueSegment]:
        """Parse SRT text content into structured DialogueSegments."""
        if not text_content or not text_content.strip():
            return []

        # Normalize line endings
        normalized = text_content.replace("\r\n", "\n").replace("\r", "\n")
        raw_blocks = normalized.strip().split("\n\n")

        segments: list[DialogueSegment] = []
        auto_index = 1

        for block in raw_blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue

            # Identify index, timestamp, and text lines
            idx = auto_index
            ts_line_idx = -1

            for i, line in enumerate(lines[:3]):
                if "-->" in line:
                    ts_line_idx = i
                    break

            if ts_line_idx == -1:
                logger.debug("Skipping block without valid timestamp arrow: %r", block[:40])
                continue

            # Try parsing explicit subtitle index if available
            if ts_line_idx > 0:
                try:
                    idx = int(lines[0])
                except ValueError:
                    idx = auto_index

            ts_line = lines[ts_line_idx]
            match = _SRT_TIMESTAMP_RE.search(ts_line)
            if not match:
                logger.warning("Failed to parse SRT timestamp line: '%s'", ts_line)
                continue

            h, m, s, ms_val = int(match.group("h")), int(match.group("m")), int(match.group("s")), int(match.group("ms"))
            eh, em, es, ems_val = int(match.group("eh")), int(match.group("em_")), int(match.group("es")), int(match.group("ems"))

            start_ms = (h * 3600 + m * 60 + s) * 1000 + ms_val
            end_ms = (eh * 3600 + em * 60 + es) * 1000 + ems_val

            text_lines = lines[ts_line_idx + 1 :]
            if not text_lines:
                continue

            raw_text = "\n".join(text_lines)
            clean_text = _TAG_RE.sub("", raw_text).strip()

            if not clean_text:
                continue

            # Stutter & hesitation detection
            has_hesitation = bool(_STUTTER_RE.search(clean_text) or _HESITATION_RE.search(clean_text))
            speech_style = "stutter" if _STUTTER_RE.search(clean_text) else ("hesitation" if has_hesitation else None)

            # Multi-speaker hyphen detection
            hyphen_matches = _MULTI_SPEAKER_RE.findall(raw_text)
            possible_multi_speaker = len(hyphen_matches) >= 2 or (len(text_lines) >= 2 and any(l.startswith("-") or l.startswith("–") or l.startswith("—") for l in text_lines))
            speaker_count_est = max(1, len(hyphen_matches)) if possible_multi_speaker else 1

            segment = DialogueSegment(
                subtitle_index=idx,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=max(0, end_ms - start_ms),
                original_text=clean_text,
                has_hesitation=has_hesitation,
                speech_style=speech_style,
                possible_multi_speaker=possible_multi_speaker,
                speaker_count_estimate=speaker_count_est,
                status="imported",
            )
            segments.append(segment)
            auto_index += 1

        logger.info("Parsed %d dialogue segments from SRT input", len(segments))
        return segments


__all__ = ["SRTParser", "srt_timestamp_to_ms", "ms_to_srt_timestamp"]
