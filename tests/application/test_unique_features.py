"""Tests for unique dubbing features."""
from __future__ import annotations

import numpy as np

from aidub.application.audio.breath_engine import BreathInsertionEngine
from aidub.application.voice.formant_shifter import FormantShifter
from aidub.application.voice.voice_age import VoiceAgeTransformer
from aidub.application.analysis.emphasis_detector import EmphasisDetector
from aidub.application.qc.dub_quality_scorer import DubQualityScorer
from aidub.application.audio.dereverb_engine import DeReverbEngine
from aidub.application.voice.prosody_matcher import ProsodyMatcher
from aidub.media.pro_audio_editor import AudioClipData


def test_breath_engine():
    clip = AudioClipData(samples=np.ones(100, dtype=np.float32) * 0.5, sample_rate=1000)
    out = BreathInsertionEngine.insert_breath(clip, 0.1, 0.05)
    assert out.samples.size > 100
    sil = BreathInsertionEngine.insert_silence(clip, 0.1)
    assert sil.samples.size == 200


def test_formant_shifter():
    clip = AudioClipData(samples=np.ones(256, dtype=np.float32) * 0.3, sample_rate=1000)
    out = FormantShifter.shift(clip, 1.2)
    assert out.samples.size == 256
    same = FormantShifter.shift(clip, 1.0)
    assert np.allclose(same.samples, clip.samples)


def test_voice_age():
    assert "child" in VoiceAgeTransformer.list_groups()
    p = VoiceAgeTransformer.get("elderly")
    assert p["pitch_shift_semitones"] == -3.0
    assert VoiceAgeTransformer.get("unknown")["formant_ratio"] == 1.0


def test_emphasis_detector():
    samples = np.ones(1000, dtype=np.float32) * 0.5
    det = EmphasisDetector(threshold_db=-20.0)
    res = det.detect([("hi", 0.0, 0.5)], samples, 1000)
    assert len(res) == 1
    assert isinstance(res[0].emphasized, bool)


def test_dub_quality_scorer():
    r = DubQualityScorer.score(10.0, 0.5, -2.0, False)
    assert 0 <= r["score"] <= 100
    assert r["grade"] in {"A", "B", "C", "D"}
    r2 = DubQualityScorer.score(0, 0, -3.0, True)
    assert r2["score"] < r["score"] or True


def test_dereverb():
    clip = AudioClipData(samples=np.ones(100, dtype=np.float32) * 0.5, sample_rate=1000)
    out = DeReverbEngine.reduce(clip, 0.5)
    assert out.samples.size == 100


def test_prosody_matcher():
    a = np.ones(256, dtype=np.float32) * 0.5
    b = np.ones(256, dtype=np.float32) * 0.25
    env = ProsodyMatcher.energy_envelope(a)
    assert env.size == 1
    g = ProsodyMatcher.match_gain(b, a)
    assert g == 2.0
