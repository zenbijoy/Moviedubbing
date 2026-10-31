"""
Comprehensive Unit Tests for Real-time Working Manual Dubbing Studios & NLE Tools.

Verifies:
  - AuditionService: real-time in-memory clip playback & voice synthesis.
  - VoiceExchangerDialog & Screen: real-time live auditioning with pitch/formant shifting.
  - ProEmotionStudioDialog & Screen: live dramatic performance auditioning.
  - VoiceEditorScreen: transport controls, ADR retake loading, live DSP auditioning.
  - ManualLipSyncScreen: Actor Mouth kinematics rendering and 24fps scrubbing.
  - QcDashboardScreen: automatic timeline project auditing.
  - TimelineScreen: NLE Razor Blade split and Ripple Delete with undo history.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from aidub.domain.viseme import VisemeGeometry, VisemeGroup, VisemeKeyframe, VisemeTimeline
from aidub.media.audition_service import AuditionService
from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine
from aidub.ui.dialogs.pro_emotion_studio_dialog import ProEmotionStudioDialog
from aidub.ui.dialogs.voice_exchanger_dialog import VoiceExchangerDialog
from aidub.ui.screens.emotion_editor import EmotionEditorScreen
from aidub.ui.screens.manual_lipsync import ManualLipSyncScreen, _ActorMouthPreviewWidget
from aidub.ui.screens.qc_dashboard import QcDashboardScreen
from aidub.ui.screens.timeline_editor import TimelineScreen
from aidub.ui.screens.voice_editor import VoiceEditorScreen
from aidub.ui.screens.voice_exchanger import VoiceExchangerScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_audition_service_clip_playback(qapp):
    svc = AuditionService()
    sig = np.zeros(4410, dtype=np.float32)
    clip = AudioClipData(samples=sig, sample_rate=44100)

    path = svc.play_clip(clip)
    assert path != ""
    assert Path(path).is_file()
    assert svc.is_playing is True

    svc.stop()
    assert svc.is_playing is False
    svc.cleanup()


def test_audition_service_synthesize_fallback(qapp):
    svc = AuditionService()
    done_flag = []

    # Test synthesis with fallback handling
    svc.synthesize_and_play(
        text="Hello test",
        voice_id="test_voice",
        on_done=lambda p: done_flag.append(p),
    )
    svc.stop()
    svc.cleanup()


def test_voice_exchanger_dialog_realtime_audition(qapp):
    dlg = VoiceExchangerDialog(
        character_name="Hero",
        current_voice_id="bn-BD-PradeepNeural",
        target_language="bn",
    )
    assert hasattr(dlg, "audition_btn")

    # Click audition: should trigger real playback instead of popup
    with patch.object(dlg, "_selected_voice", MagicMock(display_name="Pradeep", voice_id="bn-BD-PradeepNeural", language="bn")):
        dlg._audition_voice()
        assert dlg.audition_btn.text() == "⏹ Stop Audition"
        assert hasattr(dlg, "_audition")

        # Clicking again stops audition
        dlg._audition_voice()
        assert dlg.audition_btn.text() == "▶ Audition Sample"

    dlg.reject()


def test_voice_exchanger_screen_audition(qapp):
    scr = VoiceExchangerScreen(cue_ids=["cue_1", "cue_2"])
    assert hasattr(scr, "btn_audition")
    assert scr.btn_audition.text() == "▶ Audition Selected Voice"

    scr._on_audition_clicked()
    assert scr.btn_audition.text() == "⏹ Stop Audition"

    scr._on_audition_clicked()
    assert scr.btn_audition.text() == "▶ Audition Selected Voice"


def test_pro_emotion_studio_dialog_audition(qapp):
    dlg = ProEmotionStudioDialog(
        dialogue_text="আমি বিচার চাই!",
        character_name="Actor_1",
    )
    assert hasattr(dlg, "audition_btn")

    dlg._audition_emotion()
    assert dlg.audition_btn.text() == "⏹ Stop Audition"

    dlg._audition_emotion()
    assert dlg.audition_btn.text() == "🔊 Audition Emotion Audio"

    dlg.reject()


def test_emotion_editor_screen_audition(qapp):
    scr = EmotionEditorScreen(initial_text="Testing dramatic line")
    assert hasattr(scr, "btn_audition")

    scr._on_audition_clicked()
    assert scr.btn_audition.text() == "⏹ Stop Audition"

    scr._on_audition_clicked()
    assert scr.btn_audition.text() == "🔊 Audition Live Speech with Emotion"


def test_voice_editor_screen_transport_and_dsp(qapp, tmp_path: Path):
    # Create test WAV
    wav_p = tmp_path / "test_dialogue.wav"
    t = np.linspace(0, 0.5, 22050, endpoint=False)
    sig = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    clip = AudioClipData(samples=sig, sample_rate=44100)
    ProAudioDspEngine.save_wav(clip, wav_p)

    scr = VoiceEditorScreen(cue_id="cue_test", audio_path=str(wav_p))
    assert hasattr(scr, "btn_play_take")
    assert hasattr(scr, "btn_stop_take")
    assert scr.current_clip is not None

    # Test DSP processing and audition
    scr._on_apply_dsp_rack()
    assert scr.btn_play_take.text() == "⏹ Stop Audition"

    scr._on_stop_take_clicked()
    assert scr.btn_play_take.text() == "▶ Audition Take"

    # Test real ADR retake registration
    with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=("", "")):
        scr._on_record_new_take()
    assert scr.takes_list.count() >= 2


def test_manual_lipsync_mouth_kinematics(qapp):
    preview = _ActorMouthPreviewWidget()
    preview.set_viseme(
        VisemeGroup.BILABIAL,
        VisemeGeometry(openness=0.0, width=0.5, lip_protrusion=0.1, teeth_visible=False),
    )
    assert preview._viseme_group == VisemeGroup.BILABIAL

    scr = ManualLipSyncScreen()
    assert hasattr(scr, "mouth_preview")
    assert hasattr(scr, "btn_play")
    assert hasattr(scr, "lbl_timecode")

    # Scrub playhead
    scr._on_seek_playhead(0.5)
    assert scr._current_time_s == 0.5

    # Toggle animation playback
    scr._toggle_playback()
    assert scr._playback_timer.isActive()
    scr._toggle_playback()
    assert not scr._playback_timer.isActive()


def test_qc_dashboard_project_audit(qapp):
    scr = QcDashboardScreen()
    project_data = {
        "clips": [
            ("A1", 0.0, 3.0, "Source Line", 0.9),
            ("A2", 0.0, 3.1, "Dubbed Line", 0.85),
            ("S1", 0.0, 0.1, "Too short", 0.9),  # timing underflow
            ("S2", 0.0, 3.0, "", None),  # missing text
        ]
    }
    scr.audit_timeline_project(project_data)
    issues = scr.qc_service.get_blockers() + scr.qc_service.get_warnings()
    assert len(issues) >= 2
    types = [i.issue_type.value for i in issues]
    assert "timing_underflow" in types
    assert "missing_subtitle_text" in types


def test_timeline_screen_blade_and_ripple_delete(qapp):
    scr = TimelineScreen()
    scr._current_project_data["clips"] = [
        ("A2", 0.0, 4.0, "Long Dialogue", 0.9),
        ("A2", 5.0, 3.0, "Second Dialogue", 0.9),
    ]
    scr._current_project_data["duration"] = 10.0

    # Test Blade Split at playhead = 2.0s
    scr.canvas_view._playhead_pos = 2.0
    scr._apply_blade_split()

    clips = scr._current_project_data["clips"]
    assert len(clips) == 3
    assert clips[0][2] == 2.0  # Part 1 dur
    assert clips[1][1] == 2.0  # Part 2 start
    assert clips[1][2] == 2.0  # Part 2 dur
    assert len(scr._edit_history) >= 1

    # Test Ripple Delete on Part 1
    scr._active_clip_info = {"tid": "A2", "start": 0.0, "dur": 2.0}
    scr._apply_ripple_delete()

    clips_after = scr._current_project_data["clips"]
    assert len(clips_after) == 2
    # Downstream clips should be shifted left by 2.0s
    assert clips_after[0][1] == 0.0  # Part 2 shifted from 2.0 to 0.0
    assert clips_after[1][1] == 3.0  # Second dialogue shifted from 5.0 to 3.0
