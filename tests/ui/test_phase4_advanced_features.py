"""
Unit tests for Advanced NLE Timeline & Production Features:
  - Multi-track Undo/Redo Transaction Stack
  - Automated Crossfade & Equal-Power Gain Curves
  - Dynamic Timeline Zoom & Playhead Auto-Scroll
  - Broadcast Stem Export Staging Engine
"""

from __future__ import annotations

import pytest

from aidub.contracts.base import Identifier
from aidub.media.crossfade import (
    CrossfadeCalculator,
    FadeCurveShape,
)
from aidub.media.stem_export import StemExportManager, StemExportRequest, StemKind
from aidub.ui.timeline.autoscroll import AutoScrollMode, TimelineScrollController
from aidub.ui.timeline.model import (
    TimelineLayoutEngine,
    TrackId,
    create_default_multitrack_timeline,
)
from aidub.ui.undo_redo import UndoCommand, UndoManager

# ── 1. Multi-Track Undo/Redo ──────────────────────────────────────────────────


def test_undo_manager_execute_and_undo_redo() -> None:
    mgr = UndoManager(max_levels=50)
    assert mgr.can_undo is False
    assert mgr.can_redo is False

    cmd1 = UndoCommand(
        command_id=Identifier("cmd_001"),
        name="Split Clip A1",
        snapshot_before={"dur": 2000},
        snapshot_after={"dur": 1000},
    )
    mgr.execute(cmd1)

    assert mgr.can_undo is True
    assert mgr.undo_action_name == "Split Clip A1"

    undone = mgr.undo()
    assert undone is not None
    assert undone.name == "Split Clip A1"
    assert mgr.can_undo is False
    assert mgr.can_redo is True

    redone = mgr.redo()
    assert redone is not None
    assert redone.name == "Split Clip A1"
    assert mgr.can_undo is True
    assert mgr.can_redo is False


# ── 2. Crossfade & Gain Curves ────────────────────────────────────────────────


def test_crossfade_calculator_equal_power_gain() -> None:
    # At center (t=0.5), equal power gain is cos(45deg) = sin(45deg) = 0.7071
    out_gain, in_gain = CrossfadeCalculator.calculate_gain(0.5, FadeCurveShape.EQUAL_POWER)
    assert out_gain == pytest.approx(0.7071, abs=0.01)
    assert in_gain == pytest.approx(0.7071, abs=0.01)


def test_crossfade_calculator_overlap_detection() -> None:
    region = CrossfadeCalculator.detect_crossfade(
        left_clip_start_ms=0,
        left_clip_dur_ms=3000,
        right_clip_start_ms=2500,  # 500ms overlap
        right_clip_dur_ms=2000,
        left_id="left_01",
        right_id="right_01",
    )
    assert region is not None
    assert region.overlap_duration_ms == 500
    assert region.overlap_start_ms == 2500


# ── 3. Dynamic Zoom & Playhead Auto-Scroll ────────────────────────────────────


def test_autoscroll_controller_smooth_center() -> None:
    engine = TimelineLayoutEngine(zoom_px_per_sec=100.0, viewport_width_px=1000)
    ctrl = TimelineScrollController(engine, mode=AutoScrollMode.SMOOTH_CENTER)

    # Playhead at 10,000ms; viewport duration = 10,000ms -> center at 5,000ms
    new_scroll = ctrl.update_playhead(10000)
    assert new_scroll == 5000


def test_autoscroll_zoom_anchored_at_point() -> None:
    engine = TimelineLayoutEngine(zoom_px_per_sec=100.0, viewport_width_px=1000)
    ctrl = TimelineScrollController(engine)

    # Focal point at 500px, zoom in by 2.0x
    new_zoom = ctrl.zoom_at_point(focal_px=500.0, zoom_factor=2.0)
    assert new_zoom == 200.0


# ── 4. Broadcast Stem Export Staging ──────────────────────────────────────────


def test_stem_export_manager_build_specs() -> None:
    req = StemExportRequest(
        project_id="prj_feature_film",
        export_id=Identifier("exp_001"),
        selected_stems=[StemKind.DIALOGUE, StemKind.FULL_PRINT_MASTER],
    )
    tracks = create_default_multitrack_timeline()
    specs = StemExportManager.build_export_specs(req, tracks, total_project_duration_ms=120_000)

    assert len(specs) == 2
    dialogue_spec = next(s for s in specs if s.stem_kind == StemKind.DIALOGUE)
    assert dialogue_spec.output_filename == "prj_feature_film_dialogue.wav"
    assert dialogue_spec.active_track_ids == [TrackId.A1, TrackId.A2]
    assert dialogue_spec.duration_ms == 120_000
