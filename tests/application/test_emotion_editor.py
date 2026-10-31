"""
Unit tests for EmotionEditorService and EmotionTransferService.
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.application.emotion.emotion_editor import EmotionEditorService
from aidub.application.emotion.emotion_transfer import EmotionTransferService
from aidub.domain.emotion import EmotionSpec, VocalizationMarkerType
from aidub.media.pro_audio_editor import AudioClipData


def test_emotion_editor_presets_and_ssml() -> None:
    service = EmotionEditorService()

    presets = service.list_preset_names()
    assert "Neutral" in presets
    assert "Heroic Defiance" in presets

    # Apply Heroic Defiance preset at 120% intensity
    spec = service.apply_preset("Heroic Defiance", intensity=1.2)
    assert spec.intensity == 1.2
    assert spec.arousal > 0.5
    assert spec.dominance > 0.5

    # Calculate acoustic params
    params = service.calculate_acoustic_parameters(spec)
    assert params["pitch_scale"] > 1.0  # Heroic projection raises pitch slightly
    assert params["rate_scale"] > 1.0

    # Add vocalization marker
    service.add_vocalization_marker(
        spec,
        marker_type=VocalizationMarkerType.GASP,
        timestamp_s=1.2,
        duration_s=0.25,
    )

    # Generate SSML
    ssml = service.generate_ssml("আমি কখনোই হার মানবো না!", spec)
    assert "<speak" in ssml
    assert '<prosody pitch="' in ssml
    assert '<break time="250ms"/>' in ssml
    assert "আমি কখনোই হার মানবো না!" in ssml


def test_emotion_transfer_features_and_match_score() -> None:
    transfer_service = EmotionTransferService()

    sr = 48000
    # Simulate an intense, loud vocal burst
    t = np.linspace(0, 1.0, sr)
    samples_intense = (0.8 * np.sin(2 * np.pi * 300 * t) * (1.0 + 0.5 * np.sin(2 * np.pi * 5 * t))).astype(np.float32)
    clip_intense = AudioClipData(samples=samples_intense, sample_rate=sr)

    feats = transfer_service.extract_emotion_features(clip_intense)
    assert "estimated_arousal" in feats
    assert feats["estimated_arousal"] > 0.2

    # Derived emotion spec
    intent = transfer_service.transfer_emotion_intent(clip_intense, base_category="Heroic")
    assert intent.intensity >= 0.5

    # Compare identical clips -> match score should be high (>= 0.95)
    match_score = transfer_service.evaluate_emotion_match_score(clip_intense, clip_intense)
    assert match_score >= 0.95

    # Compare against flat silence
    clip_silence = AudioClipData(samples=np.zeros(sr, dtype=np.float32), sample_rate=sr)
    match_silence = transfer_service.evaluate_emotion_match_score(clip_intense, clip_silence)
    assert match_silence < match_score
