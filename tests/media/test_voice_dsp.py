"""Unit tests for Voice DSP acoustic analysis, SNR estimation, and similarity measurement."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import numpy as np

from aidub.media.voice_dsp import (
    analyze_voice_audio,
    measure_acoustic_similarity,
    normalize_audio_levels,
)


def _generate_test_wav(
    path: Path,
    *,
    duration_s: float = 3.5,
    sample_rate: int = 16000,
    freq: float = 440.0,
    noise_level: float = 0.01,
    clipped: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, n_samples, endpoint=False, dtype=np.float32)
    # Sine wave signal with harmonics
    signal = 0.6 * np.sin(2 * math.pi * freq * t) + 0.2 * np.sin(2 * math.pi * (freq * 2) * t)
    # Add random noise
    noise = np.random.normal(0, noise_level, n_samples).astype(np.float32)
    combined = signal + noise

    if clipped:
        combined[100:300] = 1.0
        combined[500:700] = -1.0

    combined = np.clip(combined, -1.0, 1.0)
    int_samples = (combined * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_samples.tobytes())

    return path


def test_analyze_voice_audio_good_file(tmp_path: Path) -> None:
    wav_path = _generate_test_wav(tmp_path / "clean_voice.wav", duration_s=4.0, noise_level=0.005)
    rep = analyze_voice_audio(wav_path)

    assert rep.duration_s >= 3.9
    assert rep.sample_rate == 16000
    assert rep.channels == 1
    assert rep.snr_db > 15.0
    assert rep.has_clipping is False
    assert rep.is_suitable_for_cloning is True
    assert rep.quality_rating in {"good", "excellent"}


def test_analyze_voice_audio_short_clip_warning(tmp_path: Path) -> None:
    wav_path = _generate_test_wav(tmp_path / "short_voice.wav", duration_s=1.5)
    rep = analyze_voice_audio(wav_path, min_speech_duration_s=3.0)

    assert rep.duration_s < 2.0
    assert any("shorter than recommended" in w for w in rep.warnings)


def test_analyze_voice_audio_clipping_detection(tmp_path: Path) -> None:
    wav_path = _generate_test_wav(tmp_path / "clipped_voice.wav", duration_s=3.5, clipped=True)
    rep = analyze_voice_audio(wav_path)

    assert rep.has_clipping is True
    assert any("clipping" in w.lower() for w in rep.warnings)


def test_analyze_voice_audio_missing_file() -> None:
    rep = analyze_voice_audio("non_existent_file.wav")
    assert rep.duration_s == 0.0
    assert rep.is_suitable_for_cloning is False
    assert rep.quality_rating == "rejected"
    assert len(rep.warnings) > 0


def test_measure_acoustic_similarity_identical_and_different(tmp_path: Path) -> None:
    wav_a = _generate_test_wav(tmp_path / "voice_a.wav", duration_s=3.0, freq=300.0)
    wav_b = _generate_test_wav(tmp_path / "voice_b.wav", duration_s=3.0, freq=300.0)
    wav_c = _generate_test_wav(tmp_path / "voice_c.wav", duration_s=3.0, freq=800.0)

    # Identical spectra
    score_identical = measure_acoustic_similarity(wav_a, wav_b)
    assert 0.90 <= score_identical <= 1.0

    # Different spectra
    score_different = measure_acoustic_similarity(wav_a, wav_c)
    assert 0.0 <= score_different < score_identical


def test_normalize_audio_levels(tmp_path: Path) -> None:
    in_wav = _generate_test_wav(tmp_path / "quiet.wav", duration_s=2.0)
    out_wav = tmp_path / "normalized.wav"

    res_path = normalize_audio_levels(in_wav, out_wav, target_peak_dbfs=-1.0)
    assert res_path.exists()

    with wave.open(str(out_wav), "rb") as wf:
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        samples = np.array(struct.unpack(f"<{n_frames}h", data), dtype=np.float32) / 32768.0
        peak = np.max(np.abs(samples))
        # -1.0 dBFS is ~0.891 full scale
        assert 0.85 <= peak <= 0.95
