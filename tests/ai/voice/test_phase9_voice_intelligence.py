"""
Unit tests for Phase 9 — Authorized Character Voice Intelligence, Zero-Shot Voice Conditioning & Multimodal Performance Transfer:
  - Model-Agnostic Speaker Embedding & Similarity
  - Diarization-based Reference Voice Mining & Quality Ranking
  - Tripartite Voice Synthesis Abstraction & Continuous VAD Emotion Fusion
  - Time-Normalized Prosody Extraction & Transfer
  - Consent Guard Authorization & Revocation Invalidation
  - Post-Synthesis Speaker Verification & Take Quality Evaluation
  - OpenVoice & Chatterbox Voice Engine Adapters
  - Voice Cloning Studio Presentation Controller
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aidub.ai.voice.acoustic_prosody import AcousticProsodyExtractor
from aidub.ai.voice.character_cloning_engine import (
    CharacterDetectionEngine,
    CharacterVoiceCloningUnavailableError,
    CharacterVoiceToneCloningEngine,
)
from aidub.ai.voice.emotion_engine import (
    AcousticEmotionDetector,
    EmotionAnalysisUnavailableError,
    EmotionEngine,
)
from aidub.ai.voice.performance_tracker import MultimodalPerformanceTracker
from aidub.ai.voice.reference_miner import DiarizationSegmentInput, ReferenceVoiceMiner
from aidub.ai.voice.speaker_verification import SpeakerVerificationEngine
from aidub.application.voice.consent_guard import PermissionDeniedError, VoiceConsentGuard
from aidub.application.voice.profile_builder import CharacterVoiceProfileBuilder
from aidub.application.voice.take_evaluator import TakeQcStatus, VoiceTakeEvaluator
from aidub.contracts.base import Identifier
from aidub.domain.performance import (
    LinguisticContent,
    PerformanceIntent,
    SynthesisRequest,
    VoiceIdentity,
)
from aidub.domain.speaker_embedding import SpeakerEmbedding
from aidub.domain.voice_profile import ReferenceQualityTier
from aidub.ui.voice.controller import VoiceCloningStudioController


def test_opaque_speaker_embedding_similarity() -> None:
    # Test 192-d ECAPA vector
    v1 = [1.0] + [0.0] * 191
    v2 = [0.98] + [0.01] * 191
    emb1 = SpeakerEmbedding(
        embedding_id=Identifier("e1"),
        model_id="ecapa_192",
        dimension=192,
        vector=v1,
        source_artifact_id=Identifier("a1"),
    )
    emb2 = SpeakerEmbedding(
        embedding_id=Identifier("e2"),
        model_id="ecapa_192",
        dimension=192,
        vector=v2,
        source_artifact_id=Identifier("a2"),
    )

    sim = emb1.compute_cosine_similarity(emb2)
    assert sim > 0.80

    # Test dimension mismatch error
    emb_256 = SpeakerEmbedding(
        embedding_id=Identifier("e3"),
        model_id="pyannote_256",
        dimension=256,
        vector=[0.1] * 256,
        source_artifact_id=Identifier("a3"),
    )
    with pytest.raises(ValueError, match="mismatching dimensions"):
        emb1.compute_cosine_similarity(emb_256)


def test_reference_voice_miner_and_quality_engine() -> None:
    miner = ReferenceVoiceMiner()
    segments = [
        DiarizationSegmentInput(
            "seg_01",
            "HERO_01",
            start_ms=0,
            duration_ms=12000,
            audio_file_path="stem1.wav",
            snr_db=28.0,
        ),
        DiarizationSegmentInput(
            "seg_02",
            "HERO_01",
            start_ms=13000,
            duration_ms=2000,
            audio_file_path="stem2.wav",
            snr_db=10.0,
        ),  # Too short
        DiarizationSegmentInput(
            "seg_03", "OTHER_01", start_ms=20000, duration_ms=15000, audio_file_path="stem3.wav"
        ),
    ]

    refs = miner.mine_speaker_references("HERO_01", segments)
    assert len(refs) == 1
    assert refs[0].sample_id == "seg_01"
    assert refs[0].quality_report.tier in (
        ReferenceQualityTier.EXCELLENT_REFERENCE,
        ReferenceQualityTier.GOOD_REFERENCE,
    )


def test_tripartite_synthesis_request() -> None:
    identity = VoiceIdentity(character_id=Identifier("HERO_01"), profile_id=Identifier("prof_01"))
    intent = PerformanceIntent(
        primary_emotion="anger", emotion_intensity=0.8, valence=-0.6, arousal=0.8
    )
    linguistic = LinguisticContent(text="Hold your fire!", target_language_code="bn-BD")

    req = SynthesisRequest(
        request_id=Identifier("req_001"),
        voice_identity=identity,
        performance_intent=intent,
        linguistic_content=linguistic,
    )
    assert req.voice_identity.character_id == "HERO_01"
    assert req.performance_intent.primary_emotion == "anger"


def test_character_detection_uses_real_anonymous_speaker_ids() -> None:
    detected = CharacterDetectionEngine().detect_movie_characters(
        [{"speaker": "SPEAKER_00"}, {"speaker": "SPEAKER_01"}]
    )
    assert [character.canonical_name for character in detected] == [
        "Speaker SPEAKER_00",
        "Speaker SPEAKER_01",
    ]
    assert all(character.recommended_base_voice is None for character in detected)

    with pytest.raises(CharacterVoiceCloningUnavailableError, match="no consent-aware RVC"):
        CharacterVoiceToneCloningEngine().clone_character_utterance(
            detected[0], "বাংla dialogue", "preview.wav"
        )


def test_emotion_analysis_never_substitutes_neutral_defaults(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        AcousticEmotionDetector().analyze_audio_features(tmp_path / "missing.wav")

    class UnavailableContextDetector:
        def detect_emotion(self, **_kwargs: Any) -> Any:
            raise EmotionAnalysisUnavailableError("provider unavailable")

    engine = EmotionEngine()
    engine.context_detector = UnavailableContextDetector()  # type: ignore[assignment]
    with pytest.raises(EmotionAnalysisUnavailableError, match="provider unavailable"):
        engine.detect_emotion("utt_01", "hello")


def test_multimodal_performance_tracker_and_prosody() -> None:
    tracker = MultimodalPerformanceTracker()
    state = tracker.analyze_utterance_performance("u1", "Stop right there!", acoustic_f0_hz=280.0)
    assert state.source_observation.dominant_category == "anger"
    assert state.source_observation.to_ui_label() == "Anger / Frustration"

    extractor = AcousticProsodyExtractor()
    profile = extractor.extract_prosody_profile("u1", duration_s=3.5)
    assert len(profile.f0_normalized_contour) == 100
    assert len(profile.energy_envelope) == 100


def test_consent_guard_authorization_and_revocation() -> None:
    guard = VoiceConsentGuard()
    builder = CharacterVoiceProfileBuilder()

    profile_unauthorized = builder.build_character_profile(
        "HERO_01", "Hero Actor", [], consent_authorized=False
    )
    with pytest.raises(PermissionDeniedError, match="Voice cloning prohibited"):
        guard.ensure_synthesis_authorized(profile_unauthorized)

    profile_authorized = builder.build_character_profile(
        "HERO_01", "Hero Actor", [], consent_authorized=True
    )
    guard.ensure_synthesis_authorized(profile_authorized)  # Passes without error

    revoked = guard.revoke_voice_consent(profile_authorized)
    assert revoked.consent_authorized is False


def test_take_evaluator_and_speaker_verification() -> None:
    evaluator = VoiceTakeEvaluator()
    report_pass = evaluator.evaluate_take(
        "t1",
        "u1",
        speaker_similarity=0.94,
        naturalness_score=0.92,
        emotion_match_score=0.91,
        timing_fit_score=0.95,
    )
    assert report_pass.qc_status == TakeQcStatus.PASS

    report_fail = evaluator.evaluate_take(
        "t2",
        "u1",
        speaker_similarity=0.40,
        naturalness_score=0.40,
        emotion_match_score=0.40,
        timing_fit_score=0.40,
    )
    assert report_fail.qc_status == TakeQcStatus.BLOCKING_FAILURE

    verifier = SpeakerVerificationEngine()
    emb1 = SpeakerEmbedding(
        embedding_id=Identifier("e1"),
        model_id="ecapa_192",
        dimension=192,
        vector=[1.0] * 192,
        source_artifact_id=Identifier("a1"),
    )
    emb2 = SpeakerEmbedding(
        embedding_id=Identifier("e2"),
        model_id="ecapa_192",
        dimension=192,
        vector=[0.95] * 192,
        source_artifact_id=Identifier("a2"),
    )
    assert verifier.verify_speaker_similarity(emb1, emb2) > 0.90


def test_voice_cloning_studio_controller() -> None:
    from aidub.ui.voice.controller import (
        ConsentAuthorizationUnavailableError,
        VoicePreviewUnavailableError,
    )

    ctrl = VoiceCloningStudioController()
    profile = ctrl.load_character_profile("HERO_01", "Hero Actor", [])
    assert profile.consent_authorized is False

    # Blocked preview without consent
    with pytest.raises(PermissionDeniedError):
        ctrl.request_synthesis_preview("u100")

    # A boolean toggle cannot replace an actual consent record or synthesized preview.
    with pytest.raises(ConsentAuthorizationUnavailableError, match="real consent record"):
        ctrl.authorize_consent()

    ctrl.active_profile = profile.model_copy(update={"consent_authorized": True})
    with pytest.raises(VoicePreviewUnavailableError, match="no voice-conversion preview backend"):
        ctrl.request_synthesis_preview("u100")

    # Clearing the local authorization state remains available.
    assert ctrl.clear_local_authorization() is True
    with pytest.raises(PermissionDeniedError):
        ctrl.request_synthesis_preview("u100")
