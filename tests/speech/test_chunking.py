from __future__ import annotations

import pytest
from pydantic import ValidationError

from aidub.speech import ChunkingPolicy, ChunkPlanningError, DeterministicChunkPlanner

from .helpers import SAMPLE_RATE, audio_range


def test_hour_scale_plan_is_exact_and_bounded_in_integer_samples() -> None:
    two_hours = 2 * 60 * 60 * SAMPLE_RATE
    source = audio_range(7 * SAMPLE_RATE, two_hours)
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=30 * SAMPLE_RATE,
        min_chunk_samples=15 * SAMPLE_RATE,
        overlap_samples=SAMPLE_RATE,
    )

    plan = DeterministicChunkPlanner().plan(source, policy)

    assert plan.chunks[0].audio_range.start == source.start
    assert plan.chunks[-1].audio_range.end_exclusive == source.end_exclusive
    assert (
        sum(chunk.audio_range.sample_count for chunk in plan.chunks)
        - (len(plan.chunks) - 1) * policy.overlap_samples
        == two_hours
    )
    assert all(
        policy.min_chunk_samples <= chunk.audio_range.sample_count <= policy.max_chunk_samples
        for chunk in plan.chunks
    )
    for left, right in zip(plan.chunks, plan.chunks[1:], strict=False):
        assert (
            left.audio_range.end_exclusive.sample_index - right.audio_range.start.sample_index
            == policy.overlap_samples
        )


def test_planner_balances_small_tail_instead_of_emitting_undersized_chunk() -> None:
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=100,
        min_chunk_samples=20,
        overlap_samples=10,
    )

    plan = DeterministicChunkPlanner().plan(audio_range(0, 101), policy)

    assert [chunk.audio_range.sample_count for chunk in plan.chunks] == [56, 55]
    assert [chunk.audio_range.start.sample_index for chunk in plan.chunks] == [0, 46]


def test_single_short_source_is_allowed_below_minimum() -> None:
    policy = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=100,
        min_chunk_samples=50,
        overlap_samples=10,
    )

    plan = DeterministicChunkPlanner().plan(audio_range(500, 20), policy)

    assert len(plan.chunks) == 1
    assert plan.chunks[0].audio_range == audio_range(500, 20)


def test_planner_rejects_incompatible_bounds_clock_and_empty_range() -> None:
    with pytest.raises(ValidationError):
        ChunkingPolicy(
            sample_rate=SAMPLE_RATE,
            max_chunk_samples=100,
            min_chunk_samples=50,
            overlap_samples=50,
        )

    impossible = ChunkingPolicy(
        sample_rate=SAMPLE_RATE,
        max_chunk_samples=100,
        min_chunk_samples=80,
        overlap_samples=10,
    )
    with pytest.raises(ChunkPlanningError):
        DeterministicChunkPlanner().plan(audio_range(0, 101), impossible)
    with pytest.raises(ChunkPlanningError):
        DeterministicChunkPlanner().plan(
            audio_range(0, 100, sample_rate=48_000),
            impossible,
        )
    with pytest.raises(ChunkPlanningError):
        DeterministicChunkPlanner().plan(audio_range(0, 0), impossible)
