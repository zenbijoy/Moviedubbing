from __future__ import annotations

from typing import ClassVar

import pytest

from aidub.speech import (
    CallbackRecognitionRuntime,
    ChunkingPolicy,
    LongFormTranscriber,
    RecognitionCancelledError,
    RecognitionChunkResult,
    RecognitionPhase,
    RecognitionProgress,
    RecognitionProvenance,
    RecognizedSegment,
    RecognizedWord,
    SpeechEngineIdentity,
    SpeechRecognitionRequest,
    SpeechRecognizer,
)
from aidub.speech.runtime import RecognitionRuntime

from .helpers import ENGINE, SAMPLE_RATE, audio_range, request_for


class FakeMultilingualRecognizer:
    TEXT: ClassVar[dict[str, str]] = {
        "en": "Welcome",
        "bn-BD": "স্বাগতম",
        "hi-IN": "स्वागत",
    }

    def __init__(self) -> None:
        self.requests: list[SpeechRecognitionRequest] = []

    @property
    def identity(self) -> SpeechEngineIdentity:
        return ENGINE

    def recognize(
        self,
        request: SpeechRecognitionRequest,
        *,
        runtime: RecognitionRuntime,
    ) -> RecognitionChunkResult:
        runtime.checkpoint()
        self.requests.append(request)
        provenance = RecognitionProvenance.from_request(request, self.identity)
        start = request.audio_range.start.sample_index + 1
        word = RecognizedWord(
            word_id=f"word:{request.chunk_index}",
            text=self.TEXT[request.language],
            audio_range=audio_range(start, 5, sample_rate=request.audio_range.sample_rate),
            confidence=0.98,
            provenance=provenance,
        )
        segment = RecognizedSegment(
            segment_id=f"segment:{request.chunk_index}",
            text=word.text,
            audio_range=word.audio_range,
            confidence=word.confidence,
            words=(word,),
            provenance=provenance,
        )
        return RecognitionChunkResult(provenance=provenance, segments=(segment,))


@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "Welcome"), ("bn-BD", "স্বাগতম"), ("hi-IN", "स्वागत")],
)
def test_injected_fake_recognizer_round_trip(language: str, expected: str) -> None:
    fake = FakeMultilingualRecognizer()
    assert isinstance(fake, SpeechRecognizer)
    request = request_for(full_range=audio_range(0, 160), language=language)
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=200,
        min_chunk_samples=50,
        overlap_samples=10,
    )
    progress: list[RecognitionProgress] = []
    runtime = CallbackRecognitionRuntime(
        is_cancelled=lambda: False,
        on_progress=progress.append,
    )

    merged = LongFormTranscriber(fake).transcribe(request, policy, runtime=runtime)

    assert [word.text for word in merged.words] == [expected]
    assert fake.requests[0].language == language
    assert progress[0].phase is RecognitionPhase.PLANNING
    assert progress[-1].phase is RecognitionPhase.COMPLETE
    assert progress[-1].completed_samples == request.audio_range.sample_count


def test_long_form_pipeline_uses_all_planned_chunks_and_monotonic_progress() -> None:
    fake = FakeMultilingualRecognizer()
    request = request_for(full_range=audio_range(1_000, 180))
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=100,
        min_chunk_samples=50,
        overlap_samples=20,
    )
    progress: list[RecognitionProgress] = []

    merged = LongFormTranscriber(fake).transcribe(
        request,
        policy,
        runtime=CallbackRecognitionRuntime(
            is_cancelled=lambda: False,
            on_progress=progress.append,
        ),
    )

    assert [item.chunk_index for item in fake.requests] == [0, 1]
    assert all(item.chunk_count == 2 for item in fake.requests)
    assert [word.word_id for word in merged.words] == ["word:0", "word:1"]
    completion_values = [
        item.completed_samples for item in progress if item.phase is RecognitionPhase.RECOGNIZING
    ]
    assert completion_values == sorted(completion_values)
    assert completion_values[-1] == request.audio_range.sample_count


def test_callback_runtime_cancels_before_model_invocation() -> None:
    fake = FakeMultilingualRecognizer()
    request = request_for(full_range=audio_range(0, 160))
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=200,
        min_chunk_samples=50,
        overlap_samples=10,
    )

    with pytest.raises(RecognitionCancelledError):
        LongFormTranscriber(fake).transcribe(
            request,
            policy,
            runtime=CallbackRecognitionRuntime(
                is_cancelled=lambda: True,
                on_progress=lambda _progress: None,
            ),
        )

    assert fake.requests == []
