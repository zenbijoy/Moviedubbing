"""Tests for FadeEngine."""
from __future__ import annotations

import numpy as np

from aidub.application.audio.fade_engine import FadeEngine
from aidub.domain.audio_edit import FadeSpec, FadeType
from aidub.media.pro_audio_editor import AudioClipData


def _clip(sr: int = 1000, n: int = 1000) -> AudioClipData:
    samples = np.ones(n, dtype=np.float32) * 0.5
    return AudioClipData(samples=samples, sample_rate=sr)


def test_fade_in_starts_silent():
    clip = _clip()
    fade = FadeSpec(duration_s=0.2, fade_type=FadeType.LINEAR, is_fade_in=True)
    out = FadeEngine().apply_fade(clip, fade)
    assert out.samples[0] == 0.0 or abs(out.samples[0]) < 1e-6
    assert abs(out.samples[-1] - 0.5) < 1e-6


def test_fade_out_ends_silent():
    clip = _clip()
    fade = FadeSpec(duration_s=0.2, fade_type=FadeType.LINEAR, is_fade_in=False)
    out = FadeEngine().apply_fade(clip, fade)
    assert abs(out.samples[0] - 0.5) < 1e-6
    assert abs(out.samples[-1]) < 1e-6


def test_fade_empty_clip():
    clip = AudioClipData(samples=np.array([], dtype=np.float32), sample_rate=1000)
    fade = FadeSpec(duration_s=0.1)
    out = FadeEngine().apply_fade(clip, fade)
    assert out.samples.size == 0


def test_apply_fades_multiple():
    clip = _clip()
    fades = [FadeSpec(duration_s=0.1, is_fade_in=True), FadeSpec(duration_s=0.1, is_fade_in=False)]
    out = FadeEngine().apply_fades(clip, fades)
    assert abs(out.samples[0]) < 1e-6
    assert abs(out.samples[-1]) < 1e-6
