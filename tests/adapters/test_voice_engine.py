"""Unit tests for Voice Engine adapter base and TTS worker (Task 3.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aidub.adapters.voice_base import (
    EmotionLabel,
    SynthesisRequest,
    SyntheticVoiceEngine,
    VoiceEngineKind,
)
from aidub.contracts.base import Identifier


def _make_request(
    utterance_id: str = "utt-001",
    text: str = "Hello, my name is Tony Stark.",
    language: str = "en-US",
    emotion: EmotionLabel = EmotionLabel.NEUTRAL,
    seed: int = 42,
) -> SynthesisRequest:
    return SynthesisRequest(
        request_id=Identifier(f"req-{utterance_id}"),
        utterance_id=Identifier(utterance_id),
        voice_profile_id=Identifier("vp-001"),
        text=text,
        language=language,
        emotion=emotion,
        seed=seed,
    )


def test_synthetic_voice_engine_produces_output(tmp_path: Path) -> None:
    engine = SyntheticVoiceEngine()
    request = _make_request()
    result = engine.synthesize(request, str(tmp_path))

    assert result.engine_kind == VoiceEngineKind.SYNTHETIC
    assert result.utterance_id == "utt-001"
    assert result.seed_used == 42
    assert result.duration_ms >= 500
    out = Path(result.output_path)
    assert out.exists()
    assert out.stat().st_size > 0


def test_synthetic_voice_engine_deterministic_output(tmp_path: Path) -> None:
    """Same seed produces same file size (deterministic duration estimation)."""
    engine = SyntheticVoiceEngine()
    request = _make_request(seed=7)
    result1 = engine.synthesize(request, str(tmp_path / "run1"))
    result2 = engine.synthesize(request, str(tmp_path / "run2"))

    assert result1.duration_ms == result2.duration_ms
    assert Path(result1.output_path).stat().st_size == Path(result2.output_path).stat().st_size


def test_synthetic_voice_engine_different_seeds_same_text(tmp_path: Path) -> None:
    """Different seeds still produce output (seed stored in filename)."""
    engine = SyntheticVoiceEngine()
    r1 = engine.synthesize(_make_request(seed=1), str(tmp_path))
    r2 = engine.synthesize(_make_request(seed=2), str(tmp_path))
    assert r1.seed_used == 1
    assert r2.seed_used == 2
    assert r1.output_path != r2.output_path


def test_synthesis_request_emotion_labels() -> None:
    for emotion in EmotionLabel:
        req = _make_request(emotion=emotion)
        assert req.emotion == emotion


def test_synthesis_request_pace_multiplier_bounds() -> None:
    with pytest.raises(ValidationError):
        SynthesisRequest(
            request_id=Identifier("req"),
            utterance_id=Identifier("utt"),
            voice_profile_id=Identifier("vp"),
            text="Hello",
            language="en-US",
            pace_multiplier=5.0,  # exceeds max of 2.0
        )


def test_synthesis_result_has_seed_metadata(tmp_path: Path) -> None:
    engine = SyntheticVoiceEngine()
    result = engine.synthesize(_make_request(seed=99), str(tmp_path))
    assert result.seed_used == 99
    assert "99" in Path(result.output_path).name


def test_edge_tts_all_supported_languages_mapped() -> None:
    from aidub.adapters.voice.edge_tts_adapter import (
        available_voices_for_language,
        default_voice_for_language,
    )

    expected_langs = [
        "bn",
        "hi",
        "es",
        "fr",
        "de",
        "ja",
        "zh",
        "ar",
        "pt",
        "ru",
        "ko",
        "it",
        "tr",
        "en",
    ]
    for lang in expected_langs:
        voice = default_voice_for_language(lang)
        assert isinstance(voice, str)
        assert len(voice) > 5
        assert "Neural" in voice

        voices = available_voices_for_language(lang)
        assert len(voices) >= 1
        assert voice in voices
