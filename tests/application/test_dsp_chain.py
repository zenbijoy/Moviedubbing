"""
Unit tests for DspChain application service.
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.application.audio.dsp_chain import DspChain
from aidub.domain.audio_edit import DspEffectType, EffectRack
from aidub.media.pro_audio_editor import AudioClipData


def test_dsp_chain_gain_and_normalize() -> None:
    chain = DspChain()

    # Generate a simple 48000 Hz sine wave
    sr = 48000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    samples = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    clip = AudioClipData(samples=samples, sample_rate=sr)

    # Initial peak is approx -12 dBFS
    assert clip.peak_dbfs == pytest.approx(-12.04, abs=0.2)

    # Apply +6 dB gain
    gained = chain.apply_gain(clip, gain_db=6.0)
    assert gained.peak_dbfs == pytest.approx(-6.04, abs=0.2)

    # Normalize to -1.0 dBFS
    normalized = chain.normalize_peak(clip, target_peak_dbfs=-1.0)
    assert normalized.peak_dbfs == pytest.approx(-1.0, abs=0.1)


def test_dsp_chain_rack_processing() -> None:
    chain = DspChain()

    sr = 48000
    samples = (0.5 * np.sin(2 * np.pi * 1000 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)
    clip = AudioClipData(samples=samples, sample_rate=sr)

    rack = EffectRack()
    rack.add_effect(
        DspEffectType.PARAMETRIC_EQ,
        low_shelf_gain_db=2.0,
        high_shelf_gain_db=-3.0,
    )
    rack.add_effect(
        DspEffectType.LEVELER_LIMITER,
        target_loudness_dbfs=-16.0,
        true_peak_limit_dbfs=-1.0,
    )

    processed = chain.process_clip(clip, rack)
    assert processed.samples.size == clip.samples.size
    # Ensure true peak limiter respected -1.0 dBFS
    assert processed.peak_dbfs <= -0.95


def test_dsp_chain_master_bypass() -> None:
    chain = DspChain()

    sr = 48000
    samples = np.ones(1000, dtype=np.float32) * 0.5
    clip = AudioClipData(samples=samples, sample_rate=sr)

    rack = EffectRack(master_bypass=True)
    rack.add_effect(DspEffectType.PARAMETRIC_EQ, high_shelf_gain_db=12.0)

    processed = chain.process_clip(clip, rack)
    # Master bypass ensures clip remains identical
    np.testing.assert_array_equal(processed.samples, clip.samples)
