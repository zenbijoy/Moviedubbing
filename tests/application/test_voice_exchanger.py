"""
Unit tests for VoiceExchanger application service.
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.application.voice.voice_exchanger import VoiceExchanger
from aidub.media.pro_audio_editor import AudioClipData


def test_voice_exchanger_catalog_and_swap() -> None:
    exchanger = VoiceExchanger()

    all_voices = exchanger.list_curated_voices()
    assert len(all_voices) >= 3

    # Language filter
    bn_voices = exchanger.list_curated_voices("bn")
    assert any("Pradeep" in v.display_name for v in bn_voices)
    assert all(v.language.startswith("bn") for v in bn_voices)

    # Valid voice swap
    swapped_cues = exchanger.swap_voice(["cue_1", "cue_2"], "bn-BD-PradeepNeural")
    assert swapped_cues == ["cue_1", "cue_2"]

    # Unknown voice fails with ValueError
    with pytest.raises(ValueError):
        exchanger.swap_voice(["cue_1"], "non_existent_voice_999")


def test_voice_exchanger_timbre_morph() -> None:
    exchanger = VoiceExchanger()

    sr = 48000
    clip_a = AudioClipData(samples=np.full(sr, 0.4, dtype=np.float32), sample_rate=sr)
    clip_b = AudioClipData(samples=np.full(sr, 0.8, dtype=np.float32), sample_rate=sr)

    # 50% morph ratio
    morphed = exchanger.morph_timbres(clip_a, clip_b, morph_ratio=0.5)
    assert morphed.samples.size == sr
    # Result must be a blend between clip_a and clip_b
    avg_sample = float(np.mean(morphed.samples))
    assert 0.4 < avg_sample < 0.8


def test_voice_exchanger_pitch_and_formant() -> None:
    exchanger = VoiceExchanger()

    sr = 48000
    samples = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)
    clip = AudioClipData(samples=samples, sample_rate=sr)

    # Apply +2 semitones pitch and +100 cents formant
    shifted = exchanger.apply_pitch_and_formant(clip, pitch_semitones=2.0, formant_cents=100.0)
    assert shifted.samples.size == clip.samples.size
    assert shifted.duration_s == pytest.approx(clip.duration_s, abs=0.01)
