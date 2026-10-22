"""
Unit tests for Advanced Emotion Detection, Cinematic LLM Instruction,
Closed-Loop Verification, Regeneration, Continual Learning, and Manual Director Control.
"""

from __future__ import annotations

import math
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path

from aidub.ai.voice.advanced_emotion import (
    CinematicLlmInstructor,
    ContinualEmotionLearner,
    DirectorEmotionController,
    EmotionVerificationReport,
    EmotionVerifierAndRegenerator,
    FastAcousticProsodyAnalyzer,
    HighPrecisionAcousticFeatures,
)
from aidub.ai.voice.emotion_engine import EmotionEngine
from aidub.domain.emotion import EmotionObservation


@pytest.fixture
def test_audio_files(tmp_path: Path) -> dict[str, Path]:
    """Generates synthetic audio files for testing acoustic prosody detection."""
    sr = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # 1. Normal conversational voice proxy (F0 ~ 180 Hz, moderate energy)
    tone_normal = 0.15 * np.sin(2 * np.pi * 180.0 * t)
    normal_path = tmp_path / "normal.wav"
    sf.write(normal_path, tone_normal.astype(np.float32), sr)

    # 2. Angry / Shouting voice proxy (F0 ~ 280 Hz, loud, high dynamic range)
    tone_loud = 0.70 * np.sin(2 * np.pi * 280.0 * t) + 0.20 * np.sin(2 * np.pi * 560.0 * t)
    loud_path = tmp_path / "shout.wav"
    sf.write(loud_path, tone_loud.astype(np.float32), sr)

    # 3. Whisper voice proxy (High noise / high ZCR, very low energy)
    np.random.seed(42)
    whisper_data = 0.02 * np.random.randn(int(sr * duration))
    whisper_path = tmp_path / "whisper.wav"
    sf.write(whisper_path, whisper_data.astype(np.float32), sr)

    return {
        "normal": normal_path,
        "shout": loud_path,
        "whisper": whisper_path,
    }


def test_fast_acoustic_prosody_analyzer(test_audio_files: dict[str, Path]) -> None:
    analyzer = FastAcousticProsodyAnalyzer()

    # 1. Test normal
    data, sr = analyzer.read_audio_interval(test_audio_files["normal"])
    feats_normal = analyzer.extract_features(data, sr)
    assert 150.0 <= feats_normal.f0_median_hz <= 210.0
    assert not feats_normal.is_whisper
    obs_normal = analyzer.features_to_vad(feats_normal)
    assert -1.0 <= obs_normal.arousal <= 1.0

    # 2. Test shouting
    data_shout, sr_shout = analyzer.read_audio_interval(test_audio_files["shout"])
    feats_shout = analyzer.extract_features(data_shout, sr_shout)
    assert feats_shout.rms_mean > feats_normal.rms_mean
    assert feats_shout.f0_median_hz > feats_normal.f0_median_hz
    obs_shout = analyzer.features_to_vad(feats_shout)
    assert obs_shout.arousal > obs_normal.arousal

    # 3. Test whisper
    data_wh, sr_wh = analyzer.read_audio_interval(test_audio_files["whisper"])
    feats_wh = analyzer.extract_features(data_wh, sr_wh)
    assert feats_wh.zero_crossing_rate > 0.05
    obs_wh = analyzer.features_to_vad(feats_wh)
    assert obs_wh.arousal < 0.0


def test_cinematic_llm_instructor_fallback() -> None:
    instructor = CinematicLlmInstructor()
    # Test shout instruction
    res_shout = instructor.generate_instruction("STOP RIGHT THERE NOW!", character_name="Commander")
    assert res_shout.primary_emotion in {"anger", "shouting", "intense_confrontation"}
    assert res_shout.intensity >= 0.7
    assert res_shout.style_degree >= 1.0

    # Test question instruction
    res_q = instructor.generate_instruction("Where did everyone go?", character_name="Protagonist")
    assert res_q.intensity > 0.2


