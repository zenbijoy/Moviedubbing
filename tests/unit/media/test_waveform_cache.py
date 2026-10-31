from pathlib import Path
import tempfile
import numpy as np
import pytest
import soundfile as sf

from aidub.media.waveform_cache import WaveformCache, DEFAULT_PEAKS_PER_SECOND


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    """Generate a 2-second stereo test WAV at 48kHz."""
    sr = 48000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Sine wave with amplitude 0.75
    left = 0.75 * np.sin(2 * np.pi * 440 * t)
    # Cosine wave with amplitude 0.5
    right = 0.5 * np.cos(2 * np.pi * 880 * t)
    audio = np.stack([left, right], axis=1).astype(np.float32)

    wav_path = tmp_path / "test_stereo_48k.wav"
    sf.write(str(wav_path), audio, sr)
    return wav_path


def test_waveform_cache_generation_and_caching(sample_wav: Path, tmp_path: Path):
    cache = WaveformCache(cache_dir=tmp_path / "peaks_cache")
    dur, peaks = cache.get_audio_peaks(sample_wav, peaks_per_second=50)

    assert dur == pytest.approx(2.0, abs=0.01)
    # 2 seconds at 50 peaks/sec -> ~100 peak points
    assert len(peaks) in (99, 100, 101)
    assert peaks.shape[1] == 2
    # Verify min is negative and max is positive
    assert np.min(peaks[:, 0]) < -0.4
    assert np.max(peaks[:, 1]) > 0.3

    # Verify cached load returns identical results
    dur2, peaks2 = cache.get_audio_peaks(sample_wav, peaks_per_second=50)
    assert dur2 == dur
    np.testing.assert_array_equal(peaks, peaks2)


def test_waveform_cache_query_slice(sample_wav: Path, tmp_path: Path):
    cache = WaveformCache(cache_dir=tmp_path / "peaks_cache")
    # Query 20 points for window [0.5s to 1.5s]
    points = cache.query_slice_peaks(sample_wav, start_sec=0.5, duration_sec=1.0, num_points=20)
    assert len(points) == 20
    for mn, mx in points:
        assert -1.0 <= mn <= mx <= 1.0


def test_waveform_cache_missing_file(tmp_path: Path):
    cache = WaveformCache(cache_dir=tmp_path / "peaks_cache")
    dur, peaks = cache.get_audio_peaks(tmp_path / "nonexistent.wav")
    assert dur == 0.0
    assert len(peaks) == 0

    points = cache.query_slice_peaks(tmp_path / "nonexistent.wav", 0.0, 5.0, 10)
    assert len(points) == 10
    assert all(p == (0.0, 0.0) for p in points)
