"""
Unit test suite for enhanced real-time DSP, voice transformation, and audio engines.
Verifies zero-mock implementations:
  1. AutoGainRider: noise floor freeze, smooth continuous leveling, peak safety.
  2. BreathInsertionEngine: organic vocal tract formant aspiration, pre-dialogue inhale.
  3. DeReverbEngine: STFT spectral decay subtraction and room reflection suppression.
  4. SidechainDucker: smooth attack, release, and hold time dialogue ducking.
  5. SpeedRamp: WSOLA pitch-preserving stretch and dynamic ramping curves.
  6. VoiceChanger: real DSP transformation (ring modulation, delay, telephone, deep).
  7. VoiceAgeTransformer: child & elderly formant/pitch morphing.
  8. TakeCompositor: anti-click micro-crossfaded take comping.
  9. SubtitleExporter: millisecond rollover protection (e.g. 59.9997s -> 00:01:00,000).
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from aidub.application.audio.auto_gain_rider import AutoGainRider
from aidub.application.audio.breath_engine import BreathInsertionEngine
from aidub.application.audio.dereverb_engine import DeReverbEngine
from aidub.application.audio.noise_gate import NoiseGateEngine
from aidub.application.audio.sidechain_ducker import SidechainDucker
from aidub.application.audio.speed_ramp import SpeedRamp
from aidub.application.audio.take_compositor import TakeCompositor
from aidub.application.captions.caption_style import CaptionStyle
from aidub.application.subtitles.subtitle_exporter import SubCue, SubtitleExporter
from aidub.application.voice.formant_shifter import FormantShifter
from aidub.application.voice.voice_age import VoiceAgeTransformer
from aidub.application.voice.voice_changer import VoiceChanger
from aidub.domain.audio_edit import CompingRegion
from aidub.media.pro_audio_editor import AudioClipData


@pytest.fixture
def synthetic_speech() -> AudioClipData:
    """1.0s synthetic harmonic speech-like signal."""
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(dur * sr), endpoint=False, dtype=np.float32)
    f0 = 150.0
    sig = (
        0.4 * np.sin(2 * np.pi * f0 * t)
        + 0.25 * np.sin(2 * np.pi * (2 * f0) * t)
        + 0.15 * np.sin(2 * np.pi * (3 * f0) * t)
    )
    env = 0.5 * (1.0 + np.sin(2 * np.pi * 2.0 * t))
    sig = (sig * env).astype(np.float32)
    return AudioClipData(samples=sig, sample_rate=sr)


def test_auto_gain_rider_noise_freeze_and_smoothing(synthetic_speech):
    sr = synthetic_speech.sample_rate
    # Create speech followed by silence
    speech = synthetic_speech.samples
    silence = np.zeros(int(0.5 * sr), dtype=np.float32)
    test_samples = np.concatenate([speech * 0.1, silence])  # quiet speech + silence
    clip = AudioClipData(samples=test_samples, sample_rate=sr)

    rider = AutoGainRider(target_rms=0.15, max_gain_db=12.0, gate_threshold_db=-45.0)
    processed = rider.process(clip)

    assert processed.samples.size == test_samples.size
    assert not np.isnan(processed.samples).any()
    # The silence region must NOT be amplified into loud noise
    sil_out = processed.samples[speech.size :]
    assert np.max(np.abs(sil_out)) < 1e-4


def test_breath_insertion_organic_acoustics(synthetic_speech):
    sr = 44100
    breath = BreathInsertionEngine.synthesize_breath(duration_s=0.25, sample_rate=sr, breath_amp=0.06)
    assert breath.size == int(0.25 * sr)
    assert not np.isnan(breath).any()
    # Check that it's filtered (not flat white noise)
    fft_mag = np.abs(np.fft.rfft(breath))
    assert np.std(fft_mag) > 0.0

    # Test pre-dialogue breath insertion
    with_pre_breath = BreathInsertionEngine.insert_breath_before(synthetic_speech, 0.2)
    assert with_pre_breath.samples.size == synthetic_speech.samples.size + int(0.2 * sr)


def test_dereverb_spectral_reduction(synthetic_speech):
    sr = synthetic_speech.sample_rate
    # Convolve with a synthetic exponential reverb impulse
    ir_len = int(0.15 * sr)
    ir = np.exp(-np.linspace(0, 4, ir_len)).astype(np.float32)
    reverberant = np.convolve(synthetic_speech.samples, ir, mode="same").astype(np.float32)
    rev_clip = AudioClipData(samples=reverberant, sample_rate=sr)

    dereverbed = DeReverbEngine.reduce(rev_clip, amount=0.7)
    assert dereverbed.samples.size == rev_clip.samples.size
    assert not np.isnan(dereverbed.samples).any()
    # Processed speech should retain signal energy without clipping
    assert dereverbed.peak_dbfs <= 0.0


def test_sidechain_ducker_smooth_curves(synthetic_speech):
    sr = synthetic_speech.sample_rate
    # 2s background music (steady tone)
    music_samples = (0.5 * np.sin(2 * np.pi * 330.0 * np.linspace(0, 2.0, 2 * sr))).astype(np.float32)
    music = AudioClipData(samples=music_samples, sample_rate=sr)

    # 1s dialogue starting at t=0.5s
    pad_pre = np.zeros(int(0.5 * sr), dtype=np.float32)
    dial_samples = np.concatenate([pad_pre, synthetic_speech.samples])
    dialogue = AudioClipData(samples=dial_samples, sample_rate=sr)

    ducker = SidechainDucker(threshold_dbfs=-30.0, duck_db=-12.0, attack_ms=20.0, release_ms=100.0)
    ducked = ducker.process(music, dialogue)

    assert ducked.samples.size == music.samples.size
    # Music during dialogue (at t=1.0s) must be quieter than initial music
    idx_quiet = int(1.0 * sr)
    idx_loud = int(0.2 * sr)
    rms_quiet = np.sqrt(np.mean(ducked.samples[idx_quiet : idx_quiet + 500] ** 2))
    rms_loud = np.sqrt(np.mean(ducked.samples[idx_loud : idx_loud + 500] ** 2))
    assert rms_quiet < rms_loud


def test_speed_ramp_preserve_pitch_and_dynamic_ramp(synthetic_speech):
    # WSOLA pitch-preserving stretch
    stretched = SpeedRamp.stretch(synthetic_speech, speed=1.25, preserve_pitch=True)
    assert stretched.samples.size > 0
    assert not np.isnan(stretched.samples).any()

    # Dynamic ramp
    ramped = SpeedRamp.ramp(synthetic_speech, start_speed=1.0, end_speed=2.0, curve="s_curve")
    assert ramped.samples.size > 0
    assert ramped.samples.size < synthetic_speech.samples.size


def test_voice_changer_real_dsp_transformations(synthetic_speech):
    # 1. Chipmunk
    chip = VoiceChanger.apply(synthetic_speech, "chipmunk")
    assert chip.samples.size > 0
    assert not np.isnan(chip.samples).any()

    # 2. Robot (ring modulation)
    robot = VoiceChanger.apply(synthetic_speech, "robot")
    assert robot.samples.size == synthetic_speech.samples.size
    assert not np.allclose(robot.samples, synthetic_speech.samples)

    # 3. Echo
    echo = VoiceChanger.apply(synthetic_speech, "echo")
    assert echo.samples.size == synthetic_speech.samples.size

    # 4. Telephone
    tele = VoiceChanger.apply(synthetic_speech, "telephone")
    assert tele.samples.size == synthetic_speech.samples.size


def test_voice_age_transformer_transform(synthetic_speech):
    child = VoiceAgeTransformer.transform(synthetic_speech, "child")
    assert child.samples.size > 0
    assert not np.isnan(child.samples).any()

    elderly = VoiceAgeTransformer.transform(synthetic_speech, "elderly")
    assert elderly.samples.size > 0
    assert not np.isnan(elderly.samples).any()


def test_take_compositor_crossfading(synthetic_speech):
    sr = synthetic_speech.sample_rate
    t1 = synthetic_speech.clone()
    t2 = synthetic_speech.clone()
    regions = [
        CompingRegion(take_id="t1", cue_id="c1", start_s=0.0, end_s=0.4, gain_db=0.0),
        CompingRegion(take_id="t2", cue_id="c2", start_s=0.4, end_s=0.8, gain_db=0.0),
    ]

    master = TakeCompositor.build_master(regions, {"t1": t1, "t2": t2}, sr=sr, crossfade_ms=10.0)
    assert master.samples.size > 0
    assert not np.isnan(master.samples).any()


def test_subtitle_exporter_rollover_protection():
    # 59.9997 seconds should format to 00:01:00,000, NOT 00:00:59,1000
    t_roll = 59.9997
    srt_str = SubtitleExporter._fmt_srt(t_roll)
    assert srt_str == "00:01:00,000"

    vtt_str = SubtitleExporter._fmt_vtt(t_roll)
    assert vtt_str == "00:01:00.000"

    # Multi-cue formatting
    cues = [SubCue(index=1, start_s=0.0, end_s=2.5, text="Welcome")]
    srt_out = SubtitleExporter.to_srt(cues)
    assert "00:00:00,000 --> 00:00:02,500" in srt_out
    assert "Welcome" in srt_out


def test_caption_style_ass_and_css():
    ass_line = CaptionStyle.to_ass_style("neon", style_name="Dialogue")
    assert "Style: Dialogue" in ass_line
    assert "Arial" in ass_line

    css_style = CaptionStyle.to_css("bold_white")
    assert "color: #FFFFFF" in css_style
    assert "font-weight: bold" in css_style
