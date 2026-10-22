"""Frame Layout & Subtitle Band Detection (from dub-studio compose.py).

Analyzes on-screen OCR text boxes to automatically partition them into:
1. Speech Subtitle Band (captions matching spoken audio narration -> blur only)
2. Graphic Text / Titles (on-screen logos, signs, titles -> translate & redraw)
"""

from __future__ import annotations

import collections
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def looks_like_caption(txt: str) -> bool:
    """Filter out OCR noise (UI icons, symbols, digits) — keep caption-shaped text."""
    t = (txt or "").strip()
    letters = sum(c.isalpha() for c in t)
    nonspace = sum(1 for c in t if not c.isspace())
    if letters < 3 or nonspace == 0:
        return False
    return (letters / nonspace) >= 0.6


def analyze_layout(
    ocr_detections: list[tuple[Any, ...]],
    frame_height: float,
    spoken_vocab: set[str] | None = None,
    band_frac: float = 0.10,
    lower_from: float = 0.45,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], int | None]:
    """
    Analyze OCR detections to identify the running speech subtitle band.

    Subtitle band characteristics:
    - Located in lower 55% of video frame (lower_from >= 0.45)
    - High string recurrence across timestamps (distinct_texts >= 3)
    - Words match spoken transcript (spoken_fraction >= 0.5)

    Args:
        ocr_detections: List of (text, x, y, w, h, t0, t1).
        frame_height: Video frame height in pixels.
        spoken_vocab: Set of lowercase words present in ASR transcript.
        band_frac: Height of horizontal analysis bands as fraction of frame height.
        lower_from: Start of lower frame search zone (0.45 = lower 55%).

    Returns:
        Tuple of (localize_list, caption_boxes_list, dominant_sub_y_center).
    """
    valid = [r for r in ocr_detections if looks_like_caption(r[0])]
    if not valid:
        return list(ocr_detections), [], None

    band_h = max(1.0, frame_height * band_frac)
    bands: dict[int, list[tuple[Any, ...]]] = collections.defaultdict(list)

    for r in valid:
        cy = r[2] + r[4] / 2.0
        bands[int(cy // band_h)].append(r)

    def _cy(b_idx: int) -> float:
        cys = sorted(r[2] + r[4] / 2.0 for r in bands[b_idx])
        return cys[len(cys) // 2]

    def _distinct_texts(rs: list[tuple[Any, ...]]) -> int:
        return len({r[0].strip().lower() for r in rs if r[0].strip()})

    def _spoken_frac(rs: list[tuple[Any, ...]]) -> float:
        if not spoken_vocab:
            return 1.0
        distinct = {r[0].strip().lower() for r in rs if r[0].strip()}
        if not distinct:
            return 0.0
        hit = 0
        for t in distinct:
            words = re.findall(r"[^\W\d_]+", t)
            if words and sum(w in spoken_vocab for w in words) >= 0.5 * len(words):
                hit += 1
        return hit / len(distinct)

    sub_lines = [
        b
        for b in bands
        if _cy(b) >= lower_from * frame_height
        and _distinct_texts(bands[b]) >= 3
        and _spoken_frac(bands[b]) >= 0.5
    ]

    if not sub_lines:
        return list(ocr_detections), [], None

    centers = sorted(_cy(b) for b in sub_lines)
    richest_band = max(sub_lines, key=lambda b: _distinct_texts(bands[b]))
    sub_y = int(_cy(richest_band))

    def on_sub_line(r: tuple[Any, ...]) -> bool:
        return any(abs((r[2] + r[4] / 2.0) - c) <= 0.7 * band_h for c in centers)

    caption_boxes = [
        (r[1], r[2], r[3], r[4], r[5], (r[6] if len(r) > 6 else r[5]))
        for r in ocr_detections
        if on_sub_line(r) and any(c.isalpha() for c in r[0])
    ]

    localize = [r for r in ocr_detections if not on_sub_line(r)]
    localize.sort(key=lambda r: (r[5], r[2]))

    return localize, caption_boxes, sub_y


__all__ = ["analyze_layout", "looks_like_caption"]
