"""
Unit tests for ITU-R BS.1770-4 Broadcast QC and Certification Engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.analysis.broadcast_qc import (
    BroadcastQCCertificate,
    BroadcastQCEngine,
    DeliverySpec,
    LoudnessQCResult,
)


def test_k_weighting_filter_creation() -> None:
    b_shelf, a_shelf, b_hp, a_hp = BroadcastQCEngine.get_k_weighting_filters(48000)
    assert len(b_shelf) == 3
    assert len(a_shelf) == 3
    assert len(b_hp) == 3
    assert len(a_hp) == 3
    # First coefficient of denominator should be 1.0
    assert a_shelf[0] == pytest.approx(1.0)
    assert a_hp[0] == pytest.approx(1.0)


def test_true_peak_and_loudness_analysis() -> None:
    fs = 48000
    duration_s = 1.0
    t = np.linspace(0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)

    # 1 kHz test tone at -20 dBFS (amplitude = 0.1)
    amplitude = 0.1
    samples = amplitude * np.sin(2.0 * np.pi * 1000.0 * t)

    metrics = BroadcastQCEngine.analyze_audio_samples(samples, fs=fs)
    assert isinstance(metrics, LoudnessQCResult)
    assert metrics.channels == 1
    assert metrics.sample_rate == fs
    # 1 kHz tone at -20 dBFS has K-weighted loudness around -20 to -24 LUFS
    assert -28.0 <= metrics.integrated_lufs <= -16.0
    # True-Peak should be near -20 dBTP
    assert -22.0 <= metrics.true_peak_dbtp <= -18.0


def test_evaluate_compliance_netflix() -> None:
    # Construct a metrics object that passes Netflix criteria
    pass_metrics = LoudnessQCResult(
        integrated_lufs=-24.1,
        loudness_range_lu=12.0,
        true_peak_dbtp=-1.5,
        sample_peak_dbfs=-1.8,
        duration_s=120.0,
        channels=6,
        sample_rate=48000,
    )

    cert_pass = BroadcastQCEngine.evaluate_compliance(
        pass_metrics, spec=DeliverySpec.NETFLIX, media_name="feature_film_netflix_51.mp4"
    )
    assert cert_pass.passed is True
    assert cert_pass.clipping_detected is False
    assert len(cert_pass.remediation_actions) == 0

    formatted = cert_pass.to_formatted_certificate()
    assert "PASSED - BROADCAST CERTIFIED" in formatted
    assert "Netflix Post-Production Spec" in formatted

    # Test failure case (too loud: -18 LUFS, clipping: 0 dBFS)
    fail_metrics = LoudnessQCResult(
        integrated_lufs=-18.0,
        loudness_range_lu=22.0,
        true_peak_dbtp=+1.2,
        sample_peak_dbfs=0.0,
        duration_s=120.0,
        channels=2,
        sample_rate=48000,
    )

    cert_fail = BroadcastQCEngine.evaluate_compliance(
        fail_metrics, spec=DeliverySpec.NETFLIX, media_name="unmastered_audio.wav"
    )
    assert cert_fail.passed is False
    assert cert_fail.clipping_detected is True
    assert len(cert_fail.remediation_actions) >= 2
    assert cert_fail.gain_correction_db < 0.0  # Needs attenuation
