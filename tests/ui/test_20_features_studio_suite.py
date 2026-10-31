"""
Unit test suite verifying all 20 Professional Movie Dubbing Features.

Covers:
  1. ADR Punch-In Retake Manager & A/B Comparison (AdrPunchInDialog)
  2. Voice Clone Studio Profile Builder (VoiceCloneStudioDialog)
  3. Visual Emotion Timeline Curve Keyframe Editor (_EmotionCurveWidget, EmotionCurve)
  4. Bangla Emotion Presets & Intensity Scaling (BanglaEmotionPresets, EmotionIntensityController)
  5. Sidechain Ducking in Audio Mixer (SidechainDucker, AudioMixerEngine)
  6. Auto Gain Rider in Audio Mixer (AutoGainRider, AudioMixerEngine)
  7. Broadcast QC Report Generation & Export (QCReportGenerator, QCCheck, QcDashboardScreen)
  8. Caption Style Presets & ASS/CSS Export (CaptionStyle)
  9. Auto-Captioning via Audio Energy Envelope (AutoCaptioner, SubtitleCaptionStudioDialog)
  10. Lip-Sync Inspector ROI & Viseme Alignment (LipSyncInspectorDialog)
  11. Voice Consistency Drift Monitoring across takes (VoiceConsistencyChecker)
  12. Speaker Cosine Similarity Matrix (SpeakerSimilarity)
  13. Beat-Sync Detection & Cut Snapping (BeatSync, AudioDspToolsDialog)
  14. Center-Channel Vocal & Accompaniment Isolation (VocalIsolator, AudioDspToolsDialog)
  15. Speed Ramp & WSOLA Pitch-Preserved Time Stretch (SpeedRamp, AudioDspToolsDialog)
  16. Reverb Matcher RT60 Estimation & Decay Matching (ReverbMatcher, AudioDspToolsDialog)
  17. System Monitor Dock Widget (SystemMonitorDockWidget)
  18. Export Delivery Preset Selector & Target LUFS Search (ExportPresetManager, ExportDeliveryDialog)
  19. Subtitle Timing Shift, Scale, and Clamp (SubtitleTimingEngine, SubtitleCaptionStudioDialog)
  20. Batch Dub Runner Queue Processor with Dynamic ETA (BatchDubber, BatchDubRunnerDialog)
"""

from __future__ import annotations

import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from aidub.application.audio.beat_sync import BeatSync
from aidub.application.audio.reverb_matcher import ReverbMatcher
from aidub.application.audio.speed_ramp import SpeedRamp
from aidub.application.audio.vocal_isolator import VocalIsolator
from aidub.application.captions.auto_captioner import AutoCaptioner
from aidub.application.captions.caption_style import CaptionStyle
from aidub.application.emotion.bangla_presets import BanglaEmotionPresets
from aidub.application.emotion.emotion_curve import EmotionCurve, EmotionCurvePoint
from aidub.application.emotion.intensity_controller import EmotionIntensityController
from aidub.application.export.preset_manager import ExportPresetManager
from aidub.application.qc.qc_report import QCCheck, QCReportGenerator
from aidub.application.subtitles.timing_engine import SubtitleCue, SubtitleTimingEngine
from aidub.application.voice.consistency_checker import VoiceConsistencyChecker
from aidub.application.voice.speaker_similarity import SpeakerSimilarity
from aidub.media.pro_audio_editor import AudioClipData
from aidub.ui.dialogs.adr_punch_in_dialog import AdrPunchInDialog
from aidub.ui.dialogs.audio_dsp_tools_dialog import AudioDspToolsDialog
from aidub.ui.dialogs.batch_dub_runner_dialog import BatchDubRunnerDialog
from aidub.ui.dialogs.export_delivery_dialog import ExportDeliveryDialog
from aidub.ui.dialogs.lipsync_inspector_dialog import LipSyncInspectorDialog
from aidub.ui.dialogs.subtitle_caption_studio_dialog import SubtitleCaptionStudioDialog
from aidub.ui.dialogs.voice_clone_studio_dialog import VoiceCloneStudioDialog
from aidub.ui.mixer import AudioMixerConsoleDialog, AudioMixerEngine, ChannelStripWidget
from aidub.ui.screens.emotion_editor import EmotionEditorScreen
from aidub.ui.screens.qc_dashboard import QcDashboardScreen
from aidub.ui.screens.system_monitor import SystemMonitorDockWidget, SystemMonitorScreen
from aidub.ui.timeline.model import TrackId


