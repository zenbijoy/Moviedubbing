"""Integration tests for the modular AI dubbing pipeline connected to TimelineScreen."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from aidub.application.modular_pipeline import (
    SynthesizedCueTake,
    TranscriptCue,
    TranslatedCue,
)
from aidub.ui.screens.timeline_editor import TimelineScreen


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_modular_pipeline_full_vertical_slice(tmp_path: Path, qapp) -> None:
    """Test full modular workflow slice: Extract -> Transcribe -> Translate -> Synthesize -> Render."""
    screen = TimelineScreen()
    try:
        # Create a sample media file
        video_p = tmp_path / "cinematic_short.mp4"
        video_p.touch()

        # Initialize mock project data on timeline
        screen._current_project_data = {
            "name": "Cinema_Dub_Project",
            "file_path": str(video_p),
            "duration": 10.0,
            "clips": [],
        }

        # 1. Action: "Extract Dialogue Audio"
        fake_audio = tmp_path / "cinematic_short_audio16k.wav"
        fake_audio.touch()

        with patch("aidub.ui.workers.ModularExtractionWorker.start"):
            screen._on_ai_action_clicked("Extract Dialogue Audio")
            assert hasattr(screen, "_extraction_worker")
            assert screen._extraction_worker is not None
            # Simulate worker completion signal
            screen._extraction_worker.extraction_completed.emit(str(fake_audio), 10.0)
            qapp.processEvents()

        # Verify Track A1 is populated
        clips = screen._current_project_data.get("clips", [])
        a1_clips = [c for c in clips if c[0] == "A1"]
        assert len(a1_clips) == 1
        assert a1_clips[0][3] == "Production Dialogue"
        assert a1_clips[0][2] == 10.0

        # 2. Action: "Transcribe Speech (S1)"
        sample_cues = [
            TranscriptCue(
                cue_id="cue_01",
                start_s=0.5,
                end_s=3.0,
                text="Welcome to the studio",
                confidence=0.98,
            ),
            TranscriptCue(
                cue_id="cue_02", start_s=4.0, end_s=7.0, text="Dubbing is ready", confidence=0.95
            ),
        ]

        with patch("aidub.ui.workers.ModularTranscriptionWorker.start"):
            screen._on_ai_action_clicked("Transcribe Speech (S1)")
            assert hasattr(screen, "_transcription_worker")
            assert screen._transcription_worker is not None
            # Simulate worker completion
            screen._transcription_worker.transcription_completed.emit(sample_cues)
            qapp.processEvents()

        # Verify Track S1 has the 2 transcript cues
        clips = screen._current_project_data.get("clips", [])
        s1_clips = [c for c in clips if c[0] == "S1"]
        assert len(s1_clips) == 2
        assert s1_clips[0][3] == "Welcome to the studio"
        assert s1_clips[1][3] == "Dubbing is ready"
        # Verify dialogue inspector card updated
        assert screen.inspector_panel.orig_in.text() == "Welcome to the studio"

        # 3. Action: "Translate Subtitles (S2)"
        sample_translations = [
            TranslatedCue(
                cue_id="cue_01",
                start_s=0.5,
                end_s=3.0,
                source_text="Welcome to the studio",
                target_text="স্টুডিওতে স্বাগতম",
                target_language="bn-BD",
                duration_budget_ms=2500,
            ),
            TranslatedCue(
                cue_id="cue_02",
                start_s=4.0,
                end_s=7.0,
                source_text="Dubbing is ready",
                target_text="ডাবিং প্রস্তুত",
                target_language="bn-BD",
                duration_budget_ms=3000,
            ),
        ]

        with patch("aidub.ui.workers.ModularTranslationWorker.start"):
            screen._on_ai_action_clicked("Translate Subtitles (S2)")
            assert hasattr(screen, "_translation_worker")
            assert screen._translation_worker is not None
            # Simulate worker completion
            screen._translation_worker.translation_completed.emit(sample_translations)
            qapp.processEvents()

        # Verify Track S2 has translated subtitles
        clips = screen._current_project_data.get("clips", [])
        s2_clips = [c for c in clips if c[0] == "S2"]
        assert len(s2_clips) == 2
        assert s2_clips[0][3] == "স্টুডিওতে স্বাগতম"
        assert s2_clips[1][3] == "ডাবিং প্রস্তুত"
        # Verify dialogue inspector card target updated
        assert screen.inspector_panel.trans_in.text() == "স্টুডিওতে স্বাগতম"

        # 4. Action: "Synthesize Voices (A2)"
        import numpy as np
        import soundfile as sf

        sr = 44100
        wav1 = tmp_path / "cue_01_fit.wav"
        wav2 = tmp_path / "cue_02_fit.wav"
        sf.write(str(wav1), np.zeros(int(2.4 * sr), dtype=np.float32), sr)
        sf.write(str(wav2), np.zeros(int(2.9 * sr), dtype=np.float32), sr)

        sample_takes = [
            SynthesizedCueTake(
                cue_id="cue_01",
                audio_path=str(wav1),
                voice_name="bn-BD-NabanitaNeural",
                start_s=0.5,
                target_duration_s=2.5,
                actual_duration_s=2.4,
                delta_s=-0.1,
                delta_pct=-0.04,
                flagged_for_review=False,
            ),
            SynthesizedCueTake(
                cue_id="cue_02",
                audio_path=str(wav2),
                voice_name="bn-BD-NabanitaNeural",
                start_s=4.0,
                target_duration_s=3.0,
                actual_duration_s=2.9,
                delta_s=-0.1,
                delta_pct=-0.03,
                flagged_for_review=False,
            ),
        ]

        with patch("aidub.ui.workers.ModularBatchSynthesisWorker.start"):
            screen._on_ai_action_clicked("Synthesize Voices (A2)")
            assert hasattr(screen, "_synthesis_worker")
            assert screen._synthesis_worker is not None
            # Simulate worker completion
            screen._synthesis_worker.synthesis_completed.emit(sample_takes)
            qapp.processEvents()

        # Verify Track A2 has synthesized takes
        clips = screen._current_project_data.get("clips", [])
        a2_clips = [c for c in clips if c[0] == "A2"]
        assert len(a2_clips) == 2
        assert a2_clips[0][3] == "bn-BD-NabanitaNeural [cue_01]"

        # 5. Action: "Render Master Video"
        rendered_master = tmp_path / "Cinema_Dub_Project_master_dub.mp4"
        rendered_master.touch()

        with patch("aidub.ui.workers.ModularRenderWorker.start"):
            screen._on_ai_action_clicked("Render Master Video")
            assert hasattr(screen, "_render_worker")
            assert screen._render_worker is not None
            # Simulate worker completion
            screen._render_worker.render_completed.emit(str(rendered_master))
            qapp.processEvents()

        # Verify master video is registered in project data
        assert screen._current_project_data.get("rendered_master") == str(rendered_master)
    finally:
        screen.close()
        qapp.processEvents()


def test_modular_pipeline_empty_guard(qapp) -> None:
    """Test guard when attempting to translate without any S1 dialogue cues."""
    screen = TimelineScreen()
    try:
        screen._current_project_data = {
            "name": "Empty_Project",
            "file_path": "",
            "clips": [],
        }

        # Attempt to translate without cues
        screen._on_ai_action_clicked("Translate Subtitles (S2)")
        qapp.processEvents()
        # Should not create worker
        assert not hasattr(screen, "_translation_worker") or screen._translation_worker is None
    finally:
        screen.close()
        qapp.processEvents()
