"""Tests for pro emotion engine new features: blend_presets and to_ssml."""
from __future__ import annotations

from aidub.application.voice.pro_emotion_engine import (
    MicroInflections,
    PADVector,
    ProEmotionDirectorEngine,
)


def test_blend_presets_midpoint():
    pad, micro, label = ProEmotionDirectorEngine.blend_presets("Neutral", "Explosive Rage", 0.5)
    assert isinstance(pad, PADVector)
    assert isinstance(micro, MicroInflections)
    assert "Blend" in label
    # midpoint should be between the two source valences
    n_pad, _, _ = ProEmotionDirectorEngine.get_preset("Neutral")
    f_pad, _, _ = ProEmotionDirectorEngine.get_preset("Explosive Rage")
    expected_v = (n_pad.valence + f_pad.valence) / 2.0
    assert abs(pad.valence - expected_v) < 1e-9


def test_blend_presets_clamps_ratio():
    a, _, _ = ProEmotionDirectorEngine.blend_presets("Neutral", "Explosive Rage", -1.0)
    b, _, _ = ProEmotionDirectorEngine.blend_presets("Neutral", "Explosive Rage", 2.0)
    n, _, _ = ProEmotionDirectorEngine.get_preset("Neutral")
    f, _, _ = ProEmotionDirectorEngine.get_preset("Explosive Rage")
    assert abs(a.valence - n.valence) < 1e-9
    assert abs(b.valence - f.valence) < 1e-9


def test_to_ssml_contains_text_and_prosody():
    pad = PADVector(valence=0.5, arousal=0.8, dominance=0.3)
    micro = MicroInflections(breathiness_pct=20.0)
    ssml = ProEmotionDirectorEngine.to_ssml("Hello world", pad, micro, 1.2)
    assert ssml.startswith("<speak")
    assert ssml.endswith("</speak>")
    assert "Hello world" in ssml
    assert "<prosody" in ssml
    assert "rate=" in ssml


def test_to_ssml_escapes_xml():
    pad = PADVector()
    ssml = ProEmotionDirectorEngine.to_ssml("A & B < C", pad)
    assert "A &amp; B &lt; C" in ssml
