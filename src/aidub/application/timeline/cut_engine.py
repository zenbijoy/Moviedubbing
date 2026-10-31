"""
Non-Linear Editing (NLE) Cutting Engine.

Implements professional timeline cutting and trimming operations:
  - Razor Blade splitting at exact playhead timecodes.
  - Head and Tail trimming with duration recalculation.
  - Ripple delete closing editorial timeline gaps.
  - Speed ramping (constant & variable speed factors).
  - Slip and slide clip repositioning.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from aidub.contracts.base import Identifier
from aidub.ui.timeline.model import TimelineClip, TrackId

logger = logging.getLogger(__name__)


class CutEngine:
    """Core mathematical and structural NLE cutting engine."""

    def blade_split(
        self,
        clip: TimelineClip,
        split_time_ms: int,
    ) -> tuple[TimelineClip, TimelineClip]:
        """
        Splits a clip into left and right sub-clips at split_time_ms.
        Raises ValueError if split_time_ms is not strictly within (start_ms, end_ms).
        """
        if not (clip.start_ms < split_time_ms < clip.end_ms):
            raise ValueError(
                f"Split time {split_time_ms}ms outside clip range [{clip.start_ms}ms, {clip.end_ms}ms]."
            )

        left_dur = split_time_ms - clip.start_ms
        right_dur = clip.end_ms - split_time_ms

        left_clip = TimelineClip(
            clip_id=Identifier(f"clip_{uuid4().hex[:10]}"),
            track_id=clip.track_id,
            start_ms=clip.start_ms,
            duration_ms=left_dur,
            label=f"{clip.label} (Part 1)",
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )

        right_clip = TimelineClip(
            clip_id=Identifier(f"clip_{uuid4().hex[:10]}"),
            track_id=clip.track_id,
            start_ms=split_time_ms,
            duration_ms=right_dur,
            label=f"{clip.label} (Part 2)",
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )

        logger.info(
            "CutEngine: Blade split clip %s at %dms into (%dms, %dms)",
            clip.clip_id,
            split_time_ms,
            left_dur,
            right_dur,
        )
        return left_clip, right_clip

    def trim_head(self, clip: TimelineClip, new_start_ms: int) -> TimelineClip:
        """Trims clip in-point to new_start_ms, reducing duration."""
        if not (clip.start_ms <= new_start_ms < clip.end_ms):
            raise ValueError(
                f"Invalid trim head {new_start_ms}ms for clip [{clip.start_ms}ms, {clip.end_ms}ms]."
            )
        new_dur = clip.end_ms - new_start_ms
        return TimelineClip(
            clip_id=clip.clip_id,
            track_id=clip.track_id,
            start_ms=new_start_ms,
            duration_ms=new_dur,
            label=clip.label,
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )

    def trim_tail(self, clip: TimelineClip, new_end_ms: int) -> TimelineClip:
        """Trims clip out-point to new_end_ms, updating duration."""
        if not (clip.start_ms < new_end_ms <= clip.end_ms):
            raise ValueError(
                f"Invalid trim tail {new_end_ms}ms for clip [{clip.start_ms}ms, {clip.end_ms}ms]."
            )
        new_dur = new_end_ms - clip.start_ms
        return TimelineClip(
            clip_id=clip.clip_id,
            track_id=clip.track_id,
            start_ms=clip.start_ms,
            duration_ms=new_dur,
            label=clip.label,
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )

    def ripple_delete(
        self,
        clips: list[TimelineClip],
        target_clip_id: str,
    ) -> list[TimelineClip]:
        """
        Deletes target_clip_id and shifts all subsequent clips leftward to close the gap.
        """
        target_idx = -1
        for idx, c in enumerate(clips):
            if c.clip_id == target_clip_id:
                target_idx = idx
                break

        if target_idx == -1:
            return list(clips)

        target_clip = clips[target_idx]
        gap_ms = target_clip.duration_ms

        updated_clips: list[TimelineClip] = []
        for idx, c in enumerate(clips):
            if idx == target_idx:
                continue
            elif c.start_ms >= target_clip.end_ms:
                # Shift subsequent clip left by gap_ms
                shifted = TimelineClip(
                    clip_id=c.clip_id,
                    track_id=c.track_id,
                    start_ms=max(0, c.start_ms - gap_ms),
                    duration_ms=c.duration_ms,
                    label=c.label,
                    utterance_id=c.utterance_id,
                    color_hex=c.color_hex,
                )
                updated_clips.append(shifted)
            else:
                updated_clips.append(c)

        return updated_clips

    def speed_ramp(
        self,
        clip: TimelineClip,
        speed_multiplier: float,
    ) -> TimelineClip:
        """
        Alters clip speed factor (e.g. 2.0x halves duration, 0.5x doubles duration).
        """
        if speed_multiplier <= 0.05 or speed_multiplier > 10.0:
            raise ValueError(f"Speed multiplier {speed_multiplier} out of valid range (0.05 - 10.0).")

        new_dur = max(1, int(round(clip.duration_ms / speed_multiplier)))
        return TimelineClip(
            clip_id=clip.clip_id,
            track_id=clip.track_id,
            start_ms=clip.start_ms,
            duration_ms=new_dur,
            label=f"{clip.label} ({speed_multiplier:.1f}x)",
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )

    def slip_clip(self, clip: TimelineClip, delta_ms: int) -> TimelineClip:
        """Nudges clip position forward or backward in time keeping duration constant."""
        new_start = max(0, clip.start_ms + delta_ms)
        return TimelineClip(
            clip_id=clip.clip_id,
            track_id=clip.track_id,
            start_ms=new_start,
            duration_ms=clip.duration_ms,
            label=clip.label,
            utterance_id=clip.utterance_id,
            color_hex=clip.color_hex,
        )


__all__ = [
    "CutEngine",
]
