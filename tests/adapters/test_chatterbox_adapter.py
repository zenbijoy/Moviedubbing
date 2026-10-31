"""Unit tests for Chatterbox AI Voice Engine adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aidub.adapters.voice.chatterbox_adapter import (
    ChatterboxAdapter,
    ChatterboxVoiceEngine,
)
from aidub.adapters.voice_base import (
    EmotionLabel,
    SynthesisRequest,
    VoiceEngineKind,
)


def test_chatterbox_voice_engine_kind() -> None:
    engine = ChatterboxVoiceEngine()
    assert engine.engine_kind == VoiceEngineKind.CHATTERBOX


def test_chatterbox_adapter_rejects_empty_text(tmp_path: Path) -> None:
    adapter = ChatterboxAdapter()
    out = tmp_path / "out.wav"
    with pytest.raises(ValueError, match="cannot be empty"):
        adapter.synthesize_to_file("   ", out)


def test_chatterbox_adapter_fallback_produces_audio(tmp_path: Path) -> None:
    adapter = ChatterboxAdapter(api_url="http://127.0.0.1:9999/nonexistent", allow_fallback=True)
    out = tmp_path / "fallback.wav"

    # Mock EdgeTTSAdapter so we don't depend on live network in unit test
    with patch(
        "aidub.adapters.voice.edge_tts_adapter.EdgeTTSAdapter.synthesize_to_file"
    ) as mock_synth:
        # Create a stub output file when mock is called
        def side_effect(text, path, **kwargs):
            Path(path).write_bytes(b"mock mp3 data")
            return Path(path)

        mock_synth.side_effect = side_effect
        with patch("aidub.adapters.voice.chatterbox_adapter._run") as mock_run:

            def ffmpeg_side_effect(cmd):
                # fake ffmpeg creating wav
                out.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 400)

            mock_run.side_effect = ffmpeg_side_effect

            res = adapter.synthesize_to_file(
                "হ্যালো বিশ্ব",
                out,
                emotion=EmotionLabel.JOY,
                pace=1.1,
            )
            assert res == out
            assert out.is_file()


def test_chatterbox_voice_engine_synthesize_request(tmp_path: Path) -> None:
    engine = ChatterboxVoiceEngine()
    req = SynthesisRequest(
        request_id="req_001",
        utterance_id="utt_001",
        voice_profile_id="voice_hero",
        text="This is a test line",
        language="bn",
        emotion=EmotionLabel.ANGRY,
        pace_multiplier=1.0,
        pitch_shift_semitones=0.0,
        output_sample_rate=44100,
    )

    with patch.object(engine.adapter, "synthesize_to_file") as mock_synth:

        def side_effect(*args, **kwargs):
            out_p = kwargs.get("output_wav_path") or args[1]
            Path(out_p).write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 500)
            return Path(out_p)

        mock_synth.side_effect = side_effect
        with patch("aidub.adapters.voice.chatterbox_adapter.duration", return_value=1.5):
            res = engine.synthesize(req, str(tmp_path))

            assert res.engine_kind == VoiceEngineKind.CHATTERBOX
            assert res.utterance_id == "utt_001"
            assert res.duration_ms == 1500
            assert Path(res.output_path).is_file()
