"""Unit tests for AdaptiveDurationFittingService."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from aidub.adapters.voice_base import SyntheticVoiceEngine
from aidub.application.adaptive_duration_fitting import (
    AdaptiveDurationFittingService,
)
from aidub.application.timing_fitter import FitStrategy
from aidub.application.voice.scene_performance_service import (
    DialogueCuePerformance,
)
from aidub.contracts.base import Identifier


def _create_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 48000) -> Path:
    n_frames = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        samples = [int(0.4 * 32767.0 * math.sin(2.0 * math.pi * 440.0 * (i / sample_rate))) for i in range(n_frames)]
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def test_fit_exact_match(tmp_path: Path) -> None:
    service = AdaptiveDurationFittingService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_exact"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("frodo"),
        speaker_id=Identifier("spk_1"),
        source_text="I will take it.",
        target_text="আমি এটা নেব।",
        start_s=5.0,
        end_s=7.0,
        target_duration_s=2.0,
    )
    wav_path = _create_wav(tmp_path / "exact.wav", duration_s=2.02)  # within 50ms

    rep = service.fit_dialogue_cue(
        cue=cue,
        input_audio_path=wav_path,
        output_dir=tmp_path / "out",
    )

    assert rep.strategy_applied == FitStrategy.EXACT_FIT
    assert rep.flagged_for_manual_review is False
    assert rep.target_duration_s == 2.0
    assert rep.original_start_s == 5.0
    assert rep.original_end_s == 7.0
    assert Path(rep.fitted_audio_path).exists()


def test_fit_suggests_shorter_translation(tmp_path: Path) -> None:
    service = AdaptiveDurationFittingService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_long"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("sam"),
        speaker_id=Identifier("spk_2"),
        source_text="It's like in the great stories, Mr. Frodo.",
        target_text="এটা সেই মহান গল্পগুলোর মতো, ফ্রোদো সাহেব।",
        target_duration_s=1.5,
    )
    wav_path = _create_wav(tmp_path / "long.wav", duration_s=2.5)  # exceeds slot

    def mock_shortener(text: str, target_s: float) -> str:
        return "গল্পের মতো, ফ্রোদো।"

    rep = service.fit_dialogue_cue(
        cue=cue,
        input_audio_path=wav_path,
        output_dir=tmp_path / "out",
        shorter_text_suggester=mock_shortener,
    )

    assert rep.suggested_shorter_text == "গল্পের মতো, ফ্রোদো।"
    assert rep.actual_generated_duration_s == 2.5


def test_fit_rate_control_via_engine(tmp_path: Path) -> None:
    service = AdaptiveDurationFittingService()
    engine = SyntheticVoiceEngine()

    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_rate"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("gimli"),
        speaker_id=Identifier("spk_3"),
        source_text="Nobody tosses a dwarf!",
        target_text="কেউ কোনো বামনকে ছুড়ে ফেলে না!",
        target_duration_s=2.0,
    )
    # Synthesized audio is 2.3s (Target 2.0s -> ~1.15x speed fits within tolerance)
    wav_path = _create_wav(tmp_path / "initial.wav", duration_s=2.3)

    rep = service.fit_dialogue_cue(
        cue=cue,
        input_audio_path=wav_path,
        output_dir=tmp_path / "out",
        voice_engine=engine,
        voice_id="synth_voice_1",
    )

    assert rep.flagged_for_manual_review is False
    assert Path(rep.fitted_audio_path).exists()


def test_fit_excessive_overrun_flags_manual_review(tmp_path: Path) -> None:
    service = AdaptiveDurationFittingService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_extreme"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("boromir"),
        speaker_id=Identifier("spk_4"),
        source_text="One does not simply walk into Mordor.",
        target_text="কেউ সহজে হেঁটে হেঁটে ভয়ংকর মরডোরের ভেতরে প্রবেশ করতে পারে না।",
        target_duration_s=1.0,  # Short slot: 1.0s
    )
    # 3.0s audio for a 1.0s slot (200% overrun! cannot be compressed cleanly without extreme distortion)
    wav_path = _create_wav(tmp_path / "huge.wav", duration_s=3.0)

    rep = service.fit_dialogue_cue(
        cue=cue,
        input_audio_path=wav_path,
        output_dir=tmp_path / "out",
    )

    # Must flag for human review rather than destroying audio quality
    assert rep.flagged_for_manual_review is True
    assert rep.strategy_applied == FitStrategy.HUMAN_REVIEW
    assert "Manual script trim or timeline extension required" in rep.review_reason
    assert rep.target_duration_s == 1.0
    assert rep.actual_generated_duration_s == 3.0
