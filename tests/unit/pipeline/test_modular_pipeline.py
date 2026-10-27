"""Unit tests for ModularDubbingPipelineService and associated domain models."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from aidub.application.modular_pipeline import (
    ModularDubbingPipelineService,
    PipelineCancelledError,
    SynthesizedCueTake,
    TranscriptCue,
    TranslatedCue,
)
from aidub.application.translation_pipeline import TranslatedLine
from aidub.contracts.base import Identifier
from aidub.domain.time import RationalRate, RationalTime


def _create_wav(path: Path, duration_s: float = 1.0, sr: int = 16000) -> Path:
    """Helper to generate a valid mono PCM WAV file."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    sine = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), sine, sr)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# 1. TranscriptCue & Rational Time
# ─────────────────────────────────────────────────────────────────────────────


def test_transcript_cue_rational_time() -> None:
    cue = TranscriptCue(cue_id="cue_01", start_s=1.5, end_s=3.75, text="Hello world")
    assert cue.duration_s == pytest.approx(2.25)

    start_rt, end_rt = cue.to_rational_time(fps=24.0)
    assert isinstance(start_rt, RationalTime)
    assert isinstance(end_rt, RationalTime)
    assert start_rt.rate == RationalRate(numerator=24, denominator=1)

    # 1.5s * 24 = 36 ticks; 3.75s * 24 = 90 ticks
    assert start_rt.ticks == 36
    assert end_rt.ticks == 90
    assert float(start_rt.seconds) == pytest.approx(1.5)
    assert float(end_rt.seconds) == pytest.approx(3.75)


def test_transcript_cue_zero_duration_guard() -> None:
    cue = TranscriptCue(cue_id="c_err", start_s=5.0, end_s=3.0, text="Backwards")
    assert cue.duration_s == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cue Normalization
# ─────────────────────────────────────────────────────────────────────────────


