"""Unit tests for sample-accurate timeline assembly and drift prevention (ADR-001)."""

from __future__ import annotations

import math
import struct
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from aidub.domain.time import AudioSamplePosition, RationalRate, RationalTime
from aidub.media.assemble import assemble_timeline


def _create_test_clip(path: Path, duration_s: float, freq_hz: float = 440.0, sr: int = 48_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, total_samples, endpoint=False, dtype=np.float32)
    waveform = (0.5 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    sf.write(str(path), waveform, sr)
    return path


def test_assemble_timeline_48khz_default_and_exact_duration(tmp_path: Path) -> None:
    clip1 = _create_test_clip(tmp_path / "clip1.wav", duration_s=1.0, freq_hz=440.0)
    clip2 = _create_test_clip(tmp_path / "clip2.wav", duration_s=1.0, freq_hz=880.0)

    out_wav = tmp_path / "assembled.wav"
    total_duration = 5.0
    assemble_timeline(
        placed_segments=[(0.5, clip1), (2.0, clip2)],
        total_duration_s=total_duration,
        output_wav=out_wav,
    )

    assert out_wav.is_file()
    data, sr = sf.read(str(out_wav))
    assert sr == 48_000  # ADR-001 broadcast audio standard
    expected_samples = int(total_duration * 48_000)
    assert len(data) == expected_samples


def test_assemble_timeline_supports_rational_time_and_sample_positions(tmp_path: Path) -> None:
    clip = _create_test_clip(tmp_path / "clip.wav", duration_s=0.5, freq_hz=440.0)
    out_wav = tmp_path / "assembled_rational.wav"

    # Place using RationalTime at 24000/1001 fps
    fps_ntsc = RationalRate(numerator=24_000, denominator=1_001)
    rt_pos = RationalTime(ticks=48, rate=fps_ntsc)  # exactly 2 seconds into video

    # Place using AudioSamplePosition
    sample_pos = AudioSamplePosition(sample_index=48_000 * 3, sample_rate=48_000)  # 3 seconds

    assemble_timeline(
        placed_segments=[(rt_pos, clip), (sample_pos, clip)],
        total_duration_s=4.0,
        output_wav=out_wav,
    )

    assert out_wav.is_file()
    data, sr = sf.read(str(out_wav))
    assert sr == 48_000
    assert len(data) == 4 * 48_000

    # Verify that energy exists at exact sample placement
    # Position 1: 48 frames at 24000/1001 -> 48 * 2002 = 96096 samples
    expected_sample_1 = 48 * 2002
    assert np.max(np.abs(data[expected_sample_1 : expected_sample_1 + 1000])) > 0.05

    # Position 2: sample 144,000 (3.0s)
    assert np.max(np.abs(data[144_000 : 144_000 + 1000])) > 0.05


def test_assemble_timeline_prevents_cascading_sync_drift_on_overlap(tmp_path: Path) -> None:
    """
    Critical ADR-001 test: If line 1 has an overrunning tail (e.g. 1.8s long placed at t=0s),
    line 2 (scheduled at t=1.0s) must NOT be pushed to t=1.8s.
    It must anchor to t=1.0s so downstream lip-sync does not drift across the movie.
    """
    long_tail_clip = _create_test_clip(tmp_path / "long.wav", duration_s=1.8, freq_hz=300.0)
    next_line_clip = _create_test_clip(tmp_path / "next.wav", duration_s=0.5, freq_hz=1000.0)

    out_wav = tmp_path / "no_drift.wav"
    assemble_timeline(
        placed_segments=[(0.0, long_tail_clip), (1.0, next_line_clip)],
        total_duration_s=3.0,
        output_wav=out_wav,
    )

    data, sr = sf.read(str(out_wav))
    assert sr == 48_000

    # The 1000 Hz tone of line 2 must start at sample 48,000 (1.0s), not at 1.8s (sample 86,400)
    line2_start_sample = 48_000
    window = data[line2_start_sample : line2_start_sample + 4800]
    # Check FFT or energy presence at 1000 Hz around 1.0s
    fft_mag = np.abs(np.fft.rfft(window))
    freqs = np.fft.rfftfreq(len(window), 1.0 / sr)
    idx_1000 = np.argmin(np.abs(freqs - 1000.0))
    # Prominent peak at 1000 Hz at t=1.0s confirms line 2 anchored properly without drift!
    assert fft_mag[idx_1000] > 10.0
