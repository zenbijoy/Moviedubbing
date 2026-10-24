"""Unit tests for professional dynamic sidechain dialogue ducking."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from aidub.media.ffmpeg_ops import dynamic_sidechain_mix, probe


def _generate_sine_wav(path: Path, duration_s: float = 2.0, freq: float = 440.0, volume: float = 0.5) -> Path:
    sr = 44100
    num_samples = int(duration_s * sr)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(num_samples):
            val = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq * (i / sr)))
            val = max(-32768, min(32767, val))
            # stereo 16-bit
            frames.extend(struct.pack("<hh", val, val))
        wf.writeframes(frames)
    return path


def test_dynamic_sidechain_mix_creates_valid_output(tmp_path: Path) -> None:
    voice = _generate_sine_wav(tmp_path / "voice.wav", duration_s=1.5, freq=500.0, volume=0.8)
    music = _generate_sine_wav(tmp_path / "music.wav", duration_s=2.0, freq=220.0, volume=0.4)
    out_wav = tmp_path / "mixed.wav"

    res = dynamic_sidechain_mix(
        voice_path=voice,
        music_path=music,
        out_path=out_wav,
        threshold_db=-25.0,
        ducking_ratio=4.0,
    )

    assert res.is_file()
    assert res.stat().st_size > 0

    info = probe(res)
    audio_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert audio_stream["channels"] == 2
    assert float(info["format"]["duration"]) >= 1.4


def test_dynamic_sidechain_mix_fallback_on_invalid_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    voice = _generate_sine_wav(tmp_path / "voice.wav", duration_s=1.0)
    music = _generate_sine_wav(tmp_path / "music.wav", duration_s=1.0)
    out_wav = tmp_path / "fallback.wav"

    # Verify graceful fallback when an extreme/invalid threshold is handled
    res = dynamic_sidechain_mix(
        voice_path=voice,
        music_path=music,
        out_path=out_wav,
        threshold_db=-120.0,  # very low threshold
    )
    assert res.is_file()
    assert res.stat().st_size > 0
