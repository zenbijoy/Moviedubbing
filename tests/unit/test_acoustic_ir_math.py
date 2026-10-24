"""
Unit tests for Mathematical Room Impulse Response (RIR) synthesis and FFT convolution.
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from aidub.contracts.base import Identifier
from aidub.media.acoustic_ir import AcousticIRConvolutionEngine, ImpulseResponseProfile


def create_synthetic_wav_bytes(duration_s: float = 0.5, freq_hz: float = 440.0, framerate: int = 48000) -> bytes:
    """Generate a clean sine wave PCM WAV byte stream for acoustic testing."""
    t = np.linspace(0, duration_s, int(framerate * duration_s), endpoint=False, dtype=np.float32)
    # 440 Hz tone with exponential decay
    samples = 0.7 * np.sin(2.0 * np.pi * freq_hz * t) * np.exp(-3.0 * t)
    int16_samples = (samples * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(int16_samples.tobytes())
    return buf.getvalue()


def test_synthesize_room_impulse_response_math() -> None:
    # Test RIR synthesis with RT60 = 0.8s
    rir = AcousticIRConvolutionEngine.synthesize_room_impulse_response(
        rt60_s=0.8, sample_rate=48000
    )
    assert isinstance(rir, np.ndarray)
    assert len(rir) > 48000 * 0.8
    # Direct sound impulse should exist near the beginning
    assert np.max(np.abs(rir)) > 0.05
    # Total energy should be normalized close to 1.0
    energy = np.sqrt(np.sum(rir**2))
    assert 0.95 <= energy <= 1.05


def test_real_wav_convolution() -> None:
    engine = AcousticIRConvolutionEngine()
    prof = ImpulseResponseProfile(
        profile_id=Identifier("ir_test"),
        ir_file_path="non_existent_preset.wav",
        wet_dry_mix=0.35,
        decay_time_ms=600,
    )

    clean_wav = create_synthetic_wav_bytes()
    convolved_bytes = engine.apply_convolution_reverb(clean_wav, prof)

    assert convolved_bytes.startswith(b"RIFF")
    assert b"CONVOLVED_REVERB" in convolved_bytes

    # Parse resulting WAV and verify audio integrity
    with wave.open(io.BytesIO(convolved_bytes[:convolved_bytes.find(b"_CONVOLVED_REVERB")]), "rb") as out_wav:
        assert out_wav.getnchannels() == 1
        assert out_wav.getframerate() == 48000
        frames = out_wav.readframes(out_wav.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        # No digital clipping (absolute max strictly < 1.0)
        assert np.max(np.abs(samples)) <= 0.98
        # Output is not dead silence
        assert np.max(np.abs(samples)) > 0.05