@pytest.fixture(autouse=True)
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ─── FEATURE 1: ADR Punch-In & Retake Comparison ────────────────────────────
def test_feature_01_adr_punch_in_and_take_compare() -> None:
    clip = AudioClipData.synthesize_speech_like(duration=3.0, sample_rate=44100)
    dlg = AdrPunchInDialog(base_clip=clip, cue_id="cue_test_01", punch_in_sec=0.5, punch_out_sec=1.5)
    assert len(dlg.takes) == 1
    assert dlg.combo_takes.count() == 1

    # Record Take 2
    dlg._execute_punch_in()
    assert len(dlg.takes) == 2
    assert dlg.combo_takes.count() == 2

    # A/B comparison
    dlg._compare_takes()
    assert "A/B Compare" in dlg.status_lbl.text()


# ─── FEATURE 2, 11, 12: Voice Clone Studio, Consistency & Cosine Matrix ──────
def test_feature_02_11_12_voice_clone_studio_and_speaker_similarity() -> None:
    dlg = VoiceCloneStudioDialog()
    assert dlg.combo_provider.count() >= 3
    assert dlg.table_matrix.rowCount() == 4

    # Speaker similarity metric
    e1 = [0.8, 0.7, 0.6]
    e2 = [0.81, 0.69, 0.61]
    cos = SpeakerSimilarity.cosine(e1, e2)
    assert cos > 0.98

    # Voice consistency check
    checker = VoiceConsistencyChecker(threshold=0.85)
    res = checker.check([e1, e2])
    assert res["consistent"] is True
    assert res["min_similarity"] > 0.85

    # Run check in UI
    dlg._run_consistency_check()
    assert "CONSISTENT" in dlg.lbl_badge.text()

    # Audition test synthesis
    dlg._audition_test()
    assert "Auditioning voice clone" in dlg.status_lbl.text()


# ─── FEATURE 3, 4: Emotion Timeline Curve & Bangla Emotion Director ─────────
def test_feature_03_04_emotion_curve_and_bangla_presets() -> None:
    screen = EmotionEditorScreen()
    assert hasattr(screen, "curve_widget")
    assert screen.combo_presets.count() > 10

    # Verify Bangla preset presence
    bangla_items = [screen.combo_presets.itemText(i) for i in range(screen.combo_presets.count()) if "Bangla" in screen.combo_presets.itemText(i)]
    assert len(bangla_items) >= 5

    # Trigger a Bangla preset
    screen.combo_presets.setCurrentIndex(screen.combo_presets.findText(bangla_items[0]))
    assert screen.current_spec is not None

    # Test EmotionCurve mathematical evaluation
    curve = EmotionCurve([EmotionCurvePoint(0.0, 0.5), EmotionCurvePoint(1.0, 1.5)])
    assert curve.evaluate(0.0) == 0.5
    assert curve.evaluate(0.5) == 1.0
    assert curve.evaluate(1.0) == 1.5

    # Test Curve Changed event propagation
    new_curve = EmotionCurve([EmotionCurvePoint(0.0, 0.3), EmotionCurvePoint(0.5, 1.8), EmotionCurvePoint(1.0, 0.9)])
    screen.curve_widget.curve_changed.emit(new_curve)
    assert screen.current_spec.intensity == 1.8
    assert "180%" in screen.lbl_intensity_val.text()


