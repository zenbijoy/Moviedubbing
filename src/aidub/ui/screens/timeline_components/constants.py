"""
Shared Constants and Helpers for Timeline UI Components.
"""

from __future__ import annotations

TRACK_HEIGHT = 32
TRACK_HEADER_WIDTH = 218
RULER_HEIGHT = 30
MIN_CLIP_WIDTH = 6
PX_PER_SEC_DEFAULT = 78.0
NAV_RAIL_WIDTH = 168
TOOL_PALETTE_WIDTH = 82

type ClipTuple = tuple[str, float, float, str, float | None]

_TRACK_DEFS = [
    ("V3", "Video", "#3B82F6", "video"),
    ("V2", "Lip Sync", "#8B5CF6", "video"),
    ("V1", "Source Video", "#3B82F6", "video"),
    ("A1", "Source Audio", "#10B981", "audio"),
    ("A2", "Dubbed Voice", "#8B5CF6", "audio"),
    ("A3", "Music", "#06B6D4", "audio"),
    ("A4", "SFX", "#F97316", "audio"),
    ("A5", "Ambience", "#EAB308", "audio"),
    ("S1", "Source Subs", "#2563EB", "subtitle"),
    ("S2", "Target Subs", "#1E3A8A", "subtitle"),
]


def _format_tc(sec: float) -> str:
    """Convert floating seconds to an absolute zero-based studio timecode."""
    total_sec = max(0.0, sec)
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    s = int(total_sec % 60)
    ms = int((total_sec - int(total_sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}:{ms:03d}"


__all__ = [
    "MIN_CLIP_WIDTH",
    "NAV_RAIL_WIDTH",
    "PX_PER_SEC_DEFAULT",
    "RULER_HEIGHT",
    "TOOL_PALETTE_WIDTH",
    "TRACK_HEADER_WIDTH",
    "TRACK_HEIGHT",
    "ClipTuple",
    "_TRACK_DEFS",
    "_format_tc",
]

