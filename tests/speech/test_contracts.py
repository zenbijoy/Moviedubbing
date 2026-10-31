from __future__ import annotations

import pytest
from pydantic import ValidationError

from aidub.speech import (
    RecognitionPhase,
    RecognitionProgress,
    RecognitionProvenance,
    RecognizedSegment,
    RecognizedWord,
    SpeechEngineIdentity,
    SpeechRecognitionRequest,
)

from .helpers import ENGINE, SOURCE_HASH, audio_range, request_for, result_for


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Accuracy matters."),
        ("bn-BD", "নির্ভুলতা গুরুত্বপূর্ণ।"),
        ("hi-IN", "सटीकता महत्वपूर्ण है।"),
    ],
)
def test_multilingual_contract_round_trip_preserves_unicode(language: str, text: str) -> None:
    request = request_for(full_range=audio_range(0, 1_600), language=language)
    result = result_for(request, [("word:1", text, 100, 400, 0.97)])

    restored = type(result).model_validate_json(result.model_dump_json())

    assert restored == result
    assert restored.words[0].text == text
    assert restored.words[0].provenance.language == language


def test_engine_identity_requires_semver_weight_hash_and_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SpeechEngineIdentity(
            engine_id="local-asr",
            engine_version="latest",
            model_id="model",
            model_version="1.0.0",
            model_weights_sha256="not-a-hash",
        )

    payload = ENGINE.model_dump()
    payload["untracked_runtime"] = "cuda"
    with pytest.raises(ValidationError):
        SpeechEngineIdentity.model_validate(payload)


def test_request_rejects_coercion_and_ranges_outside_full_source() -> None:
    full_range = audio_range(100, 100)
    with pytest.raises(ValidationError):
        SpeechRecognitionRequest(
            request_id="asr:test",
            project_id="prj_test",
            media_asset_id="med_test",
            source_audio_sha256=SOURCE_HASH,
            language="en",
            full_audio_range=full_range,
            audio_range=audio_range(90, 50),
        )

    valid = request_for(full_range=full_range)
    payload = valid.model_dump()
    payload["channel_index"] = "0"
    with pytest.raises(ValidationError):
        SpeechRecognitionRequest.model_validate(payload)


def test_word_and_segment_require_contained_monotonic_exact_sample_ranges() -> None:
    request = request_for(full_range=audio_range(0, 1_000))
    provenance = RecognitionProvenance.from_request(request, ENGINE)
    outside = RecognizedWord.model_construct(
        word_id="word:outside",
        text="outside",
        audio_range=audio_range(900, 200),
        confidence=0.8,
        provenance=provenance,
    )
    with pytest.raises(ValidationError):
        RecognizedWord.model_validate(outside.model_dump())

    later = RecognizedWord(
        word_id="word:later",
        text="later",
        audio_range=audio_range(200, 100),
        confidence=0.8,
        provenance=provenance,
    )
    earlier = RecognizedWord(
        word_id="word:earlier",
        text="earlier",
        audio_range=audio_range(100, 100),
        confidence=0.8,
        provenance=provenance,
    )
    with pytest.raises(ValidationError):
        RecognizedSegment(
            segment_id="segment:bad-order",
            text="later earlier",
            audio_range=audio_range(100, 200),
            confidence=0.8,
            words=(later, earlier),
            provenance=provenance,
        )


def test_progress_rejects_impossible_completion() -> None:
    with pytest.raises(ValidationError):
        RecognitionProgress(
            request_id="asr:test",
            phase=RecognitionPhase.RECOGNIZING,
            completed_samples=101,
            total_samples=100,
            chunk_count=1,
        )
