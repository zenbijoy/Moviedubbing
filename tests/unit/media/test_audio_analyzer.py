"""Real signal-level checks for the streamed audio analyzer."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from aidub.analysis.audio_analyzer import AudioAnalysisCancelled, analyze_audio_file


def test_audio_analyzer_measures_level_silence_and_pitch(tmp_path) -> None:
    sample_rate = 48_000
    timeline = np.arange(sample_rate * 3, dtype=np.float32) / sample_rate
    signal = np.zeros_like(timeline)
    audible = (timeline < 1.0) | (timeline >= 2.0)
    signal[audible] = 0.4 * np.sin(2 * np.pi * 220 * timeline[audible])
    source = tmp_path / "measured-tone.wav"
    sf.write(source, signal, sample_rate)

    report = analyze_audio_file(source, duration_seconds=3.0)

    assert report.analyzed_seconds == pytest.approx(3.0, abs=0.02)
    assert report.source_sample_rate_hz == sample_rate
    assert report.source_channels == 1
    assert report.peak_dbfs == pytest.approx(-7.96, abs=0.15)
    assert report.silence_percent == pytest.approx(33.3, abs=2.0)
    assert report.active_audio_percent == pytest.approx(66.7, abs=2.0)
    assert report.pitch_median_hz == pytest.approx(220.0, abs=8.0)
    assert report.spectral_centroid_hz > 100
    assert "not speech recognition" in report.measurement_note


def test_audio_analyzer_rejects_a_missing_source(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        analyze_audio_file(tmp_path / "missing.wav", duration_seconds=1.0)


def test_audio_analyzer_stops_when_cancel_requested(tmp_path) -> None:
    sample_rate = 16_000
    signal = np.sin(2 * np.pi * 180 * np.arange(sample_rate * 2) / sample_rate)
    source = tmp_path / "cancel-tone.wav"
    sf.write(source, signal, sample_rate)

    with pytest.raises(AudioAnalysisCancelled):
        analyze_audio_file(
            source,
            duration_seconds=2.0,
            cancel_requested=lambda: True,
        )
