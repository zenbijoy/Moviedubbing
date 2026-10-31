"""
Unit Test Suite for Cubase Pro & Nuendo DAW Features Clone.

Covers:
  1. CubaseVariAudioEngine: Syllable pitch detection, formant shift, intonation quantization.
  2. CubaseAudioAlignmentEngine: DTW timing alignment, correlation improvement, WSOLA time warp.
  3. CubaseDopEngine: Direct Offline Processing chain (Tube Saturation, Gate, EQ, De-Esser, Limiter).
  4. CubaseControlRoomEngine: Master monitoring matrix, Dim (-20dB), Mono fold-down, EBU R128 telemetry.
  5. CubaseCrossfadeEngine: Equal Power, S-Curve, Linear crossfades, midpoint skew, seamless splicing.
  6. Dialog UI Instantiations: VariAudio, Alignment, DOP, Control Room, Crossfade.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from aidub.media.cubase_audio_align import AlignmentTolerance, CubaseAudioAlignmentEngine
from aidub.media.cubase_control_room import (
    CubaseControlRoomEngine,
    LoudnessTelemetry,
    MonitorSource,
)
from aidub.media.cubase_crossfade import (
    CrossfadeSettings,
    CrossfadeShape,
    CubaseCrossfadeEngine,
)
from aidub.media.cubase_dop import CubaseDopEngine, DopProcessStep, DopProcessType
from aidub.media.cubase_variaudio import CubaseVariAudioEngine, VariAudioSegment
from aidub.media.pro_audio_editor import AudioClipData

try:
    from PySide6.QtWidgets import QApplication

    from aidub.ui.dialogs.cubase_audio_align_dialog import CubaseAudioAlignmentDialog
    from aidub.ui.dialogs.cubase_control_room_dialog import CubaseControlRoomDialog
    from aidub.ui.dialogs.cubase_crossfade_dialog import CubaseCrossfadeDialog
    from aidub.ui.dialogs.cubase_dop_dialog import CubaseDopDialog
    from aidub.ui.dialogs.cubase_variaudio_dialog import CubaseVariAudioDialog

    _QT = True
except ImportError:
    _QT = False


@pytest.fixture(scope="session")
def qapp():
    if not _QT:
        return None
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def speech_synthetic_clip() -> AudioClipData:
    """Generate 1.5s multi-harmonic vocal clip simulating speech syllables."""
    sr = 44100
    dur = 1.5
    n = int(dur * sr)
    t = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)

    # 3 distinct syllables with short pauses
    f0_contour = 140.0 + 20.0 * np.sin(2 * np.pi * 1.5 * t)
    phase = 2 * np.pi * np.cumsum(f0_contour) / sr

    sig = (
        0.4 * np.sin(phase)
        + 0.25 * np.sin(2 * phase)
        + 0.15 * np.sin(3 * phase)
        + 0.08 * np.sin(4 * phase)
    )

    # Vowel envelope modulation with pauses
    env = 0.5 * (1.0 + np.sin(2 * np.pi * 3.0 * t))
    env = np.clip(env - 0.2, 0.0, 1.0)
    sig = (sig * env).astype(np.float32)

    return AudioClipData(samples=sig, sample_rate=sr)


# ==============================================================================
# 1. VariAudio 3 Engine Tests
# ==============================================================================


def test_variaudio_segment_detection(speech_synthetic_clip):
    engine = CubaseVariAudioEngine(speech_synthetic_clip.sample_rate)
    segments = engine.detect_segments(speech_synthetic_clip)

    assert len(segments) > 0
    for seg in segments:
        assert seg.start_s >= 0.0
        assert seg.end_s > seg.start_s
        assert seg.pitch_hz > 40.0
        assert seg.is_voiced is True


def test_variaudio_quantize_intonation(speech_synthetic_clip):
    engine = CubaseVariAudioEngine(speech_synthetic_clip.sample_rate)
    segments = engine.detect_segments(speech_synthetic_clip)
    assert len(segments) > 0

    quantized = engine.quantize_pitch_to_speech_intonation(segments, strength=0.8)

    assert len(quantized) == len(segments)
    for seg in quantized:
        assert isinstance(seg.pitch_cents, float)


def test_variaudio_pitch_and_formant_processing(speech_synthetic_clip):
    engine = CubaseVariAudioEngine(speech_synthetic_clip.sample_rate)
    segments = engine.detect_segments(speech_synthetic_clip)
    if segments:
        segments[0].pitch_cents = 35.0
        segments[0].formant_shift_semitones = 1.5

    processed = engine.apply_segment_edits(speech_synthetic_clip, segments)
    assert isinstance(processed, AudioClipData)
    assert processed.sample_rate == speech_synthetic_clip.sample_rate
    assert processed.samples.size > 0
    assert not np.isnan(processed.samples).any()
    assert not np.isinf(processed.samples).any()


# ==============================================================================
# 2. Audio Alignment Engine Tests (VocAlign Pro Clone)
# ==============================================================================


def test_audio_alignment_envelope_and_dtw(speech_synthetic_clip):
    engine = CubaseAudioAlignmentEngine()
    guide = speech_synthetic_clip
    # Create target by shifting guide by 100ms
    shift_samples = int(guide.sample_rate * 0.1)
    target_samples = np.pad(guide.samples, (shift_samples, 0))[: guide.samples.size]
    target = AudioClipData(samples=target_samples, sample_rate=guide.sample_rate)

    env_guide = engine._extract_envelope(guide.samples, 441)
    env_target = engine._extract_envelope(target.samples, 441)
    assert env_guide.size > 0
    assert env_target.size > 0

    aligned, report = engine.align_dialogue(guide, target, tolerance=AlignmentTolerance.STANDARD)
    assert isinstance(aligned, AudioClipData)
    assert aligned.samples.size > 0
    assert not np.isnan(aligned.samples).any()

    # Telemetry check: correlation must improve after DTW alignment
    assert -1.0 <= report.initial_correlation <= 1.0
    assert -1.0 <= report.aligned_correlation <= 1.0
    assert report.aligned_correlation > report.initial_correlation
    assert report.average_drift_ms >= 0.0


def test_audio_alignment_tolerance_modes(speech_synthetic_clip):
    engine = CubaseAudioAlignmentEngine()
    guide = speech_synthetic_clip
    target = speech_synthetic_clip.clone()

    for mode in [AlignmentTolerance.TIGHT, AlignmentTolerance.STANDARD, AlignmentTolerance.LOOSE]:
        aligned, report = engine.align_dialogue(guide, target, tolerance=mode)
        assert aligned.duration_s > 0.0
        assert report.tolerance_mode == mode


# ==============================================================================
# 3. Direct Offline Processing (DOP F7) Tests
# ==============================================================================


def test_cubase_dop_engine_chain(speech_synthetic_clip):
    engine = CubaseDopEngine()

    steps = [
        engine.create_step(DopProcessType.TUBE_SATURATION, drive_db=4.0, warmth=0.7),
        engine.create_step(DopProcessType.NOISE_GATE, threshold_db=-45.0),
        engine.create_step(
            DopProcessType.PARAMETRIC_EQ,
            low_mid_gain_db=1.5,
            high_mid_gain_db=2.0,
            high_shelf_gain_db=1.0,
        ),
        engine.create_step(DopProcessType.DE_ESSER, threshold_db=-24.0, freq_hz=6800.0),
        engine.create_step(DopProcessType.BRICKWALL_LIMITER, ceiling_db=-1.0),
    ]

    assert len(steps) == 5
    for s in steps:
        assert s.is_active is True

    processed = engine.render_dop_chain(speech_synthetic_clip, steps)
    assert isinstance(processed, AudioClipData)
    assert processed.sample_rate == speech_synthetic_clip.sample_rate
    assert processed.duration_s > 0.0
    assert not np.isnan(processed.samples).any()
    # Limiter ceiling test: max peak must not exceed 0 dBFS
    assert processed.peak_dbfs <= 0.1


def test_cubase_dop_bypass_toggle(speech_synthetic_clip):
    engine = CubaseDopEngine()
    step = engine.create_step(DopProcessType.TUBE_SATURATION, drive_db=12.0)
    step.is_active = False

    processed = engine.render_dop_chain(speech_synthetic_clip, [step])
    # When bypassed (inactive), processed samples should match input
    diff = np.max(np.abs(processed.samples - speech_synthetic_clip.samples))
    assert diff < 1e-4


# ==============================================================================
# 4. Control Room & Loudness Radar Tests
# ==============================================================================


def test_cubase_control_room_monitoring(speech_synthetic_clip):
    cr = CubaseControlRoomEngine()

    dub_clip = speech_synthetic_clip
    guide_clip = speech_synthetic_clip.clone()

    # Source switching
    cr.set_source(MonitorSource.MAIN_DUB)
    out_dub = cr.route_monitor_audio(dub_clip, guide_clip)
    assert np.allclose(out_dub.samples, dub_clip.samples)

    cr.set_source(MonitorSource.REF_GUIDE)
    out_guide = cr.route_monitor_audio(dub_clip, guide_clip)
    assert np.allclose(out_guide.samples, guide_clip.samples)

    # Dim (-20 dB) attenuation check: 10^(-20/20) = 0.1
    cr.set_source(MonitorSource.MAIN_DUB)
    cr.is_dimmed = True
    out_dim = cr.route_monitor_audio(dub_clip, guide_clip)
    expected = dub_clip.samples * (10.0 ** (-20.0 / 20.0))
    assert np.allclose(out_dim.samples, expected, atol=1e-4)

    # Mono fold-down
    cr.is_dimmed = False
    cr.is_mono = True
    out_mono = cr.route_monitor_audio(dub_clip, guide_clip)
    assert out_mono.samples.size == dub_clip.samples.size


def test_cubase_control_room_loudness_radar(speech_synthetic_clip):
    cr = CubaseControlRoomEngine()
    telemetry = cr.measure_loudness(speech_synthetic_clip)

    assert isinstance(telemetry, LoudnessTelemetry)
    assert -70.0 <= telemetry.integrated_lufs <= 0.0
    assert -70.0 <= telemetry.short_term_lufs <= 0.0
    assert telemetry.true_peak_dbfs <= 1.0
    assert telemetry.loudness_range_lu >= 0.0


# ==============================================================================
# 5. Crossfade Engine Tests
# ==============================================================================


def test_cubase_crossfade_curves():
    engine = CubaseCrossfadeEngine()
    n_pts = 100

    # Equal power: fade_out^2 + fade_in^2 ≈ 1.0 (constant energy sum)
    cfg_eq = CrossfadeSettings(shape=CrossfadeShape.EQUAL_POWER, midpoint_skew_pct=0.0)
    f_out, f_in = engine.generate_curves(n_pts, cfg_eq)
    power_sum = f_out**2 + f_in**2
    assert np.allclose(power_sum, 1.0, atol=1e-3)

    # S-Curve
    cfg_s = CrossfadeSettings(shape=CrossfadeShape.S_CURVE, midpoint_skew_pct=0.0)
    f_out_s, f_in_s = engine.generate_curves(n_pts, cfg_s)
    assert f_out_s[0] == pytest.approx(1.0, abs=1e-3)
    assert f_out_s[-1] == pytest.approx(0.0, abs=1e-3)
    assert f_in_s[0] == pytest.approx(0.0, abs=1e-3)
    assert f_in_s[-1] == pytest.approx(1.0, abs=1e-3)

    # Linear / Equal Gain
    cfg_lin = CrossfadeSettings(shape=CrossfadeShape.EQUAL_GAIN, midpoint_skew_pct=0.0)
    f_out_lin, f_in_lin = engine.generate_curves(n_pts, cfg_lin)
    gain_sum = f_out_lin + f_in_lin
    assert np.allclose(gain_sum, 1.0, atol=1e-3)


def test_cubase_crossfade_splicing(speech_synthetic_clip):
    engine = CubaseCrossfadeEngine()
    clip_a = speech_synthetic_clip
    clip_b = speech_synthetic_clip.clone()

    settings = CrossfadeSettings(
        duration_ms=50.0,
        shape=CrossfadeShape.EQUAL_POWER,
        midpoint_skew_pct=0.0,
    )

    spliced = engine.splice_clips(clip_a, clip_b, settings)
    assert isinstance(spliced, AudioClipData)
    expected_dur = clip_a.duration_s + clip_b.duration_s - (settings.duration_ms / 1000.0)
    assert math.isclose(spliced.duration_s, expected_dur, rel_tol=1e-2)
    assert not np.isnan(spliced.samples).any()


# ==============================================================================
# 6. Dialog UI Instantiations Tests
# ==============================================================================


@pytest.mark.skipif(not _QT, reason="Qt bindings unavailable in headless run")
def test_cubase_dialogs_instantiation(qapp, speech_synthetic_clip):
    # 1. VariAudio Dialog
    va_dlg = CubaseVariAudioDialog(speech_synthetic_clip, character_name="Protagonist")
    assert va_dlg.windowTitle().startswith("Cubase VariAudio 3")
    assert len(va_dlg.segments) > 0
    va_dlg.close()

    # 2. Audio Alignment Dialog
    guide = speech_synthetic_clip
    target = speech_synthetic_clip.clone()
    align_dlg = CubaseAudioAlignmentDialog(guide, target, cue_id="cue_042")
    assert "Audio Alignment Panel" in align_dlg.windowTitle()
    align_dlg.close()

    # 3. Direct Offline Processing Dialog
    dop_dlg = CubaseDopDialog(speech_synthetic_clip, cue_id="cue_042")
    assert "Direct Offline Processing" in dop_dlg.windowTitle()
    assert len(dop_dlg.steps) >= 3
    dop_dlg.close()

    # 4. Control Room Dialog
    cr_dlg = CubaseControlRoomDialog(speech_synthetic_clip, guide_clip=guide)
    assert "Cubase Control Room" in cr_dlg.windowTitle()
    cr_dlg.close()

    # 5. Crossfade Dialog
    xfade_dlg = CubaseCrossfadeDialog(clip_a=guide, clip_b=target)
    assert "Crossfade Editor" in xfade_dlg.windowTitle()
    xfade_dlg.close()
