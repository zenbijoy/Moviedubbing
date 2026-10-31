"""Typed factories shared by speech-recognition unit tests."""

from __future__ import annotations

from collections.abc import Sequence

from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.speech import (
    RecognitionChunkResult,
    RecognitionProvenance,
    RecognizedSegment,
    RecognizedWord,
    SpeechEngineIdentity,
    SpeechRecognitionRequest,
)

SAMPLE_RATE = 16_000
SOURCE_HASH = "a" * 64
OTHER_SOURCE_HASH = "b" * 64
WEIGHTS_HASH = "c" * 64
ENGINE = SpeechEngineIdentity(
    engine_id="local-asr",
    engine_version="1.2.3",
    model_id="multilingual-asr",
    model_version="3.0.1",
    model_weights_sha256=WEIGHTS_HASH,
)

TokenSpec = tuple[str, str, int, int, float]


def audio_range(start: int, count: int, *, sample_rate: int = SAMPLE_RATE) -> AudioSampleRange:
    return AudioSampleRange(
        start=AudioSamplePosition(sample_index=start, sample_rate=sample_rate),
        sample_count=count,
    )


def request_for(
    *,
    full_range: AudioSampleRange,
    chunk_range: AudioSampleRange | None = None,
    chunk_index: int = 0,
    chunk_count: int = 1,
    language: str = "en",
    source_hash: str = SOURCE_HASH,
    media_asset_id: str = "med_source",
) -> SpeechRecognitionRequest:
    return SpeechRecognitionRequest(
        request_id="asr:test-request",
        project_id="prj_test",
        media_asset_id=media_asset_id,
        source_audio_sha256=source_hash,
        language=language,
        full_audio_range=full_range,
        audio_range=chunk_range if chunk_range is not None else full_range,
        channel_index=0,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
    )


def result_for(
    request: SpeechRecognitionRequest,
    tokens: Sequence[TokenSpec],
    *,
    engine: SpeechEngineIdentity = ENGINE,
) -> RecognitionChunkResult:
    provenance = RecognitionProvenance.from_request(request, engine)
    words = tuple(
        RecognizedWord(
            word_id=word_id,
            text=text,
            audio_range=audio_range(start, count, sample_rate=request.audio_range.sample_rate),
            confidence=confidence,
            provenance=provenance,
        )
        for word_id, text, start, count, confidence in tokens
    )
    if not words:
        return RecognitionChunkResult(provenance=provenance)
    segment_start = words[0].audio_range.start.sample_index
    segment_end = words[-1].audio_range.end_exclusive.sample_index
    segment = RecognizedSegment(
        segment_id=f"segment:{request.chunk_index}",
        text=" ".join(word.text for word in words),
        audio_range=audio_range(
            segment_start,
            segment_end - segment_start,
            sample_rate=request.audio_range.sample_rate,
        ),
        confidence=sum(word.confidence for word in words) / len(words),
        words=words,
        provenance=provenance,
    )
    return RecognitionChunkResult(provenance=provenance, segments=(segment,))


__all__ = [
    "ENGINE",
    "OTHER_SOURCE_HASH",
    "SAMPLE_RATE",
    "SOURCE_HASH",
    "WEIGHTS_HASH",
    "TokenSpec",
    "audio_range",
    "request_for",
    "result_for",
]
