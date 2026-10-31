"""Tests for voice cloning + emotion control features."""
from __future__ import annotations

import math

from aidub.application.voice.voice_clone_profile import VoiceCloneProfile, VoiceCloneRegistry
from aidub.application.voice.speaker_similarity import SpeakerSimilarity
from aidub.application.voice.consistency_checker import VoiceConsistencyChecker
from aidub.application.emotion.intensity_controller import EmotionIntensityController
from aidub.application.emotion.blend_engine import EmotionBlendEngine
from aidub.application.emotion.transfer_engine import EmotionTransferEngine
from aidub.application.emotion.emotion_curve import EmotionCurve, EmotionCurvePoint
from aidub.application.emotion.bangla_presets import BanglaEmotionPresets
from aidub.application.voice.pro_emotion_engine import PADVector, MicroInflections


def test_voice_clone_profile():
    p = VoiceCloneProfile("p1", "Actor A", embedding=[1.0, 2.0])
    assert p.has_embedding()
    reg = VoiceCloneRegistry()
    reg.add(p)
    assert reg.get("p1") is not None
    assert "p1" in reg.list_ids()
    reg.remove("p1")
    assert reg.get("p1") is None


def test_speaker_similarity():
    a = [1.0, 0.0]; b = [1.0, 0.0]
    assert abs(SpeakerSimilarity.cosine(a, b) - 1.0) < 1e-6
    assert SpeakerSimilarity.consistent(a, b, 0.9) is True
    assert SpeakerSimilarity.cosine([], b) == 0.0


def test_consistency_checker():
    embs = [[1.0, 0.0], [0.99, 0.01]]
    res = VoiceConsistencyChecker(0.9).check(embs)
    assert res["consistent"] is True
    res2 = VoiceConsistencyChecker(0.99).check([[1.0, 0.0], [0.0, 1.0]])
    assert res2["consistent"] is False


def test_intensity_controller():
    pad = PADVector(0.5, 0.5, 0.5)
    out = EmotionIntensityController.scale_pad(pad, 2.0)
    assert out.valence == 1.0
    micro = MicroInflections(tremble_pct=50.0)
    m2 = EmotionIntensityController.scale_micro(micro, 0.5)
    assert m2.tremble_pct == 25.0


def test_blend_engine():
    p1 = PADVector(1.0, 0.0, 0.0); p2 = PADVector(-1.0, 0.0, 0.0)
    blended = EmotionBlendEngine.blend_pads([p1, p2], [0.5, 0.5])
    assert abs(blended.valence) < 1e-6


def test_transfer_engine():
    pad = PADVector(0.5, 0.6, 0.4)
    micro = MicroInflections(throat_tension_pct=30.0)
    res = EmotionTransferEngine.transfer(pad, micro)
    assert "pitch_shift_semitones" in res
    assert "rate_multiplier" in res


def test_emotion_curve():
    curve = EmotionCurve([EmotionCurvePoint(0.0, 0.5), EmotionCurvePoint(1.0, 1.5)])
    assert abs(curve.evaluate(0.5) - 1.0) < 1e-6
    arr = curve.to_array(4)
    assert arr.size == 4


def test_bangla_presets():
    assert "romantic" in BanglaEmotionPresets.list()
    pad, micro = BanglaEmotionPresets.get("tragic")
    assert pad.valence < 0