# ─── FEATURE 5, 6: Mixer Sidechain Ducking & Auto Gain Rider ─────────────────
def test_feature_05_06_mixer_sidechain_and_auto_gain_rider() -> None:
    mixer = AudioMixerEngine()
    t_id = TrackId.A2
    music_clip = AudioClipData.synthesize_tone(frequency=100.0, duration=1.0, sample_rate=44100)
    dialogue_clip = AudioClipData.synthesize_speech_like(duration=1.0, sample_rate=44100)

    # Enable AutoGainRider
    mixer.set_auto_gain_rider(t_id, enabled=True, target_rms=0.15)
    ch = mixer.get_channel(t_id)
    assert ch is not None
    assert ch.gain_rider_enabled is True

    # Enable Sidechain Ducking
    mixer.set_sidechain_ducking(t_id, enabled=True, duck_db=-14.0)
    ch = mixer.get_channel(t_id)
    assert ch.ducking_enabled is True
    assert ch.ducking_depth_db == -14.0

    # Process audio through mixer DSP chain
    out = mixer.process_channel_audio(t_id, clip=music_clip, dialogue_sidechain_clip=dialogue_clip)
    assert out.samples.size == music_clip.samples.size
    assert out.sample_rate == music_clip.sample_rate


# ─── FEATURE 7: QC Report Generator & Compliance Export ──────────────────────
def test_feature_07_qc_report_generator_and_export() -> None:
    checks = [
        QCCheck(name="Loudness", passed=True, value=-24.0, threshold=-24.0),
        QCCheck(name="True Peak", passed=True, value=-1.5, threshold=-1.0),
        QCCheck(name="LipSync", passed=False, value=65.0, threshold=45.0),
    ]
    report = QCReportGenerator.generate(checks)
    assert report["total"] == 3
    assert report["passed"] == 2
    assert report["failed"] == 1
    assert round(report["pass_rate"], 1) == 66.7
    assert report["overall"] == "FAIL"

    screen = QcDashboardScreen()
    rep = screen.generate_qc_report()
    assert "total" in rep
    assert "overall" in rep

    # Test Auto-Fix compliance issues
    screen.auto_fix_all_defects()
    assert "Auto-fixed" in screen.status_label.text()


# ─── FEATURE 8, 9, 19: Subtitle Studio, AutoCaptioner, Timing Engine ────────
def test_feature_08_09_19_subtitle_caption_studio(tmp_path: Any) -> None:
    # 8. Caption Style
    styles = CaptionStyle.list()
    assert "bold_white" in styles
    assert "yellow_pop" in styles
    ass_line = CaptionStyle.to_ass_style("bold_white")
    assert ass_line.startswith("Style:")

    # 19. Subtitle Timing Engine
    cues = [SubtitleCue(1.0, 2.5, "প্রথম লাইন"), SubtitleCue(3.0, 4.0, "দ্বিতীয় লাইন")]
    shifted = SubtitleTimingEngine.shift(cues, delta_s=0.5)
    assert shifted[0].start_s == 1.5
    assert shifted[0].end_s == 3.0

    scaled = SubtitleTimingEngine.scale(cues, factor=2.0)
    assert scaled[0].start_s == 2.0

    clamped = SubtitleTimingEngine.clamp([SubtitleCue(-0.5, 1.0, "নেগেটিভ")], min_s=0.0)
    assert clamped[0].start_s == 0.0

    # 9. Auto-Captioner & Dialog
    dlg = SubtitleCaptionStudioDialog(cues=cues)
    dlg._run_auto_caption()
    assert len(dlg.cues) > 0

    # Save deliverable SRT to file
    out_srt = tmp_path / "deliverable.srt"
    dlg._save_to_file(out_srt)
    assert out_srt.exists()
    assert "আমি তোমাকে" in out_srt.read_text(encoding="utf-8")


# ─── FEATURE 10: LipSync Inspector ROI & Viseme Aligner ─────────────────────
def test_feature_10_lipsync_inspector_dialog() -> None:
    dlg = LipSyncInspectorDialog(total_duration_s=4.0)
    assert hasattr(dlg, "_roi_widget")
    assert hasattr(dlg, "_timeline_widget")


