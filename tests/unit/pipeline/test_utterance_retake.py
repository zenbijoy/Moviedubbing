"""Unit tests for UtteranceRetakeService (ADR single-line retakes)."""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidub.pipeline.errors import PipelineError
from aidub.pipeline.retake import RetakeResult, UtteranceRetakeService
from aidub.pipeline.utterance_store import UtteranceStore


def _make_dummy_wav(path: Path, duration_s: float = 1.0) -> Path:
    sr = 44100
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(duration_s * sr)):
            val = int(10000 * math.sin(2 * math.pi * 440 * (i / sr)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return path


def test_retake_service_validation(tmp_path: Path) -> None:
    service = UtteranceRetakeService(tmp_path, target_language="bn")

    # Empty text error
    with pytest.raises(PipelineError) as exc_info:
        service.retake_utterance(0, "   ")
    assert exc_info.value.code == "empty_retake_text"

    # No utterances in directory
    with pytest.raises(PipelineError) as exc_info:
        service.retake_utterance(0, "নতুন সংলাপ")
    assert exc_info.value.code == "no_utterances_found"


def test_retake_service_successful_replacement(tmp_path: Path) -> None:
    # 1. Setup existing project artifacts
    store = UtteranceStore("bn", tmp_path)
    segs = [
        {"start": 0.5, "end": 2.0, "text": "Hello friend", "tgt": "হ্যালো বন্ধু", "speaker": 0},
        {"start": 3.0, "end": 5.0, "text": "Good morning", "tgt": "সুপ্রভাত", "speaker": 1},
    ]
    store.save_utterances(segs)

    # Provide existing fitted segment wavs
    _make_dummy_wav(tmp_path / "seg_000_fit.wav", duration_s=1.5)
    _make_dummy_wav(tmp_path / "seg_001_fit.wav", duration_s=2.0)

    # Provide dummy manifest
    manifest_data = {
        "outputs": {"duration_s": 6.0},
        "inputs": {"source_video": ""},
    }
    with (tmp_path / "aidub_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    service = UtteranceRetakeService(tmp_path, target_language="bn")

    # Mock synthesize_to_file to write a valid dummy audio file
    def _mock_synth(text: str, output_mp3_path: Path, **kwargs: object) -> None:
        _make_dummy_wav(output_mp3_path, duration_s=1.2)

    with patch("aidub.pipeline.retake.EdgeTTSAdapter.synthesize_to_file", side_effect=_mock_synth):
        result: RetakeResult = service.retake_utterance(
            utterance_index=0,
            new_target_text="স্বাগতম প্রিয় বন্ধু",
        )

    assert result.success is True
    assert result.utterance_index == 0
    assert result.new_target_text == "স্বাগতম প্রিয় বন্ধু"
    assert Path(result.dubbed_vocals_path).is_file()
    assert Path(result.subtitle_path).is_file()

    # Verify store updated
    loaded_utterances, _ = store.load_utterances()
    assert loaded_utterances[0]["tgt"] == "স্বাগতম প্রিয় বন্ধু"
    assert loaded_utterances[0]["retake_applied"] is True

    # Verify subtitles updated
    srt_content = Path(result.subtitle_path).read_text(encoding="utf-8")
    assert "স্বাগতম প্রিয় বন্ধু" in srt_content
