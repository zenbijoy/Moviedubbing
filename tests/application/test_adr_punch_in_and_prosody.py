"""Unit tests for ADR Punch-In / Punch-Out Splicing and Prosody Rhythm Transfer."""

from __future__ import annotations

import numpy as np
import pytest

from aidub.application.adr.adr_recorder import ADRRecorder, PunchInSession
from aidub.application.voice.prosody_matcher import ProsodyMatcher


def test_adr_recorder_splice_punch_in() -> None:
    sr = 44100
    base_dur = 4.0
    recorder = ADRRecorder(sample_rate=sr)

    # Base track: 200 Hz tone
    t_base = np.linspace(0, base_dur, int(base_dur * sr), endpoint=False, dtype=np.float32)
    base_samples = 0.5 * np.sin(2 * np.pi * 200.0 * t_base)

    # Punch interval: from 1.0s to 2.5s (1.5s duration)
    tin = 1.0
    tout = 2.5
    punch_dur = tout - tin
    t_punch = np.linspace(0, punch_dur, int(punch_dur * sr), endpoint=False, dtype=np.float32)
    punch_samples = 0.5 * np.sin(2 * np.pi * 400.0 * t_punch)

    session = PunchInSession(
        punch_in_time=tin,
        punch_out_time=tout,
        pre_roll_sec=1.0,
        post_roll_sec=1.0,
        crossfade_ms=20.0,
    )

    spliced = recorder.splice_punch_in(
        base_samples=base_samples,
        punch_samples=punch_samples,
        session=session,
    )

    assert len(spliced) == len(base_samples)
    assert not np.isnan(spliced).any()
    # Before punch-in (e.g. at 0.5s): identical to base
    idx_before = int(0.5 * sr)
    assert pytest.approx(spliced[idx_before], abs=1e-4) == base_samples[idx_before]
    # During punch interval (e.g. at 1.8s): corresponds to punch samples
    idx_mid = int(1.8 * sr)
    idx_punch = int((1.8 - tin) * sr)
    assert pytest.approx(spliced[idx_mid], abs=1e-4) == punch_samples[idx_punch]
    # After punch-out (e.g. at 3.0s): identical to base
    idx_after = int(3.0 * sr)
    assert pytest.approx(spliced[idx_after], abs=1e-4) == base_samples[idx_after]


def test_prosody_matcher_transfer_prosody() -> None:
    sr = 44100
    dur = 2.0
    matcher = ProsodyMatcher(sample_rate=sr)

    t = np.linspace(0, dur, int(dur * sr), endpoint=False, dtype=np.float32)

    # Guide actor with high dynamic envelope (e.g. crescendo from 0.1 to 0.9)
    guide_envelope = np.linspace(0.1, 0.9, len(t), dtype=np.float32)
    guide_samples = guide_envelope * np.sin(2 * np.pi * 150.0 * t)

    # Flat dub take
    dub_samples = 0.4 * np.ones_like(t, dtype=np.float32) * np.sin(2 * np.pi * 180.0 * t)

    transferred = matcher.transfer_prosody(
        guide_samples=guide_samples,
        dub_samples=dub_samples,
        sample_rate=sr,
        energy_strength=0.8,
        pitch_weight=0.5,
        frame_len_ms=20.0,
    )

    assert len(transferred) == len(dub_samples)
    assert not np.isnan(transferred).any()
    # Transferred take should reflect the crescendo (end energy > start energy)
    start_rms = np.sqrt(np.mean(transferred[: int(0.3 * sr)] ** 2))
    end_rms = np.sqrt(np.mean(transferred[-int(0.3 * sr) :] ** 2))
    assert end_rms > start_rms
