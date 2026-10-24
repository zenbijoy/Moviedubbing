"""
Unit tests for TwoStageCharacterVoiceCloner and Optimal Reference Extractor (Feature 4).
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from unittest.mock import patch

from aidub.adapters.voice.two_stage_cloner import (
    TwoStageCharacterVoiceCloner,
    TwoStageCloningResult,
)


def _make_dummy_wav(path: Path, duration_s: float = 1.0, freq_hz: float = 440.0) -> Path:
    sr = 24000
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(duration_s * sr)):
            val = int(12000 * math.sin(2 * math.pi * freq_hz * (i / sr)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return path


def test_extract_optimal_speaker_references(tmp_path: Path) -> None:
    vocals_file = _make_dummy_wav(tmp_path / "vocals16.wav", duration_s=40.0)

    # 3 speakers with multiple turns
    segments = [
        {"start": 0.5, "end": 6.5, "speaker": 0, "text": "Turn A"},
        {"start": 7.0, "end": 25.0, "speaker": 0, "text": "Turn B (18s)"},
        {"start": 26.0, "end": 32.0, "speaker": 1, "text": "Turn C"},
        {"start": 33.0, "end": 39.0, "speaker": 1, "text": "Turn D"},
    ]

    ref_dir = tmp_path / "references"

    # Mock ffmpeg trim to extract dummy audio
    def _mock_trim(inp: Path | str, out: Path | str, a: float, b: float) -> None:
        dur = max(0.5, b - a)
        _make_dummy_wav(Path(out), duration_s=dur)

    with patch("aidub.adapters.voice.two_stage_cloner.trim", side_effect=_mock_trim):
        profiles = TwoStageCharacterVoiceCloner.extract_optimal_speaker_references(
            segments=segments,
            vocals_wav_path=vocals_file,
            output_dir=ref_dir,
            target_min_duration_s=15.0,
            target_max_duration_s=30.0,
        )

    assert 0 in profiles
    assert 1 in profiles

    prof_0 = profiles[0]
    assert prof_0.speaker_id == 0
    assert prof_0.total_reference_duration_s >= 15.0
    assert prof_0.reference_wav_path.is_file()
    assert prof_0.snr_estimate_db > 0.0


def test_two_stage_voice_cloning_pipeline(tmp_path: Path) -> None:
    work_dir = tmp_path / "cloner_work"
    cloner = TwoStageCharacterVoiceCloner(work_dir, target_language="bn")

    ref_audio = _make_dummy_wav(tmp_path / "ref_actor.wav", duration_s=3.0, freq_hz=220.0)
    out_audio = tmp_path / "final_cloned_dialogue.wav"

    # Mock Stage 1 Edge-TTS synthesis to create dummy base audio
    def _mock_synth(text: str, output_mp3_path: Path, **kwargs: object) -> None:
        _make_dummy_wav(output_mp3_path, duration_s=1.8, freq_hz=350.0)

    with patch("aidub.adapters.voice.edge_tts_adapter.EdgeTTSAdapter.synthesize_to_file", side_effect=_mock_synth):
        result: TwoStageCloningResult = cloner.synthesize_character_voice(
            text="আমি তোমাকে কখনো ভুলব না",
            output_wav_path=out_audio,
            reference_audio_paths=[ref_audio],
            character_name="Hero_Lead",
            pitch_shift_semitones=0.0,
        )

    assert result.success is True
    assert result.character_name == "Hero_Lead"
    assert result.duration_s > 0.0
    assert result.timbre_similarity_score >= 0.75
    assert Path(result.stage1_base_path).is_file()
    assert Path(result.stage2_converted_path).is_file()

    # Validate output audio header
    with wave.open(result.stage2_converted_path, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0


def test_two_stage_voice_cloning_fallback_no_reference(tmp_path: Path) -> None:
    work_dir = tmp_path / "cloner_work_fallback"
    cloner = TwoStageCharacterVoiceCloner(work_dir, target_language="bn")
    out_audio = tmp_path / "fallback_dialogue.wav"

    def _mock_synth(text: str, output_mp3_path: Path, **kwargs: object) -> None:
        _make_dummy_wav(output_mp3_path, duration_s=1.2)

    with patch("aidub.adapters.voice.edge_tts_adapter.EdgeTTSAdapter.synthesize_to_file", side_effect=_mock_synth):
        result = cloner.synthesize_character_voice(
            text="সাধারণ ব্যাকআপ সংলাপ",
            output_wav_path=out_audio,
            reference_audio_paths=[],  # Empty references
            character_name="Unknown_Extra",
        )

    assert result.success is True
    assert Path(result.stage2_converted_path).is_file()
