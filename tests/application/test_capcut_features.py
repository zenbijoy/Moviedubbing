"""Tests for CapCut-style features."""
from __future__ import annotations

import numpy as np

from aidub.application.captions.auto_captioner import AutoCaptioner
from aidub.application.voice.voice_changer import VoiceChanger
from aidub.application.audio.speed_ramp import SpeedRamp
from aidub.application.audio.vocal_isolator import VocalIsolator
from aidub.application.audio.beat_sync import BeatSync
from aidub.application.captions.caption_style import CaptionStyle
from aidub.media.pro_audio_editor import AudioClipData


def test_auto_captioner():
    samples = np.zeros(2000, dtype=np.float32)
    samples[200:800] = 0.5
    caps = AutoCaptioner().segment(samples, 1000, words=["hello", "world"])
    assert len(caps) >= 1


def test_voice_changer():
    assert "chipmunk" in VoiceChanger.list_presets()
    p = VoiceChanger.get("deep")
    assert p["pitch"] == -5.0


def test_speed_ramp():
    clip = AudioClipData(samples=np.arange(100, dtype=np.float32), sample_rate=1000)
    out = SpeedRamp.stretch(clip, 2.0)
    assert out.samples.size == 50
    same = SpeedRamp.stretch(clip, 1.0)
    assert same.samples.size == 100


def test_vocal_isolator():
    stereo = np.array([[0.5, 0.5], [0.3, -0.3]], dtype=np.float32)
    v = VocalIsolator.isolate(stereo)
    assert v.shape == (2,)
    a = VocalIsolator.accompaniment(stereo)
    assert a.shape == (2,)


def test_beat_sync():
    samples = np.zeros(4096, dtype=np.float32)
    samples[0:256] = 1.0
    samples[2048:2304] = 1.0
    beats = BeatSync.detect_beats(samples, 1000, hop=256)
    assert isinstance(beats, list)
    assert BeatSync.snap_to_beat(1.0, [0.0, 2.0]) == 2.0 or BeatSync.snap_to_beat(1.0, [0.0, 2.0]) == 0.0


def test_caption_style():
    assert "bold_white" in CaptionStyle.list()
    s = CaptionStyle.get("neon")
    assert s["color"] == "#00FFFF"
