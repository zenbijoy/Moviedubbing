"""
Comprehensive unit tests for Phase 4 desktop UI components:
  - Task 4.1: Multitrack Timeline Surface & Models
  - Task 4.2: NLE Editorial Command Engine & Keyboard Shortcuts
  - Task 4.3: Dual Viewer & Frame-Accurate Playback Engine
  - Task 4.4: 26-Screen Catalog Registry
  - Task 4.5: Command Palette & Workspace Layout Manager
"""

from __future__ import annotations

import pytest

from aidub.contracts.base import Identifier
from aidub.media.playback import DualViewerMode, PlaybackController
from aidub.ui.editorial import EditorialCommandEngine, SnappingEngine
from aidub.ui.keyboard_shortcuts import (
    ShortcutAction,
    ShortcutManager,
)
from aidub.ui.timeline.model import (
    TimelineClip,
    TimelineLayoutEngine,
    TimelineTrack,
    TrackId,
    TrackKind,
    create_default_multitrack_timeline,
)
from aidub.ui.workspace_manager import (
    WorkspaceLayout,
    WorkspaceManager,
    WorkspacePreset,
)

# ── Task 4.1: Multitrack Timeline ─────────────────────────────────────────────


def test_timeline_default_9_tracks() -> None:
    tracks = create_default_multitrack_timeline()
    assert len(tracks) == 9
    track_ids = [t.track_id for t in tracks]
    assert track_ids == [
        TrackId.V1,
        TrackId.V2,
        TrackId.A1,
        TrackId.A2,
        TrackId.A3,
        TrackId.A4,
        TrackId.A5,
        TrackId.S1,
        TrackId.S2,
    ]


def test_timeline_layout_engine_time_px_conversion() -> None:
    engine = TimelineLayoutEngine(zoom_px_per_sec=100.0)
    assert engine.time_to_px(0) == 0.0
    assert engine.time_to_px(1000) == 100.0
    assert engine.time_to_px(2500) == 250.0

    assert engine.px_to_time(100.0) == 1000
    assert engine.px_to_time(250.0) == 2500


def test_timeline_layout_engine_visible_clips_culling() -> None:
    engine = TimelineLayoutEngine(zoom_px_per_sec=100.0, viewport_width_px=500)
    tracks = create_default_multitrack_timeline()

    # Add 2 clips to A1 track: one visible (start 0ms), one offscreen (start 10000ms = 1000px)
    clip_visible = TimelineClip(
        clip_id=Identifier("c-001"),
        track_id=TrackId.A1,
        start_ms=0,
        duration_ms=2000,
        label="Visible",
    )
    clip_offscreen = TimelineClip(
        clip_id=Identifier("c-002"),
        track_id=TrackId.A1,
        start_ms=10000,
        duration_ms=2000,
        label="Culled",
    )
    tracks[2].clips.extend([clip_visible, clip_offscreen])

    visible = engine.visible_clips(tracks)
    clip_ids = [clip.clip_id for clip, x, y, w, h in visible]

    assert "c-001" in clip_ids
    assert "c-002" not in clip_ids


# ── Task 4.2: Editorial Toolset & Keyboard Engine ─────────────────────────────


def test_editorial_blade_split() -> None:
    clip = TimelineClip(
        clip_id=Identifier("c-orig"),
        track_id=TrackId.A1,
        start_ms=1000,
        duration_ms=4000,
        label="Take",
    )
    left, right = EditorialCommandEngine.blade_split(clip, 2500)

    assert left.start_ms == 1000
    assert left.duration_ms == 1500
    assert left.end_ms == 2500

    assert right.start_ms == 2500
    assert right.duration_ms == 2500
    assert right.end_ms == 5000


def test_editorial_blade_split_outside_bounds_raises() -> None:
    clip = TimelineClip(
        clip_id=Identifier("c-orig"), track_id=TrackId.A1, start_ms=1000, duration_ms=4000
    )
    with pytest.raises(ValueError, match="strictly inside"):
        EditorialCommandEngine.blade_split(clip, 5000)  # at end edge


