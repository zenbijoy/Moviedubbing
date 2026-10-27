"""Unit and Integration Tests for Phase 4: Professional Timeline Editor, Audio Mixing, Voice Management, and Export Verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from aidub.media.broadcast_exporter import (
    BroadcastMasterExporter,
)
from aidub.ui.dialogs.voice_model_dialog import VoiceModelDialog
from aidub.ui.screens.timeline_editor import (
    TimelineScreen,
    _TimelineCanvasView,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ─────────────────────────────────────────────────────────────────────────────
# 1. Timeline Canvas Editing: Trimming, Moving, Splitting, Deleting
# ─────────────────────────────────────────────────────────────────────────────


def test_canvas_view_clip_edge_detection(qapp):
    view = _TimelineCanvasView()
    clips = [
        ("V1", 0.0, 5.0, "Video Clip"),
        ("A1", 0.0, 5.0, "Audio Source"),
        ("S1", 1.0, 3.0, "Dialogue Cue"),
    ]
    view.set_clips(clips, 10.0)

    # Query S1 clip item dynamically from view._clip_items
    s1_entry = next(entry for entry in view._clip_items if entry[0]["tid"] == "S1")
    rect = s1_entry[1].boundingRect()

    # Left edge point: 2px inside left boundary
    clip_info, edge = view._get_clip_edge_at(QPointF(rect.left() + 2, rect.center().y()))
    assert edge == "left"
    assert clip_info is not None
    assert clip_info["tid"] == "S1"

    # Right edge point: 2px inside right boundary
    clip_info_r, edge_r = view._get_clip_edge_at(QPointF(rect.right() - 2, rect.center().y()))
    assert edge_r == "right"
    assert clip_info_r is not None
    assert clip_info_r["tid"] == "S1"

    # Body point: center of clip rect
    clip_info_body, edge_body = view._get_clip_edge_at(rect.center())
    assert edge_body == "body"
    assert clip_info_body is not None
    assert clip_info_body["tid"] == "S1"


def test_canvas_view_trim_left_and_right(qapp):
    view = _TimelineCanvasView()
    clips = [("A2", 2.0, 4.0, "Dubbed Take")]
    view.set_clips(clips, 10.0)
    clip_info = {"tid": "A2", "start": 2.0, "dur": 4.0, "label": "Dubbed Take"}

    # Trim right edge: reduce duration to 2.5s
    view._update_clip_timing(clip_info, new_start=2.0, new_dur=2.5)
    updated = view._clips_data[0]
    assert updated[1] == 2.0
    assert updated[2] == 2.5

    # Trim left edge: shift start to 2.5s, duration becomes 2.0s
    view._update_clip_timing(clip_info, new_start=2.5, new_dur=2.0)
    updated_left = view._clips_data[0]
    assert updated_left[1] == 2.5
    assert updated_left[2] == 2.0


def test_canvas_view_split_at_playhead(qapp):
    view = _TimelineCanvasView()
    clips = [("A2", 1.0, 4.0, "Long Dub Dialogue Take")]
    view.set_clips(clips, 10.0)

    # Set playhead at 2.5s (inside the clip from 1.0 to 5.0)
    view.set_playhead(2.5)

    emitted_clips = []
    view.clips_edited.connect(lambda c: emitted_clips.append(c))

    assert view.split_at_playhead() is True
    assert len(view._clips_data) == 2

    # First piece: 1.0s to 2.5s (duration 1.5s)
    p1 = view._clips_data[0]
    assert p1[0] == "A2"
    assert p1[1] == 1.0
    assert p1[2] == 1.5

    # Second piece: 2.5s to 5.0s (duration 2.5s)
    p2 = view._clips_data[1]
    assert p2[0] == "A2"
    assert p2[1] == 2.5
    assert p2[2] == 2.5

    assert len(emitted_clips) == 1


def test_canvas_view_delete_selected_clips(qapp):
    view = _TimelineCanvasView()
    clips = [
        ("A2", 1.0, 2.0, "Take 1"),
        ("A2", 4.0, 2.0, "Take 2"),
    ]
    view.set_clips(clips, 10.0)

    # Select the first clip
    first_item = view._clip_items[0]
    rect_item = first_item[1]
    view._selected_rects = [rect_item]

    emitted_clips = []
    view.clips_edited.connect(lambda c: emitted_clips.append(c))

    assert view.delete_selected_clips() is True
    assert len(view._clips_data) == 1
    assert view._clips_data[0][3] == "Take 2"
    assert len(emitted_clips) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. Timeline Undo/Redo Integration
# ─────────────────────────────────────────────────────────────────────────────


def test_timeline_screen_undo_redo(qapp):
    screen = TimelineScreen()
    initial_clips = [
        ("A2", 1.0, 4.0, "Dialogue Take"),
    ]
    screen._current_project_data["clips"] = list(initial_clips)
    screen.canvas_view.set_clips(initial_clips, 10.0)

    # Simulate split at 3.0s
    screen.canvas_view.set_playhead(3.0)
    screen.canvas_view.split_at_playhead()

    # Now there are 2 clips in project data
    assert len(screen._current_project_data["clips"]) == 2

    # Perform Undo -> should revert to 1 clip
    screen.undo()
    assert len(screen._current_project_data["clips"]) == 1
    assert screen._current_project_data["clips"][0][2] == 4.0

    # Perform Redo -> should restore to 2 clips
    screen.redo()
    assert len(screen._current_project_data["clips"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multitrack Audio Mixer: Levels, Mutes, Solos, Ducking, VU Meter
# ─────────────────────────────────────────────────────────────────────────────


def test_multitrack_mixer_controls_and_signals(qapp):
    screen = TimelineScreen()
    insp = screen.inspector_panel

    # Verify mixer card exists and has channel strips
    assert hasattr(insp, "mixer_card")
    assert "A1" in insp._mixer_sliders
    assert "A2" in insp._mixer_sliders
    assert "A3" in insp._mixer_sliders
    assert "master" in insp._mixer_sliders

    # Test track level changed
    insp.set_track_level("A3", 0.5)
    assert insp._mixer_sliders["A3"].value() == 50
    assert insp._mixer_val_lbls["A3"].text() == "50%"
    assert screen._mixer_levels["A3"] == 0.5

    # Test track mute toggle
    insp.set_track_mute("A1", True)
    assert insp._mixer_mute_btns["A1"].isChecked() is True
    insp._mixer_mute_btns["A1"].setChecked(False)
    assert "A1" not in screen._mixer_mutes

    # Test track solo toggle
    insp.set_track_solo("A2", True)
    assert insp._mixer_solo_btns["A2"].isChecked() is True

    # Test ducking toggle
    assert insp.chk_sidechain_duck.isChecked() is True
    insp.chk_sidechain_duck.setChecked(False)
    assert screen._sidechain_ducking_enabled is False

    # Test peak warning indicator
    insp.set_peak_warning(is_clipping=True, peak_db=1.5)
    assert "CLIP" in insp.lbl_peak_badge.text()
    insp.set_peak_warning(is_clipping=False, peak_db=-2.0)
    assert "CLIP" not in insp.lbl_peak_badge.text()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Dialogue and Subtitle Timing Synchronization & Conflict Alerts
# ─────────────────────────────────────────────────────────────────────────────


def test_timing_conflict_alert_and_fit_to_slot(qapp):
    screen = TimelineScreen()
    insp = screen.inspector_panel

    # Test 1: Dub take exceeds target slot by >15% (e.g. 2.0s slot vs 2.6s take = +30%)
    insp.set_timing_alert(slot_dur=2.0, take_dur=2.6)
    assert not insp.timing_alert_box.isHidden()
    assert "+30.0%" in insp.timing_alert_lbl.text()

    # Test 2: Dub take matches slot within tolerance -> alert hidden
    insp.set_timing_alert(slot_dur=2.0, take_dur=2.1)
    assert insp.timing_alert_box.isHidden()

    # Test 3: Fit-to-Slot action
    screen._current_project_data["clips"] = [
        ("S1", 1.0, 2.0, "Original Source Dialogue"),
        ("A2", 1.0, 2.8, "Dub Take Too Long"),
    ]
    screen.canvas_view.set_clips(screen._current_project_data["clips"], 10.0)
    screen._active_clip_info = {
        "tid": "A2",
        "start": 1.0,
        "dur": 2.8,
        "label": "Dub Take Too Long",
    }

    # Trigger fit-to-slot
    screen._on_fit_to_slot()

    # Active clip and timeline clip should now match source slot duration (2.0s)
    assert screen._active_clip_info["dur"] == 2.0
    matching_clip = next(c for c in screen.canvas_view._clips_data if c[0] == "A2")
    assert matching_clip[2] == 2.0


def test_nudge_timing(qapp):
    screen = TimelineScreen()
    screen._current_project_data["clips"] = [
        ("A2", 1.0, 2.0, "Dub Take"),
    ]
    screen.canvas_view.set_clips(screen._current_project_data["clips"], 10.0)
    screen._active_clip_info = {
        "tid": "A2",
        "start": 1.0,
        "dur": 2.0,
        "label": "Dub Take",
    }

    # Nudge forward by +100ms (+0.1s)
    screen._on_nudge_timing(0.1)
    assert screen._active_clip_info["start"] == 1.1

    matching_clip = next(c for c in screen.canvas_view._clips_data if c[0] == "A2")
    assert matching_clip[1] == 1.1


# ─────────────────────────────────────────────────────────────────────────────
# 5. Voice Management: Available Providers, Languages, Rate/Pitch, Caching
# ─────────────────────────────────────────────────────────────────────────────


def test_voice_model_dialog_languages_and_voices(qapp):
    dlg = VoiceModelDialog(target_language="bn")

    # Verify real language options
    assert dlg.lang_combo.count() >= 10
    lang_codes = [dlg.lang_combo.itemData(i) for i in range(dlg.lang_combo.count())]
    assert "bn" in lang_codes
    assert "en" in lang_codes
    assert "hi" in lang_codes

    # Verify Bengali voices match Edge-TTS real voices
    assert dlg.voice_combo.count() >= 1
    voices = [dlg.voice_combo.itemText(i) for i in range(dlg.voice_combo.count())]
    assert any("bn-BD-NabanitaNeural" in v for v in voices)

    # Test Rate & Pitch getters
    dlg.rate_slider.setValue(15)
    assert dlg.get_selected_rate() == "+15%"

    dlg.pitch_slider.setValue(-5)
    assert dlg.get_selected_pitch() == "-5Hz"

    # Test configuration dictionary export
    config = dlg.get_configuration()
    assert config["language"] == "bn"
    assert config["rate"] == "+15%"
    assert config["pitch"] == "-5Hz"


def test_voice_cloning_authorization_requirement(qapp):
    dlg = VoiceModelDialog(current_engine="chatterbox")

    # Uncheck authorization checkbox
    dlg.chk_cloning_auth.setChecked(False)

    # Attempt to accept without consent -> should be blocked
    with (
        patch.object(dlg, "done") as mock_done,
        patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn,
    ):
        dlg.accept()
        mock_done.assert_not_called()
        mock_warn.assert_called_once()

    # With consent checked -> accept succeeds
    dlg.chk_cloning_auth.setChecked(True)
    with patch.object(dlg, "done") as mock_done:
        dlg.accept()
        mock_done.assert_called_once()


def test_voice_audition_stable_cache_key(tmp_path: Path):
    text = "আমি এখানে সিনেমা ডাবিং করতে এসেছি।"
    engine = "edge_tts"
    lang = "bn"
    voice = "bn-BD-NabanitaNeural"
    rate = "+0%"
    pitch = "+0Hz"
    emotion = "neutral"

    # Stable SHA-256 identifier calculation
    key1 = hashlib.sha256(
        f"{engine}:{lang}:{voice}:{rate}:{pitch}:{emotion}:{text}".encode()
    ).hexdigest()
    key2 = hashlib.sha256(
        f"{engine}:{lang}:{voice}:{rate}:{pitch}:{emotion}:{text}".encode()
    ).hexdigest()
    assert key1 == key2

    # Changing rate invalidates the cache key
    key_diff_rate = hashlib.sha256(
        f"{engine}:{lang}:{voice}:+10%:{pitch}:{emotion}:{text}".encode()
    ).hexdigest()
    assert key1 != key_diff_rate

    # Changing text invalidates the cache key
    key_diff_text = hashlib.sha256(
        f"{engine}:{lang}:{voice}:{rate}:{pitch}:{emotion}:অন্য লাইন".encode()
    ).hexdigest()
    assert key1 != key_diff_text


# ─────────────────────────────────────────────────────────────────────────────
# 6. Final Export: Overwrite Protection and Output Verification
# ─────────────────────────────────────────────────────────────────────────────


def test_export_prevents_overwriting_source_video(tmp_path: Path):
    vid = tmp_path / "movie.mp4"
    vid.write_bytes(b"sample video")
    aud = tmp_path / "audio.wav"
    aud.write_bytes(b"sample audio")

    # Output path is identical to source video path
    with pytest.raises(ValueError, match="cannot overwrite source video"):
        BroadcastMasterExporter.export(
            video_path=vid,
            audio_path=aud,
            output_path=vid,
        )


def test_export_verification_catches_missing_streams(tmp_path: Path):
    vid = tmp_path / "movie.mp4"
    vid.write_bytes(b"sample video")
    aud = tmp_path / "audio.wav"
    aud.write_bytes(b"sample audio")
    out = tmp_path / "out_audio_only.mp4"

    def fake_run(cmd: list[str]):
        out.write_bytes(b"simulated output")
        return MagicMock(returncode=0)

    # Simulate probe returning only an audio stream (no video stream)
    fake_probe_audio_only = {
        "streams": [{"codec_type": "audio", "codec_name": "aac", "channels": 2}],
        "format": {"duration": "5.0"},
    }

    with (
        patch("aidub.media.broadcast_exporter._run", side_effect=fake_run),
        patch("aidub.media.broadcast_exporter.probe", return_value=fake_probe_audio_only),
        pytest.raises(RuntimeError, match="has no video stream"),
    ):
        BroadcastMasterExporter.export(
            video_path=vid,
            audio_path=aud,
            output_path=out,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Project Persistence: Mixer and Timeline State Round-Trip
# ─────────────────────────────────────────────────────────────────────────────


def test_project_mixer_persistence_roundtrip(tmp_path: Path, qapp):
    screen = TimelineScreen()
    screen._mixer_levels = {"A1": 0.9, "A2": 1.2, "A3": 0.4, "A4": 0.8, "A5": 0.6, "master": 1.0}
    screen._mixer_mutes = {"A1"}
    screen._mixer_solos = {"A2"}
    screen._sidechain_ducking_enabled = True
    screen._sidechain_ducking_depth = 14.0

    # Mock opened project package
    opened_mock = MagicMock()
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir(parents=True)
    opened_mock.paths.transcripts = transcripts_dir
    opened_mock.project.name = "Test Project"
    opened_mock.project.project_id = "proj_test_1"

    # Save to project
    success = screen.save_to_project(opened=opened_mock)
    assert success is True

    state_file = transcripts_dir / "timeline_state.json"
    assert state_file.is_file()

    import json

    saved_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "mixer" in saved_data
    assert saved_data["mixer"]["levels"]["A2"] == 1.2
    assert "A1" in saved_data["mixer"]["mutes"]
    assert "A2" in saved_data["mixer"]["solos"]
    assert saved_data["mixer"]["ducking_depth"] == 14.0
