"""
Unit tests for CutEngine application service.
"""

from __future__ import annotations

import pytest

from aidub.application.timeline.cut_engine import CutEngine
from aidub.contracts.base import Identifier
from aidub.ui.timeline.model import TimelineClip, TrackId


def test_cut_engine_blade_split() -> None:
    engine = CutEngine()

    clip = TimelineClip(
        clip_id=Identifier("clip_master"),
        track_id=TrackId.A2,
        start_ms=1000,
        duration_ms=4000,
        label="Dialogue Master",
    )
    assert clip.end_ms == 5000

    # Blade split at 2500ms
    left, right = engine.blade_split(clip, split_time_ms=2500)

    assert left.start_ms == 1000
    assert left.duration_ms == 1500
    assert left.end_ms == 2500
    assert "Part 1" in left.label

    assert right.start_ms == 2500
    assert right.duration_ms == 2500
    assert right.end_ms == 5000
    assert "Part 2" in right.label

    # Invalid split (out of bounds)
    with pytest.raises(ValueError):
        engine.blade_split(clip, split_time_ms=500)
    with pytest.raises(ValueError):
        engine.blade_split(clip, split_time_ms=6000)


def test_cut_engine_trim_head_and_tail() -> None:
    engine = CutEngine()

    clip = TimelineClip(
        clip_id=Identifier("clip_trim"),
        track_id=TrackId.A2,
        start_ms=2000,
        duration_ms=3000,
    )
    assert clip.end_ms == 5000

    # Trim head from 2000 to 2500ms -> duration is now 2500ms
    trimmed_head = engine.trim_head(clip, new_start_ms=2500)
    assert trimmed_head.start_ms == 2500
    assert trimmed_head.duration_ms == 2500
    assert trimmed_head.end_ms == 5000

    # Trim tail from 5000 to 4200ms -> duration is now 2200ms
    trimmed_tail = engine.trim_tail(clip, new_end_ms=4200)
    assert trimmed_tail.start_ms == 2000
    assert trimmed_tail.duration_ms == 2200
    assert trimmed_tail.end_ms == 4200


def test_cut_engine_ripple_delete() -> None:
    engine = CutEngine()

    c1 = TimelineClip(clip_id=Identifier("c1"), track_id=TrackId.A2, start_ms=0, duration_ms=1000)
    c2 = TimelineClip(clip_id=Identifier("c2"), track_id=TrackId.A2, start_ms=1000, duration_ms=2000)  # to delete
    c3 = TimelineClip(clip_id=Identifier("c3"), track_id=TrackId.A2, start_ms=3000, duration_ms=1500)
    c4 = TimelineClip(clip_id=Identifier("c4"), track_id=TrackId.A2, start_ms=4500, duration_ms=1000)

    clips = [c1, c2, c3, c4]

    # Ripple delete c2 (duration 2000ms)
    rippled = engine.ripple_delete(clips, "c2")
    assert len(rippled) == 3

    # c1 is unaffected
    assert rippled[0].clip_id == "c1"
    assert rippled[0].start_ms == 0

    # c3 shifted from 3000ms left by 2000ms -> starts at 1000ms
    assert rippled[1].clip_id == "c3"
    assert rippled[1].start_ms == 1000
    assert rippled[1].duration_ms == 1500

    # c4 shifted from 4500ms left by 2000ms -> starts at 2500ms
    assert rippled[2].clip_id == "c4"
    assert rippled[2].start_ms == 2500


def test_cut_engine_speed_ramp_and_slip() -> None:
    engine = CutEngine()

    clip = TimelineClip(
        clip_id=Identifier("clip_speed"),
        track_id=TrackId.A2,
        start_ms=1000,
        duration_ms=2000,
    )

    # 2.0x speed -> 1000ms duration
    fast = engine.speed_ramp(clip, speed_multiplier=2.0)
    assert fast.duration_ms == 1000

    # 0.5x speed -> 4000ms duration
    slow = engine.speed_ramp(clip, speed_multiplier=0.5)
    assert slow.duration_ms == 4000

    # Slip clip forward +500ms
    slipped = engine.slip_clip(clip, delta_ms=500)
    assert slipped.start_ms == 1500
    assert slipped.duration_ms == 2000