def test_emotion_verifier_and_auto_regeneration(tmp_path: Path) -> None:
    analyzer = FastAcousticProsodyAnalyzer()
    verifier = EmotionVerifierAndRegenerator(
        analyzer=analyzer,
        min_accuracy_threshold=0.68,
        max_regeneration_attempts=2,
    )

    out_file = tmp_path / "verified_take.wav"

    # Mock synthesis function that responds to pitch/rate changes
    def mock_synth(text: str, target_path: Path, rate: str, pitch: str) -> None:
        sr = 16000
        # Parse pitch shift to modulate frequency
        p_val = int(pitch.replace("Hz", "").replace("+", "") or 0)
        freq = max(100.0, 220.0 + p_val * 4.0)
        t = np.linspace(0, 1.0, sr, endpoint=False)
        # Add slight AM modulation to simulate vocal syllabic energy envelope
        env = 0.5 * (1.0 + np.sin(2 * np.pi * 3.0 * t))
        audio = env * 0.4 * np.sin(2 * np.pi * freq * t)
        sf.write(target_path, audio.astype(np.float32), sr)

    target_intent = EmotionObservation(
        dominant_category="anger",
        arousal=0.85,
        valence=-0.6,
        dominance=0.7,
        intensity=0.8,
    )

    report = verifier.synthesize_with_closed_loop_verification(
        text="Get out of here!",
        output_path=out_file,
        synth_fn=mock_synth,
        target_intent=target_intent,
        base_rate="+0%",
        base_pitch="+0Hz",
    )

    assert out_file.is_file()
    assert report.accuracy_score >= 0.65
    assert report.target_category == "anger"


def test_continual_emotion_learner(tmp_path: Path) -> None:
    store_file = tmp_path / "test_emotion_store.json"
    learner = ContinualEmotionLearner(memory_file_path=store_file)

    # Initial bias is 0
    pitch, rate = learner.get_learned_prosody_offset("HERO_01", "anger")
    assert pitch == 0 and rate == 0

    # Record feedback from verified takes
    learner.record_performance_feedback(
        character_id="HERO_01",
        emotion_category="anger",
        applied_pitch_hz=12,
        applied_rate_percent=10,
        verified_accuracy=0.92,
        manual_override=True,
    )

    # Should learn non-zero bias
    new_pitch, new_rate = learner.get_learned_prosody_offset("HERO_01", "anger")
    assert new_pitch > 0
    assert new_rate > 0

    # Test persistence by reloading
    learner2 = ContinualEmotionLearner(memory_file_path=store_file)
    p2, r2 = learner2.get_learned_prosody_offset("HERO_01", "anger")
    assert p2 == new_pitch
    assert r2 == new_rate


def test_director_emotion_controller(tmp_path: Path) -> None:
    store_file = tmp_path / "director_store.json"
    learner = ContinualEmotionLearner(memory_file_path=store_file)
    controller = DirectorEmotionController(learner=learner)

    # Set manual override
    controller.set_override(
        utterance_id="utt_101",
        emotion_category="shouting",
        intensity=0.95,
        pitch_offset_hz=16,
        rate_offset_percent=14,
        lock_take=True,
    )

    assert controller.is_locked("utt_101")
    override = controller.get_override("utt_101")
    assert override is not None
    assert override["emotion_category"] == "shouting"
    assert override["pitch_offset_hz"] == 16


def test_emotion_engine_synthesize_verified_line(tmp_path: Path) -> None:
    engine = EmotionEngine()
    out_file = tmp_path / "verified_engine_take.wav"

    def mock_synth(text: str, target_path: Path, rate: str, pitch: str) -> None:
        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        audio = 0.25 * np.sin(2 * np.pi * 200.0 * t)
        sf.write(target_path, audio.astype(np.float32), sr)

    # Use manual director override on this utterance
    engine.director_controller.set_override(
        utterance_id="utt_test",
        emotion_category="joy",
        intensity=0.85,
        pitch_offset_hz=10,
        rate_offset_percent=12,
    )

    detection, report = engine.synthesize_verified_line(
        text="We won the championship!",
        output_path=out_file,
        synth_fn=mock_synth,
        utterance_id="utt_test",
        character_name="Player_01",
    )

    assert detection.primary_emotion == "joy"
    assert detection.detection_source == "director_manual_override"
    assert out_file.is_file()
    assert report.target_category == "joy"
