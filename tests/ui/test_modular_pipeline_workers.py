"""Unit tests for modular pipeline QThread workers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from aidub.application.modular_pipeline import (
    PipelineCancelledError,
    SynthesizedCueTake,
    TranscriptCue,
    TranslatedCue,
)
from aidub.ui.workers import (
    ModularBatchSynthesisWorker,
    ModularExtractionWorker,
    ModularRenderWorker,
    ModularTranscriptionWorker,
    ModularTranslationWorker,
)


@pytest.fixture(autouse=True)
def qapp():
    """Ensure a QApplication exists for Qt signal/slot testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ─────────────────────────────────────────────────────────────────────────────
# 1. Extraction Worker Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_modular_extraction_worker_success(tmp_path: Path):
    in_video = tmp_path / "sample.mp4"
    in_video.touch()
    out_audio = tmp_path / "dialogue.wav"

    mock_service = MagicMock()
    mock_service.extract_dialogue_audio.return_value = (5.5, out_audio)

    worker = ModularExtractionWorker(in_video, out_audio, service=mock_service)

    progress_records = []
    completed_records = []

    worker.progress_updated.connect(lambda p, m: progress_records.append((p, m)))
    worker.extraction_completed.connect(lambda path, dur: completed_records.append((path, dur)))

    worker.run()

    assert len(completed_records) == 1
    assert completed_records[0] == (str(out_audio), 5.5)


def test_modular_extraction_worker_cancellation(tmp_path: Path):
    in_video = tmp_path / "sample.mp4"
    out_audio = tmp_path / "dialogue.wav"

    mock_service = MagicMock()
    mock_service.extract_dialogue_audio.side_effect = PipelineCancelledError("cancelled by user")

    worker = ModularExtractionWorker(in_video, out_audio, service=mock_service)

    cancelled = []
    failed = []
    worker.extraction_cancelled.connect(lambda: cancelled.append(True))
    worker.extraction_failed.connect(failed.append)

    worker.run()

    assert len(cancelled) == 1
    assert len(failed) == 0


def test_modular_extraction_worker_failure(tmp_path: Path):
    in_video = tmp_path / "missing.mp4"
    out_audio = tmp_path / "dialogue.wav"

    mock_service = MagicMock()
    mock_service.extract_dialogue_audio.side_effect = RuntimeError("FFmpeg decode failure")

    worker = ModularExtractionWorker(in_video, out_audio, service=mock_service)

    errors = []
    worker.extraction_failed.connect(errors.append)

    worker.run()

    assert len(errors) == 1
    assert "FFmpeg decode failure" in errors[0]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Transcription Worker Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_modular_transcription_worker_success(tmp_path: Path):
    audio_file = tmp_path / "audio.wav"
    audio_file.touch()

    sample_cues = [
        TranscriptCue(cue_id="cue_01", start_s=0.5, end_s=2.5, text="Welcome to the studio"),
    ]

    mock_service = MagicMock()
    mock_service.transcribe_audio.return_value = sample_cues

    worker = ModularTranscriptionWorker(
        audio_file, language="en", model_size="base", service=mock_service
    )

    results = []
    worker.transcription_completed.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].text == "Welcome to the studio"


def test_modular_transcription_worker_cancellation(tmp_path: Path):
    audio_file = tmp_path / "audio.wav"
    mock_service = MagicMock()
    mock_service.transcribe_audio.side_effect = PipelineCancelledError("aborted")

    worker = ModularTranscriptionWorker(audio_file, service=mock_service)

    cancelled = []
    worker.transcription_cancelled.connect(lambda: cancelled.append(True))

    worker.run()

    assert len(cancelled) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 3. Translation Worker Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_modular_translation_worker_success():
    cues = [
        TranscriptCue(cue_id="c1", start_s=0.0, end_s=2.0, text="Hello"),
    ]
    trans_cues = [
        TranslatedCue(
            cue_id="c1",
            start_s=0.0,
            end_s=2.0,
            source_text="Hello",
            target_text="হ্যালো",
            target_language="bn-BD",
        ),
    ]

    mock_service = MagicMock()
    mock_service.translate_cues.return_value = trans_cues

    worker = ModularTranslationWorker(
        cues, source_lang="en", target_lang="bn-BD", service=mock_service
    )

    results = []
    worker.translation_completed.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert results[0][0].target_text == "হ্যালো"


def test_modular_translation_worker_failure():
    cues = [TranscriptCue(cue_id="c1", start_s=0.0, end_s=1.0, text="Hi")]
    mock_service = MagicMock()
    mock_service.translate_cues.side_effect = ValueError("Rate limit exceeded")

    worker = ModularTranslationWorker(
        cues, source_lang="en", target_lang="bn", service=mock_service
    )

    errors = []
    worker.translation_failed.connect(errors.append)

    worker.run()

    assert len(errors) == 1
    assert "Rate limit exceeded" in errors[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Batch Synthesis Worker Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_modular_synthesis_worker_success(tmp_path: Path):
    cues = [
        TranslatedCue(
            cue_id="c1",
            start_s=0.0,
            end_s=2.0,
            source_text="Hello",
            target_text="হ্যালো",
            target_language="bn-BD",
        ),
    ]
    takes = [
        SynthesizedCueTake(
            cue_id="c1",
            audio_path=str(tmp_path / "c1.wav"),
            voice_name="bn-BD-NabanitaNeural",
            start_s=0.0,
            target_duration_s=2.0,
            actual_duration_s=1.9,
            delta_s=-0.1,
            delta_pct=-0.05,
            flagged_for_review=False,
        ),
    ]

    mock_service = MagicMock()
    mock_service.synthesize_cues.return_value = takes

    worker = ModularBatchSynthesisWorker(
        cues, target_lang="bn-BD", output_dir=tmp_path, service=mock_service
    )

    results = []
    worker.synthesis_completed.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].flagged_for_review is False


def test_modular_synthesis_worker_cancellation(tmp_path: Path):
    cues = [
        TranslatedCue(
            cue_id="c1",
            start_s=0.0,
            end_s=1.0,
            source_text="Hello",
            target_text="হ্যালো",
            target_language="bn-BD",
        ),
    ]
    mock_service = MagicMock()
    mock_service.synthesize_cues.side_effect = PipelineCancelledError("synthesis stopped")

    worker = ModularBatchSynthesisWorker(
        cues, target_lang="bn-BD", output_dir=tmp_path, service=mock_service
    )

    cancelled = []
    worker.synthesis_cancelled.connect(lambda: cancelled.append(True))

    worker.run()

    assert len(cancelled) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. Render Worker Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_modular_render_worker_success(tmp_path: Path):
    in_video = tmp_path / "source.mp4"
    in_audio = tmp_path / "dubbed.wav"
    out_master = tmp_path / "master.mp4"

    mock_service = MagicMock()
    mock_service.render_master_timeline.return_value = out_master

    worker = ModularRenderWorker(in_video, in_audio, out_master, service=mock_service)

    results = []
    worker.render_completed.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert results[0] == str(out_master)


def test_modular_render_worker_cancellation(tmp_path: Path):
    in_video = tmp_path / "source.mp4"
    in_audio = tmp_path / "dubbed.wav"
    out_master = tmp_path / "master.mp4"

    mock_service = MagicMock()
    mock_service.render_master_timeline.side_effect = PipelineCancelledError("render aborted")

    worker = ModularRenderWorker(in_video, in_audio, out_master, service=mock_service)

    cancelled = []
    worker.render_cancelled.connect(lambda: cancelled.append(True))

    worker.run()

    assert len(cancelled) == 1