# ─── FEATURE 13, 14, 15, 16: Advanced Audio DSP Suite ───────────────────────
def test_feature_13_14_15_16_audio_dsp_tools_dialog() -> None:
    clip = AudioClipData.synthesize_speech_like(duration=2.5, sample_rate=44100)
    dlg = AudioDspToolsDialog(clip=clip)

    # 13. Beat Sync
    beats = BeatSync.detect_beats(clip.samples, clip.sample_rate)
    dlg._run_beat_detection()
    assert len(dlg.detected_beats) > 0
    snapped = BeatSync.snap_to_beat(1.1, [0.5, 1.0, 1.5])
    assert snapped == 1.0

    # 14. Vocal Isolation
    dlg._isolate_dialogue()
    assert dlg.processed_clip is not None
    dlg._isolate_music()
    assert dlg.processed_clip is not None

    # 15. Speed Ramp & WSOLA
    dlg._render_speed_stretch()
    assert dlg.processed_clip is not None
    dlg._render_speed_ramp()
    assert dlg.processed_clip is not None

    # 16. Reverb Matcher RT60
    rt60 = ReverbMatcher.estimate_rt60(clip.samples, clip.sample_rate)
    decay = ReverbMatcher.suggested_decay(rt60)
    assert decay >= 0.1
    dlg._analyze_reverb()
    assert "RT60" in dlg.lbl_reverb_results.text()

    # Audition processed slice
    dlg._audition_processed()
    assert "Auditioning" in dlg.status_lbl.text()


# ─── FEATURE 17: System Monitor Dock Widget ─────────────────────────────────
def test_feature_17_system_monitor_dock_widget() -> None:
    dock = SystemMonitorDockWidget()
    assert dock.widget() is not None
    assert isinstance(dock.monitor_screen, SystemMonitorScreen)


# ─── FEATURE 18: Export Delivery Presets & Loudness Search ───────────────────
def test_feature_18_export_delivery_presets() -> None:
    mgr = ExportPresetManager()
    keys = mgr.list_keys()
    assert "netflix" in keys
    assert "youtube" in keys

    # Target loudness search
    netflix_matches = mgr.for_loudness(-24.0)
    assert len(netflix_matches) >= 1
    assert netflix_matches[0].name.lower() == "netflix"

    dlg = ExportDeliveryDialog(preset_manager=mgr)
    assert dlg.spin_lufs.value() == -24.0
    dlg._find_by_loudness()
    assert "matching presets" in dlg.lbl_status.text()


# ─── FEATURE 20: Batch Dub Runner Queue Processor with Dynamic ETA ──────────
def test_feature_20_batch_dub_runner_queue_and_eta() -> None:
    dlg = BatchDubRunnerDialog()
    assert len(dlg.cues) == 5
    assert dlg.table_cues.rowCount() == 5

    # Run batch dubbing queue
    dlg._run_batch()
    assert len(dlg.results) == 5
    assert dlg.btn_apply.isEnabled() is True
    assert dlg.prog_bar.value() == 100

    # Audition selected row
    dlg.table_cues.setCurrentCell(0, 0)
    dlg._audition_selected_cue()
    assert "Auditioning cue" in dlg.lbl_eta.text()


# ─── FEATURE 09: Cubase MixConsole F3 Rack Dialog & Channel Strips ──────────
def test_feature_09_mixer_console_dialog_and_channel_strip() -> None:
    mixer = AudioMixerEngine()
    dlg = AudioMixerConsoleDialog(mixer=mixer)
    assert len(dlg.strips) == 4

    strip = dlg.strips[TrackId.A1]
    assert strip.track_id == TrackId.A1

    # Mute toggle test
    strip.btn_mute.click()
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None
    assert ch.muted is True

    # Solo toggle test
    strip.btn_solo.click()
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None
    assert ch.solo is True

    # AutoGainRider UI toggle
    strip.chk_rider.setChecked(True)
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None
    assert ch.gain_rider_enabled is True

    # Sidechain Ducking UI toggle
    strip.chk_ducking.setChecked(True)
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None
    assert ch.ducking_enabled is True
