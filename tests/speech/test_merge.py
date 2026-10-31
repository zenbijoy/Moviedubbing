from __future__ import annotations

import pytest

from aidub.speech import (
    AudioChunkPlan,
    ChunkingPolicy,
    DeterministicChunkMerger,
    DeterministicChunkPlanner,
    MergeCompatibilityError,
    MergeWarningCode,
    SpeechEngineIdentity,
)

from .helpers import (
    ENGINE,
    OTHER_SOURCE_HASH,
    SAMPLE_RATE,
    WEIGHTS_HASH,
    audio_range,
    request_for,
    result_for,
)


def _two_chunk_plan() -> AudioChunkPlan:
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=100,
        min_chunk_samples=50,
        overlap_samples=20,
    )
    return DeterministicChunkPlanner().plan(audio_range(0, 180), policy)


def test_overlap_duplicate_keeps_higher_confidence_without_shifting_time() -> None:
    plan = _two_chunk_plan()
    left_request = request_for(
        full_range=plan.source_range,
        chunk_range=plan.chunks[0].audio_range,
        chunk_index=0,
        chunk_count=2,
    )
    right_request = request_for(
        full_range=plan.source_range,
        chunk_range=plan.chunks[1].audio_range,
        chunk_index=1,
        chunk_count=2,
    )
    left = result_for(
        left_request,
        [
            ("word:hello", "Hello", 10, 10, 0.99),
            ("word:left-world", "World", 85, 10, 0.80),
        ],
    )
    right = result_for(
        right_request,
        [
            ("word:right-world", "world", 86, 10, 0.95),
            ("word:again", "again", 120, 10, 0.90),
        ],
    )

    merged = DeterministicChunkMerger().merge(plan, (right, left))

    assert [word.word_id for word in merged.words] == [
        "word:hello",
        "word:right-world",
        "word:again",
    ]
    retained = merged.words[1]
    assert retained.audio_range.start.sample_index == 86
    assert retained.audio_range.sample_count == 10
    assert len(merged.warnings) == 1
    assert merged.warnings[0].code is MergeWarningCode.OVERLAP_DUPLICATE_REMOVED
    assert merged.warnings[0].kept_word_id == "word:right-world"
    assert merged.warnings[0].dropped_word_id == "word:left-world"


def test_equal_confidence_tie_prefers_lower_chunk_index() -> None:
    plan = _two_chunk_plan()
    requests = tuple(
        request_for(
            full_range=plan.source_range,
            chunk_range=chunk.audio_range,
            chunk_index=chunk.index,
            chunk_count=2,
        )
        for chunk in plan.chunks
    )
    left = result_for(requests[0], [("word:left", "এক", 85, 10, 0.9)])
    right = result_for(requests[1], [("word:right", "এক", 86, 10, 0.9)])

    merged = DeterministicChunkMerger().merge(plan, (left, right))

    assert [word.word_id for word in merged.words] == ["word:left"]
    assert merged.words[0].audio_range.start.sample_index == 85
    assert merged.warnings[0].kept_word_id == "word:left"


def test_different_overlapping_text_emits_conflict_warning_and_never_moves_winner() -> None:
    plan = _two_chunk_plan()
    requests = tuple(
        request_for(
            full_range=plan.source_range,
            chunk_range=chunk.audio_range,
            chunk_index=chunk.index,
            chunk_count=2,
            language="hi-IN",
        )
        for chunk in plan.chunks
    )
    left = result_for(requests[0], [("word:left", "एक", 84, 12, 0.7)])
    right = result_for(requests[1], [("word:right", "दो", 86, 8, 0.9)])

    merged = DeterministicChunkMerger().merge(plan, (left, right))

    assert [word.word_id for word in merged.words] == ["word:right"]
    assert merged.words[0].audio_range == audio_range(86, 8)
    assert merged.warnings[0].code is MergeWarningCode.OVERLAPPING_TIMING_CONFLICT
    assert "no timestamp was shifted" in merged.warnings[0].message


@pytest.mark.parametrize("mismatch", ["language", "source", "media", "engine", "clock"])
def test_merger_rejects_incompatible_provenance(mismatch: str) -> None:
    plan = _two_chunk_plan()
    left_request = request_for(
        full_range=plan.source_range,
        chunk_range=plan.chunks[0].audio_range,
        chunk_index=0,
        chunk_count=2,
    )
    right_full = plan.source_range
    right_chunk = plan.chunks[1].audio_range
    language = "bn-BD" if mismatch == "language" else "en"
    source_hash = OTHER_SOURCE_HASH if mismatch == "source" else "a" * 64
    media_asset_id = "med_other" if mismatch == "media" else "med_source"
    if mismatch == "clock":
        right_full = audio_range(0, 180, sample_rate=48_000)
        right_chunk = audio_range(80, 100, sample_rate=48_000)
    right_request = request_for(
        full_range=right_full,
        chunk_range=right_chunk,
        chunk_index=1,
        chunk_count=2,
        language=language,
        source_hash=source_hash,
        media_asset_id=media_asset_id,
    )
    engine = ENGINE
    if mismatch == "engine":
        engine = SpeechEngineIdentity(
            engine_id=ENGINE.engine_id,
            engine_version=ENGINE.engine_version,
            model_id=ENGINE.model_id,
            model_version=ENGINE.model_version,
            model_weights_sha256=WEIGHTS_HASH.replace("c", "d"),
        )
    left = result_for(left_request, [("word:left", "left", 10, 10, 0.9)])
    right = result_for(
        right_request,
        [("word:right", "right", right_chunk.start.sample_index + 10, 10, 0.9)],
        engine=engine,
    )

    with pytest.raises(MergeCompatibilityError):
        DeterministicChunkMerger().merge(plan, (left, right))