def test_normalize_cues_sorting_and_clamping() -> None:
    service = ModularDubbingPipelineService()
    cues = [
        TranscriptCue(cue_id="c2", start_s=4.0, end_s=6.0, text="Second"),
        TranscriptCue(cue_id="c1", start_s=1.0, end_s=1.0, text="Zero duration"),  # invalid
        TranscriptCue(cue_id="c3", start_s=5.0, end_s=8.0, text="Overlap"),
    ]

    normalized = service.normalize_cues(cues)
    assert len(normalized) == 3
    # Verify sorting by start_s
    assert [c.cue_id for c in normalized] == ["c1", "c2", "c3"]
    # Verify minimal duration applied to zero-duration cue
    assert normalized[0].end_s > normalized[0].start_s
    assert normalized[0].duration_s == pytest.approx(0.1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Translation (Offline Lexicon & Cancellation)
# ─────────────────────────────────────────────────────────────────────────────


def test_translate_cues_offline_bengali() -> None:
    service = ModularDubbingPipelineService()
    cues = [
        TranscriptCue(cue_id="c1", start_s=0.0, end_s=1.5, text="Hello world"),
        TranscriptCue(cue_id="c2", start_s=2.0, end_s=4.0, text="Thank you"),
    ]

    progress_records: list[tuple[float, str]] = []

    def on_progress(p: float, msg: str) -> None:
        progress_records.append((p, msg))

    translated = service.translate_cues(
        cues,
        source_lang="en",
        target_lang="bn-BD",
        router=None,
        progress_cb=on_progress,
    )

    assert len(translated) == 2
    assert translated[0].target_text == "হ্যালো বিশ্ব"
    assert translated[0].target_language == "bn-BD"
    assert translated[0].duration_budget_ms == 1500
    assert translated[1].target_text == "ধন্যবাদ"
    assert len(progress_records) >= 2


def test_translate_cues_cancellation() -> None:
    service = ModularDubbingPipelineService()
    cues = [
        TranscriptCue(cue_id="c1", start_s=0.0, end_s=1.0, text="Hello"),
    ]

    with pytest.raises(PipelineCancelledError, match="cancelled"):
        service.translate_cues(
            cues,
            source_lang="en",
            target_lang="bn",
            router=None,
            cancel_check=lambda: True,
        )


def test_translate_cues_with_router_mock() -> None:
    service = ModularDubbingPipelineService()
    cues = [
        TranscriptCue(cue_id="c1", start_s=1.0, end_s=3.0, text="Custom speech"),
    ]

    mock_router = MagicMock()
    mock_pipeline = MagicMock()
    mock_pipeline.translate_batch.return_value = [
        TranslatedLine(
            utterance_id=Identifier("c1"),
            source_text="Custom speech",
            translated_text="কাস্টম বক্তব্য",
            target_language="bn-BD",
            estimated_duration_ms=1800,
            duration_delta_pct=0.0,
            within_tolerance=True,
        )
    ]

    with patch(
        "aidub.application.modular_pipeline.TranslationPipeline", return_value=mock_pipeline
    ):
        res = service.translate_cues(
            cues,
            source_lang="en",
            target_lang="bn",
            router=mock_router,
        )

    assert len(res) == 1
    assert res[0].target_text == "কাস্টম বক্তব্য"
    assert res[0].estimated_duration_ms == 1800


# ─────────────────────────────────────────────────────────────────────────────
# 4. Speech Synthesis & Duration Budgeting
# ─────────────────────────────────────────────────────────────────────────────


def test_synthesize_cues_with_timing_budget(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()
    out_dir = tmp_path / "tts_out"

    cues = [
        TranslatedCue(
            cue_id="t1",
            start_s=0.0,
            end_s=2.0,  # 2.0s slot
            source_text="Hello",
            target_text="হ্যালো",
            target_language="bn-BD",
            duration_budget_ms=2000,
        ),
        TranslatedCue(
            cue_id="t2",
            start_s=3.0,
            end_s=4.0,  # 1.0s slot
            source_text="A very long translation that exceeds budget significantly",
            target_text="অনেক বড় একটি বাক্য যা নির্ধারিত সময় অতিক্রম করবে",
            target_language="bn-BD",
            duration_budget_ms=1000,
        ),
    ]

    mock_adapter = MagicMock()

    # Define mock synthesize behavior to create a valid wav
    def fake_synthesize(text: str, out_p: Path, **kwargs: object) -> Path:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # For cue 1, duration 1.9s (within budget)
        # For cue 2, duration 2.5s (exceeds budget by > 15%)
        dur = 1.9 if "Hello" in text or "হ্যালো" in text else 2.5
        _create_wav(out_p, duration_s=dur)
        return out_p

    mock_adapter.synthesize_to_file.side_effect = fake_synthesize

    takes = service.synthesize_cues(
        cues,
        target_lang="bn-BD",
        output_dir=out_dir,
        adapter=mock_adapter,
    )

    assert len(takes) == 2
    assert takes[0].cue_id == "t1"
    assert Path(takes[0].audio_path).is_file()

    # Cue 2 generated 2.5s for a 1.0s slot -> delta is (2.5 - 1.0)/1.0 = 150% > 15%
    # fit_to_slot speed-up clamps to max_stretch (1.08x) -> final dur ~ 2.31s > 1.0s slot
    assert takes[1].cue_id == "t2"
    assert takes[1].flagged_for_review is True
    assert takes[1].delta_pct > 0.15


def test_synthesize_cues_cancellation(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()
    cues = [
        TranslatedCue(
            cue_id="t1",
            start_s=0.0,
            end_s=1.0,
            source_text="Hello",
            target_text="হ্যালো",
            target_language="bn-BD",
        ),
    ]

    with pytest.raises(PipelineCancelledError, match="cancelled"):
        service.synthesize_cues(
            cues,
            target_lang="bn-BD",
            output_dir=tmp_path,
            cancel_check=lambda: True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Timeline Audio Mixing
# ─────────────────────────────────────────────────────────────────────────────


def test_mix_timeline_audio(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()

    wav1 = _create_wav(tmp_path / "take1.wav", duration_s=1.0)
    wav2 = _create_wav(tmp_path / "take2.wav", duration_s=1.5)

    takes = [
        SynthesizedCueTake(
            cue_id="t1",
            audio_path=str(wav1),
            voice_name="bn-IN-TanishaaNeural",
            start_s=0.5,
            target_duration_s=1.0,
            actual_duration_s=1.0,
            delta_s=0.0,
            delta_pct=0.0,
            flagged_for_review=False,
        ),
        SynthesizedCueTake(
            cue_id="t2",
            audio_path=str(wav2),
            voice_name="bn-IN-TanishaaNeural",
            start_s=2.0,
            target_duration_s=1.5,
            actual_duration_s=1.5,
            delta_s=0.0,
            delta_pct=0.0,
            flagged_for_review=False,
        ),
    ]

    out_mix = tmp_path / "dubbed_mix.wav"
    res_path = service.mix_timeline_audio(takes, total_duration_s=5.0, output_mix_wav=out_mix)

    assert res_path.is_file()
    data, sr = sf.read(str(res_path))
    assert sr == 44100
    # Length should match total_duration_s (5.0s * 44100)
    assert len(data) >= int(5.0 * 44100)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Audio Extraction & Media Probing
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_dialogue_audio_missing_input(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()
    with pytest.raises(FileNotFoundError, match="Source video media does not exist"):
        service.extract_dialogue_audio(tmp_path / "non_existent.mp4", tmp_path / "out.wav")


def test_extract_dialogue_audio_cancellation(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()
    in_media = _create_wav(tmp_path / "source.wav", duration_s=1.0)

    with pytest.raises(PipelineCancelledError, match="cancelled"):
        service.extract_dialogue_audio(
            in_media,
            tmp_path / "out.wav",
            cancel_check=lambda: True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Master Render & Validation
# ─────────────────────────────────────────────────────────────────────────────


def test_render_master_timeline_file_missing_validation(tmp_path: Path) -> None:
    service = ModularDubbingPipelineService()
    with pytest.raises(FileNotFoundError, match="Source video file not found"):
        service.render_master_timeline(
            tmp_path / "vid_missing.mp4",
            tmp_path / "aud_missing.wav",
            tmp_path / "out.mp4",
        )
