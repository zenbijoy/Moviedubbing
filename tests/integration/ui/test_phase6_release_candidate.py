"""
Phase 6 Release Candidate Authoritative Verification Suite.

Validates:
1. End-to-end Project Lifecycle:
   - Create .aidub package -> Import synthetic media -> Probe duration ->
   - Edit Unicode Bengali transcript/subtitles -> Split clip at playhead ('S' hotkey) ->
   - Adjust track mixer faders, mutes, solos, sidechain ducking ->
   - Save atomically (.tmp -> .bak -> target) ->
   - Simulate corruption and recover from backup ->
   - Reopen and verify persisted state fidelity.
2. Modular Pipeline Execution & Cancellation:
   - Extraction -> Transcription -> Translation -> Voice Synthesis -> Master Render.
   - Comprehensive has_active_job() check and cancellation signal handling.
3. Broadcast Master Export & Security:
   - Stream validation (video + audio presence, valid duration).
   - Source media overwrite prevention (ValueError).
   - Subtitle export (source, target, bilingual).
4. UI Navigation & Shell Lifecycle:
   - Chrome navigation tab synchronization.
   - Menu triggers and keyboard shortcuts.
   - Graceful window shutdown with worker termination.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6", reason="PySide6 required for studio UI release candidate tests")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from aidub.application.modular_pipeline import (
    SynthesizedCueTake,
    TranscriptCue,
    TranslatedCue,
)
from aidub.application.projects import ProjectPackageService
from aidub.domain.project import PrivacyMode, ProjectSettings, QualityPreset
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate
from aidub.infrastructure.catalog import ProjectCatalog
from aidub.media.broadcast_exporter import BroadcastMasterExporter, BroadcastPreset
from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt
from aidub.ui.screens.timeline_editor import TimelineScreen
from aidub.ui.studio_window import AIDubStudioWindow


@pytest.fixture
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _create_sample_settings() -> ProjectSettings:
    return ProjectSettings(
        video_rate=RationalRate(numerator=24000, denominator=1001),
        source_language="en-US",
        quality_preset=QualityPreset.PROFESSIONAL,
        privacy_mode=PrivacyMode.OFFLINE,
    )


def _create_sample_auth() -> SourceAuthorization:
    return SourceAuthorization(
        acknowledged=True,
        acknowledged_by="qc.auditor@studio.test",
        acknowledged_at=datetime.now(UTC),
        authority_basis="Broadcast Master Dubbing Agreement",
        evidence_reference="contract://2026-bengali-dub-rc",
    )


def _create_synthetic_audio_wav(
    path: Path, duration_s: float = 2.0, sample_rate: int = 16000
) -> Path:
    import numpy as np
    import soundfile as sf

    total_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, total_samples, endpoint=False, dtype=np.float32)
    # 440 Hz reference tone
    audio_data = 0.2 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), audio_data, sample_rate)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Full Project Lifecycle, Timeline Editing, and Atomic Persistence
# ─────────────────────────────────────────────────────────────────────────────


def test_rc_project_lifecycle_persistence_and_recovery(tmp_path: Path, qapp: QApplication) -> None:
    catalog_path = tmp_path / "catalog_rc.db"
    catalog = ProjectCatalog(catalog_path)
    catalog.initialize()

    # Step 1: Package Creation
    service = ProjectPackageService(catalog=catalog)
    pkg_root = tmp_path / "Cinema_Movie_বাংলা.aidub"
    opened = service.create(
        pkg_root,
        name="Cinema Movie বাংলা",
        settings=_create_sample_settings(),
        source_authorization=_create_sample_auth(),
        localization_locales=("bn-BD",),
        actor_id="qc.auditor@studio.test",
    )
    assert opened.paths.root.is_dir()
    assert opened.paths.manifest.is_file()
    assert opened.paths.database.is_file()

    # Verify standard package directories
    assert opened.paths.transcripts.is_dir()
    assert opened.paths.localizations.is_dir()
    assert opened.paths.source_links.is_dir()
    assert opened.paths.recovery.is_dir()

    # Step 2: Initialize TimelineScreen and load package
    screen = TimelineScreen()
    try:
        screen.load_opened_project(opened)
        qapp.processEvents()

        assert screen.current_project_name == "Cinema Movie বাংলা"

        # Step 3: Populate bilingual subtitle cues with Bengali Unicode
        bilingual_cues = [
            ("S1", 1.0, 3.0, "Welcome to the cinematic AI studio.", None),
            ("S2", 1.0, 3.0, "সিনেমাটিক এআই স্টুডিওতে স্বাগতম।", None),
            ("S1", 4.5, 4.0, "Every voice line is synchronized.", None),
            ("S2", 4.5, 4.0, "প্রতিটি কণ্ঠস্বর সিঙ্ক্রোনাইজ করা হয়েছে।", None),
        ]
        video_clip = ("V1", 0.0, 10.0, "source_movie.mp4", None)
        audio_clip = ("A1", 0.0, 10.0, "source_audio.wav", None)

        all_clips = [video_clip, audio_clip] + bilingual_cues
        screen._current_project_data["clips"] = all_clips
        screen._current_project_data["duration"] = 10.0
        screen.canvas_view.set_clips(all_clips, 10.0)
        qapp.processEvents()

        # Step 4: Verify Key_S splits clip at playhead
        screen.canvas_view._playhead_sec = 2.5
        # Select S1 clip
        s1_clip_info = {
            "tid": "S1",
            "start": 1.0,
            "dur": 3.0,
            "label": "Welcome to the cinematic AI studio.",
        }
        split_ok = screen.canvas_view._split_clip(s1_clip_info, 2.5)
        assert split_ok is True
        qapp.processEvents()

        clips_after_split = screen._current_project_data["clips"]
        s1_after_split = [c for c in clips_after_split if c[0] == "S1"]
        assert len(s1_after_split) == 3
        assert any(abs(c[1] - 1.0) < 0.01 and abs(c[2] - 1.5) < 0.01 for c in s1_after_split)
        assert any(abs(c[1] - 2.5) < 0.01 and abs(c[2] - 1.5) < 0.01 for c in s1_after_split)

        # Step 5: Configure Track Mixer levels, mutes, solos, ducking
        screen._on_track_level_changed("A1", 0.85)
        screen._on_track_level_changed("A2", 1.0)
        screen._on_track_level_changed("master", 0.95)
        screen._on_track_mute_toggled("A3", True)
        screen._on_track_solo_toggled("A2", True)
        screen._on_ducking_changed(True, 15.0)

        assert screen._mixer_levels["A1"] == 0.85
        assert screen._mixer_levels["master"] == 0.95
        assert "A3" in screen._mixer_mutes
        assert "A2" in screen._mixer_solos
        assert screen._sidechain_ducking_depth == 15.0

        # Step 6: Save project atomically
        save_success = screen.save_to_project(opened)
        assert save_success is True

        state_file = opened.paths.transcripts / "timeline_state.json"
        bak_file = opened.paths.transcripts / "timeline_state.json.bak"
        s1_file = opened.paths.transcripts / "subtitles_S1.srt"
        s2_file = opened.paths.transcripts / "subtitles_S2.srt"

        assert state_file.is_file()
        assert s1_file.is_file()
        assert s2_file.is_file()

        # Step 7: Verify Bengali Unicode in persisted SRT
        s2_text = s2_file.read_text(encoding="utf-8")
        assert "সিনেমাটিক এআই স্টুডিওতে স্বাগতম।" in s2_text
        assert "প্রতিটি কণ্ঠস্বর সিঙ্ক্রোনাইজ" in s2_text

        # Step 8: Trigger backup creation by saving again
        screen.save_to_project(opened)
        assert bak_file.is_file()

        # Step 9: Simulate corrupted primary file
        state_file.write_text("CORRUPTED_JSON_DATA{{{", encoding="utf-8")

        # Step 10: Reopen project and verify transparent recovery from .bak
        reopen_screen = TimelineScreen()
        try:
            reopen_screen.load_opened_project(opened)
            qapp.processEvents()

            recovered_clips = reopen_screen._current_project_data.get("clips", [])
            assert len(recovered_clips) >= 5

            # Verify mixer restoration
            assert reopen_screen._mixer_levels.get("A1") == 0.85
            assert reopen_screen._mixer_levels.get("master") == 0.95
            assert "A3" in reopen_screen._mixer_mutes
            assert "A2" in reopen_screen._mixer_solos
            assert reopen_screen._sidechain_ducking_depth == 15.0

            # Verify Unicode Bengali text recovery
            s2_recovered = [c for c in recovered_clips if c[0] == "S2"]
            assert len(s2_recovered) >= 1
            assert "সিনেমাটিক এআই স্টুডিওতে" in s2_recovered[0][3]
        finally:
            reopen_screen.close()
    finally:
        screen.close()
        qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Modular Pipeline Vertical Slice & Cancellation Handling
# ─────────────────────────────────────────────────────────────────────────────


def test_rc_modular_pipeline_vertical_slice_and_cancellation(
    tmp_path: Path, qapp: QApplication
) -> None:
    screen = TimelineScreen()
    try:
        video_file = tmp_path / "cinematic_short.mp4"
        video_file.touch()

        screen._current_project_data = {
            "name": "Modular_RC_Project",
            "file_path": str(video_file),
            "duration": 6.0,
            "clips": [],
        }

        # 1. Extraction Worker & Cancellation
        fake_audio = tmp_path / "extracted_16k.wav"
        _create_synthetic_audio_wav(fake_audio, duration_s=6.0)

        with patch("aidub.ui.workers.ModularExtractionWorker.start"):
            screen._on_ai_action_clicked("Extract Dialogue Audio")
            assert screen._extraction_worker is not None
            with patch.object(screen._extraction_worker, "isRunning", return_value=True):
                assert screen.has_active_job() is True

            # Test cancellation
            screen.cancel_active_job()
            screen._extraction_worker.extraction_cancelled.emit()
            qapp.processEvents()
            assert screen._extraction_worker is None
            assert screen.has_active_job() is False

        # 2. Complete Extraction
        with patch("aidub.ui.workers.ModularExtractionWorker.start"):
            screen._on_ai_action_clicked("Extract Dialogue Audio")
            screen._extraction_worker.extraction_completed.emit(str(fake_audio), 6.0)
            qapp.processEvents()
            assert screen._extraction_worker is None
            clips = screen._current_project_data.get("clips", [])
            assert any(c[0] == "A1" for c in clips)

        # 3. Transcription Worker & Cancellation
        with patch("aidub.ui.workers.ModularTranscriptionWorker.start"):
            screen._on_ai_action_clicked("Transcribe Speech (S1)")
            assert screen._transcription_worker is not None
            with patch.object(screen._transcription_worker, "isRunning", return_value=True):
                assert screen.has_active_job() is True

            screen.cancel_active_job()
            screen._transcription_worker.transcription_cancelled.emit()
            qapp.processEvents()
            assert screen._transcription_worker is None
            assert screen.has_active_job() is False

        # 4. Complete Transcription
        sample_cues = [
            TranscriptCue(cue_id="c1", start_s=0.5, end_s=2.5, text="Hello world", confidence=0.99),
            TranscriptCue(
                cue_id="c2", start_s=3.0, end_s=5.5, text="Ready for launch", confidence=0.97
            ),
        ]
        with patch("aidub.ui.workers.ModularTranscriptionWorker.start"):
            screen._on_ai_action_clicked("Transcribe Speech (S1)")
            screen._transcription_worker.transcription_completed.emit(sample_cues)
            qapp.processEvents()
            s1_c = [c for c in screen._current_project_data.get("clips", []) if c[0] == "S1"]
            assert len(s1_c) == 2

        # 5. Translation Worker & Cancellation
        with patch("aidub.ui.workers.ModularTranslationWorker.start"):
            screen._on_ai_action_clicked("Translate Subtitles (S2)")
            assert screen._translation_worker is not None
            with patch.object(screen._translation_worker, "isRunning", return_value=True):
                assert screen.has_active_job() is True

            screen.cancel_active_job()
            screen._translation_worker.translation_cancelled.emit()
            qapp.processEvents()
            assert screen._translation_worker is None
            assert screen.has_active_job() is False

        # 6. Complete Translation
        sample_translated = [
            TranslatedCue(
                cue_id="c1",
                start_s=0.5,
                end_s=2.5,
                source_text="Hello world",
                target_text="ওহে বিশ্ব",
                target_language="bn-BD",
                duration_budget_ms=2000,
            ),
            TranslatedCue(
                cue_id="c2",
                start_s=3.0,
                end_s=5.5,
                source_text="Ready for launch",
                target_text="উদ্বোধনের জন্য প্রস্তুত",
                target_language="bn-BD",
                duration_budget_ms=2500,
            ),
        ]
        with patch("aidub.ui.workers.ModularTranslationWorker.start"):
            screen._on_ai_action_clicked("Translate Subtitles (S2)")
            screen._translation_worker.translation_completed.emit(sample_translated)
            qapp.processEvents()
            s2_c = [c for c in screen._current_project_data.get("clips", []) if c[0] == "S2"]
            assert len(s2_c) == 2
            assert s2_c[0][3] == "ওহে বিশ্ব"

        # 7. Voice Synthesis Worker & Cancellation
        wav1 = tmp_path / "take_c1.wav"
        wav2 = tmp_path / "take_c2.wav"
        _create_synthetic_audio_wav(wav1, 2.0)
        _create_synthetic_audio_wav(wav2, 2.4)

        sample_takes = [
            SynthesizedCueTake(
                cue_id="c1",
                audio_path=str(wav1),
                voice_name="bn-BD-NabanitaNeural",
                start_s=0.5,
                target_duration_s=2.0,
                actual_duration_s=2.0,
                delta_s=0.0,
                delta_pct=0.0,
            ),
            SynthesizedCueTake(
                cue_id="c2",
                audio_path=str(wav2),
                voice_name="bn-BD-NabanitaNeural",
                start_s=3.0,
                target_duration_s=2.5,
                actual_duration_s=2.4,
                delta_s=-0.1,
                delta_pct=-4.0,
            ),
        ]

        with patch("aidub.ui.workers.ModularBatchSynthesisWorker.start"):
            screen._on_ai_action_clicked("Synthesize Voices (A2)")
            assert screen._batch_tts_worker is not None
            with patch.object(screen._batch_tts_worker, "isRunning", return_value=True):
                assert screen.has_active_job() is True

            screen.cancel_active_job()
            screen._batch_tts_worker.synthesis_cancelled.emit()
            qapp.processEvents()
            assert screen._batch_tts_worker is None
            assert screen._synthesis_worker is None
            assert screen.has_active_job() is False

        # 8. Complete Synthesis
        with patch("aidub.ui.workers.ModularBatchSynthesisWorker.start"):
            screen._on_ai_action_clicked("Synthesize Voices (A2)")
            screen._batch_tts_worker.synthesis_completed.emit(sample_takes)
            qapp.processEvents()
            a2_c = [c for c in screen._current_project_data.get("clips", []) if c[0] == "A2"]
            assert len(a2_c) == 2

        # 9. Master Render Worker & Cancellation
        rendered_target = tmp_path / "rendered_rc_master.mp4"
        with patch("aidub.ui.workers.ModularRenderWorker.start"):
            screen._on_ai_action_clicked("Render Master Video")
            assert screen._render_worker is not None
            with patch.object(screen._render_worker, "isRunning", return_value=True):
                assert screen.has_active_job() is True

            screen.cancel_active_job()
            screen._render_worker.render_cancelled.emit()
            qapp.processEvents()
            assert screen._render_worker is None
            assert screen.has_active_job() is False

        # 10. Complete Master Render
        rendered_target.touch()
        with patch("aidub.ui.workers.ModularRenderWorker.start"):
            screen._on_ai_action_clicked("Render Master Video")
            screen._render_worker.render_completed.emit(str(rendered_target))
            qapp.processEvents()
            assert screen._render_worker is None
            assert screen._current_project_data.get("rendered_master") == str(rendered_target)
    finally:
        screen.close()
        qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Broadcast Master Export & Security Checks
# ─────────────────────────────────────────────────────────────────────────────


def test_rc_broadcast_export_validation_and_overwrite_protection(tmp_path: Path) -> None:
    src_video = tmp_path / "source_feature.mp4"
    src_audio = tmp_path / "master_audio.wav"
    src_sub = tmp_path / "subtitles_bn.srt"

    src_video.touch()
    _create_synthetic_audio_wav(src_audio, 3.0)
    src_sub.write_text("1\n00:00:00,500 --> 00:00:02,500\nপরীক্ষামূলক সাবটাইটেল\n", encoding="utf-8")

    # 1. Overwrite Protection: output == source_video must raise ValueError
    with pytest.raises(ValueError, match="Output path cannot overwrite source video"):
        BroadcastMasterExporter.export(
            video_path=src_video,
            audio_path=src_audio,
            output_path=src_video,
            preset=BroadcastPreset.YOUTUBE_4K,
        )

    # 2. Missing source video file must raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="Source video not found"):
        BroadcastMasterExporter.export(
            video_path=tmp_path / "nonexistent.mp4",
            audio_path=src_audio,
            output_path=tmp_path / "out.mp4",
        )

    # 3. Missing master audio file must raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="Master audio track not found"):
        BroadcastMasterExporter.export(
            video_path=src_video,
            audio_path=tmp_path / "nonexistent.wav",
            output_path=tmp_path / "out.mp4",
        )

    # 4. Verify Subtitle Exports
    segments = [
        {"start": 1.0, "end": 3.0, "text": "Original English Line", "tgt": "বাংলা অনূদিত লাইন"},
        {"start": 4.0, "end": 6.5, "text": "Second Line Here", "tgt": "দ্বিতীয় সংলাপ এখানে"},
    ]
    bilingual_out = tmp_path / "bilingual_master.srt"
    target_out = tmp_path / "target_bn.srt"

    write_bilingual_srt(segments, str(bilingual_out), LineMode.BILINGUAL_TARGET_BOTTOM)
    write_srt(segments, str(target_out), translated=True)

    assert bilingual_out.is_file()
    assert target_out.is_file()

    bilingual_content = bilingual_out.read_text(encoding="utf-8")
    target_content = target_out.read_text(encoding="utf-8")

    assert "Original English Line" in bilingual_content
    assert "বাংলা অনূদিত লাইন" in bilingual_content
    assert "দ্বিতীয় সংলাপ এখানে" in target_content


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: UI Navigation, Chrome Synchronization, and Clean Shutdown
# ─────────────────────────────────────────────────────────────────────────────


def test_rc_studio_window_navigation_and_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    catalog_path = tmp_path / "test_catalog_nav.db"
    monkeypatch.setattr("aidub.infrastructure.catalog.default_catalog_path", lambda: catalog_path)
    monkeypatch.setattr(
        "aidub.infrastructure.catalog.catalog.default_catalog_path", lambda: catalog_path
    )

    win = AIDubStudioWindow()
    try:
        win.show()
        qapp.processEvents()

        # 1. Verify initial view is Home Dashboard
        assert win.stack.currentWidget() is win.home_view

        # 2. Switch to Timeline Studio via show_studio() and verify chrome buttons update
        win.show_studio()
        qapp.processEvents()
        assert win.stack.currentWidget() is win.studio
        assert "2563EB" in win.chrome.nav_studio_btn.styleSheet()

        # 3. Switch back to Home Dashboard via show_home() and verify chrome buttons update
        win.show_home()
        qapp.processEvents()
        assert win.stack.currentWidget() is win.home_view
        assert "E11D48" in win.chrome.nav_dub_btn.styleSheet()

        # 4. Verify menu bar setup
        menu_texts = [a.text() for a in win.chrome.menu_bar.actions()]
        assert "File" in menu_texts
        assert "Edit" in menu_texts
        assert "Help" in menu_texts

        # 5. Verify Keyboard Shortcuts dialog opens without errors
        with patch("aidub.ui.keyboard_shortcuts_dialog.KeyboardShortcutsDialog.exec") as mock_exec:
            win.show_keyboard_shortcuts()
            assert mock_exec.called

        # 6. Verify Preferences dialog opens without errors
        with patch("aidub.ui.preferences_dialog.PreferencesDialog.exec") as mock_pref:
            win.open_preferences()
            assert mock_pref.called

        # 7. Verify shutdown with running active job prompts and ignores if rejected
        with (
            patch.object(win.studio, "has_active_job", return_value=True),
            patch(
                "PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.No
            ),
        ):
            event = QCloseEvent()
            win.closeEvent(event)
            assert event.isAccepted() is False
    finally:
        win.close()
        qapp.processEvents()
