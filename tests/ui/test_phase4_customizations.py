"""
Unit tests for Advanced Phase 4 Customization & Functionality:
  - Custom Hotkey Rebinding, Conflict Detection & Profile Import/Export
  - Clip Grouping, Color Tagging & Track Mute/Solo Presets
  - Video Thumbnail Strip & Frame Cache Manager
"""

from __future__ import annotations

from pathlib import Path

from aidub.contracts.base import Identifier
from aidub.ui.keyboard_shortcuts import NleProfile, ShortcutAction, ShortcutManager
from aidub.ui.shortcut_editor import ShortcutEditor
from aidub.ui.timeline.customization import (
    ClipColorLabel,
    TimelineCustomizationEngine,
)
from aidub.ui.timeline.model import TimelineClip, TrackId, create_default_multitrack_timeline
from aidub.ui.timeline.thumbnails import ThumbnailCacheManager

# ── 1. Custom Hotkey Rebinding & Profile Export/Import ────────────────────────


def test_shortcut_editor_conflict_detection() -> None:
    mgr = ShortcutManager(NleProfile.DEFAULT)
    editor = ShortcutEditor(mgr)

    # 'V' is bound to TOOL_SELECT
    conflict = editor.check_conflict("V", ShortcutAction.TOOL_BLADE)
    assert conflict is not None
    assert conflict.existing_action == ShortcutAction.TOOL_SELECT
    assert conflict.attempted_action == ShortcutAction.TOOL_BLADE


def test_shortcut_editor_rebind_and_export_import(tmp_path: Path) -> None:
    mgr = ShortcutManager(NleProfile.DEFAULT)
    editor = ShortcutEditor(mgr)

    # Rebind 'X' to TOOL_BLADE (no conflict)
    result = editor.rebind("X", ShortcutAction.TOOL_BLADE)
    assert result is None
    assert mgr.resolve("X") == ShortcutAction.TOOL_BLADE

    # Export custom profile
    export_file = tmp_path / "custom_shortcuts.aidub-keys"
    editor.export_profile("Studio Pro Binds", export_file)
    assert export_file.exists()

    # Import into clean editor
    clean_mgr = ShortcutManager(NleProfile.DEFAULT)
    clean_editor = ShortcutEditor(clean_mgr)
    imported = clean_editor.import_profile(export_file)

    assert imported.name == "Studio Pro Binds"
    assert clean_mgr.resolve("X") == ShortcutAction.TOOL_BLADE


# ── 2. Clip Grouping, Color Tagging & Track Presets ───────────────────────────


def test_timeline_customization_clip_grouping() -> None:
    engine = TimelineCustomizationEngine()
    group = engine.create_group("Dialogue Group A", ["c1", "c2", "c3"])

    assert group.name == "Dialogue Group A"
    assert len(group.clip_ids) == 3

    matched = engine.get_group_for_clip("c2")
    assert matched is not None
    assert matched.group_id == group.group_id


def test_timeline_customization_color_labeling() -> None:
    engine = TimelineCustomizationEngine()
    clip = TimelineClip(clip_id=Identifier("c1"), track_id=TrackId.A1, start_ms=0, duration_ms=1000)

    tagged = engine.apply_color_label(clip, ClipColorLabel.DIALOGUE)
    assert tagged.color_hex == ClipColorLabel.DIALOGUE.value


def test_timeline_customization_track_presets() -> None:
    engine = TimelineCustomizationEngine()
    tracks = create_default_multitrack_timeline()

    # Apply "dialogue_only" preset
    updated = engine.apply_track_preset(tracks, "dialogue_only")
    a1 = next(t for t in updated if t.track_id == TrackId.A1)
    a3 = next(t for t in updated if t.track_id == TrackId.A3)

    assert a1.solo is True
    assert a3.solo is False


# ── 3. Video Thumbnail Strip & Cache ──────────────────────────────────────────


def test_thumbnail_cache_manager() -> None:
    cache = ThumbnailCacheManager(max_cache_size=10)
    frame1 = cache.get_thumbnail("v_clip_01", pts_ms=1000, fps=24.0)
    assert frame1.frame_index == 24
    assert frame1.image_cache_key == "thumb_v_clip_01_24"

    strip = cache.generate_strip("v_clip_01", duration_ms=5000, interval_ms=1000)
    assert strip.clip_id == "v_clip_01"
    assert len(strip.frames) >= 5