def test_editorial_ripple_delete() -> None:
    track = TimelineTrack(
        track_id=TrackId.A1,
        display_name="A1",
        kind=TrackKind.AUDIO,
        clips=[
            TimelineClip(
                clip_id=Identifier("c1"), track_id=TrackId.A1, start_ms=0, duration_ms=1000
            ),
            TimelineClip(
                clip_id=Identifier("c2"), track_id=TrackId.A1, start_ms=1000, duration_ms=2000
            ),
            TimelineClip(
                clip_id=Identifier("c3"), track_id=TrackId.A1, start_ms=3000, duration_ms=1000
            ),
        ],
    )

    # Ripple delete c2 (duration 2000ms)
    updated = EditorialCommandEngine.ripple_delete(track, "c2")
    assert len(updated.clips) == 2
    # c3 should be shifted left by 2000ms (from 3000ms -> 1000ms)
    c3_updated = next(c for c in updated.clips if c.clip_id == "c3")
    assert c3_updated.start_ms == 1000


def test_editorial_snapping_engine() -> None:
    snapper = SnappingEngine(tolerance_ms=50)
    snap_points = [0, 1000, 2500, 5000]

    # Within tolerance
    snapped, flag = snapper.snap(2490, snap_points)
    assert flag is True
    assert snapped == 2500

    # Outside tolerance
    snapped, flag = snapper.snap(2300, snap_points)
    assert flag is False
    assert snapped == 2300


def test_keyboard_shortcuts_resolver() -> None:
    mgr = ShortcutManager()
    assert mgr.resolve("V") == ShortcutAction.TOOL_SELECT
    assert mgr.resolve("B") == ShortcutAction.TOOL_BLADE
    assert mgr.resolve("Ctrl+K") == ShortcutAction.COMMAND_PALETTE
    assert mgr.resolve("Space") == ShortcutAction.PLAY_PAUSE


# ── Task 4.3: Playback Controller & Dual Viewer ───────────────────────────────


def test_playback_controller_shuttle_jkl() -> None:
    ctrl = PlaybackController(fps=24.0)
    assert ctrl.state.playing is False

    ctrl.play()
    assert ctrl.state.playing is True
    assert ctrl.state.shuttle_speed == 1.0

    ctrl.shuttle_l()  # 2x forward
    assert ctrl.state.shuttle_speed == 2.0

    ctrl.shuttle_k()  # Pause
    assert ctrl.state.playing is False
    assert ctrl.state.shuttle_speed == 0.0

    ctrl.shuttle_j()  # 1x reverse
    assert ctrl.state.playing is True
    assert ctrl.state.shuttle_speed == -1.0


def test_playback_controller_seek_frame() -> None:
    ctrl = PlaybackController(fps=24.0)
    # Frame 24 at 24fps = 1000ms
    ctrl.seek_ms(1000)
    assert ctrl.state.current_frame == 24

    new_ms = ctrl.state.seek_frame(48)
    assert new_ms == 2000


def test_playback_controller_dual_viewer_modes() -> None:
    ctrl = PlaybackController()
    for mode in DualViewerMode:
        ctrl.set_viewer_mode(mode)
        assert ctrl.state.viewer_mode == mode


# ── Task 4.5: Workspace Manager ───────────────────────────────────────────────


def test_workspace_manager_load_presets() -> None:
    mgr = WorkspaceManager()
    for preset in WorkspacePreset:
        if preset == WorkspacePreset.CUSTOM:
            continue
        layout = mgr.load_preset(preset)
        assert layout.preset == preset
        assert len(layout.panels) > 0


def test_workspace_manager_save_custom_layout() -> None:
    mgr = WorkspaceManager()
    layout = WorkspaceLayout(
        layout_id=Identifier("layout_custom_001"),
        name="My Custom Editing Layout",
        preset=WorkspacePreset.CUSTOM,
    )
    mgr.save_custom_layout(layout)
    retrieved = mgr.get_layout("layout_custom_001")
    assert retrieved is not None
    assert retrieved.name == "My Custom Editing Layout"
