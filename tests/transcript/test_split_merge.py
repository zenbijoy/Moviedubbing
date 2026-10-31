from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aidub.domain import RationalTime
from aidub.transcript import (
    MergePolicy,
    MergeUtterancesCommand,
    SplitUtteranceCommand,
    TranscriptCommandService,
    TranscriptInvariantViolation,
)

from .factories import RATE, audio_range, time_range, transcript, utterance, word

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
EDITOR = "editor@example.test"


def test_split_preserves_exact_boundaries_words_samples_and_old_snapshot() -> None:
    original = utterance(
        words=(
            word("আমি", 1_000, 1_350),
            word("এখানে", 1_450, 1_900),
            word("আছি", 2_100, 2_600),
        ),
        samples=audio_range(48_000, 96_000),
        revision=4,
    )
    source = transcript(original, revision=8)
    result = TranscriptCommandService().split(
        source,
        SplitUtteranceCommand(
            expected_revision=8,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            left_utterance_id="utt_line_left",
            right_utterance_id="utt_line_right",
            source_position=RationalTime(ticks=2_000, rate=RATE),
            edit_position=RationalTime(ticks=6_000, rate=RATE),
            left_text="আমি এখানে",
            right_text="আছি",
        ),
    )

    left, right = result.transcript.utterances
    assert source.utterances == (original,)
    assert left.source_range == time_range(1_000, 2_000)
    assert right.source_range == time_range(2_000, 3_000)
    assert left.edit_range == time_range(5_000, 6_000)
    assert right.edit_range == time_range(6_000, 7_000)
    assert tuple(item.text for item in left.words) == ("আমি", "এখানে")
    assert tuple(item.text for item in right.words) == ("আছি",)
    assert left.source_audio_range is not None
    assert right.source_audio_range is not None
    assert left.source_audio_range.sample_count == 48_000
    assert right.source_audio_range.start.sample_index == 96_000
    assert right.source_audio_range.sample_count == 48_000
    assert left.revision == right.revision == 5
    assert result.transcript.revision == 9
    assert result.audit.affected_utterance_ids == (
        "utt_line_001",
        "utt_line_left",
        "utt_line_right",
    )
    assert tuple(root.utterance_id for root in result.invalidation_roots) == (
        "utt_line_001",
        "utt_line_left",
        "utt_line_right",
    )


def test_split_rejects_position_inside_word_and_range_edges() -> None:
    source = transcript(utterance(words=(word("একটি", 1_500, 2_500),)))
    service = TranscriptCommandService()

    with pytest.raises(TranscriptInvariantViolation, match="crosses aligned word"):
        service.split(
            source,
            SplitUtteranceCommand(
                expected_revision=0,
                actor=EDITOR,
                occurred_at=NOW,
                utterance_id="utt_line_001",
                left_utterance_id="utt_line_left",
                right_utterance_id="utt_line_right",
                source_position=RationalTime(ticks=2_000, rate=RATE),
                edit_position=RationalTime(ticks=6_000, rate=RATE),
                left_text="এক",
                right_text="টি",
            ),
        )

    for edge in (1_000, 3_000):
        with pytest.raises(TranscriptInvariantViolation, match="strictly inside"):
            service.split(
                source,
                SplitUtteranceCommand(
                    expected_revision=0,
                    actor=EDITOR,
                    occurred_at=NOW,
                    utterance_id="utt_line_001",
                    left_utterance_id="utt_edge_left",
                    right_utterance_id="utt_edge_right",
                    source_position=RationalTime(ticks=edge, rate=RATE),
                    edit_position=RationalTime(ticks=6_000, rate=RATE),
                    left_text="বাম",
                    right_text="ডান",
                ),
            )


@settings(max_examples=35, deadline=None)
@given(
    start=st.integers(min_value=0, max_value=100_000),
    left_duration=st.integers(min_value=1, max_value=20_000),
    right_duration=st.integers(min_value=1, max_value=20_000),
)
def test_split_property_exact_half_open_partition(
    start: int,
    left_duration: int,
    right_duration: int,
) -> None:
    split = start + left_duration
    end = split + right_duration
    line = utterance(
        source_start=start,
        source_end=end,
        edit_start=start,
        edit_end=end,
        source_text="सीमा परीक्षण",
        language="hi-IN",
    )
    source = transcript(line, language="hi-IN")

    result = TranscriptCommandService().split(
        source,
        SplitUtteranceCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            left_utterance_id="utt_prop_left",
            right_utterance_id="utt_prop_right",
            source_position=RationalTime(ticks=split, rate=RATE),
            edit_position=RationalTime(ticks=split, rate=RATE),
            left_text="सीमा",
            right_text="परीक्षण",
        ),
    )

    left, right = result.transcript.utterances
    assert left.source_range.start.ticks == start
    assert left.source_range.end_exclusive == right.source_range.start
    assert right.source_range.end_exclusive.ticks == end
    assert left.source_range.duration.ticks + right.source_range.duration.ticks == end - start


def test_adjacent_merge_covers_exact_ranges_and_preserves_word_order() -> None:
    left = utterance(
        "utt_line_left",
        source_start=1_000,
        source_end=2_000,
        edit_start=5_000,
        edit_end=6_000,
        source_text="আমি এখানে",
        words=(word("আমি", 1_000, 1_300), word("এখানে", 1_400, 1_900)),
        samples=audio_range(48_000, 48_000),
        revision=2,
    )
    right = utterance(
        "utt_line_right",
        source_start=2_000,
        source_end=3_000,
        edit_start=6_000,
        edit_end=7_000,
        source_text="আছি",
        words=(word("আছি", 2_100, 2_600),),
        samples=audio_range(96_000, 48_000),
        revision=5,
    )
    source = transcript(left, right, revision=11)

    result = TranscriptCommandService().merge(
        source,
        MergeUtterancesCommand(
            expected_revision=11,
            actor=EDITOR,
            occurred_at=NOW,
            left_utterance_id="utt_line_left",
            right_utterance_id="utt_line_right",
            merged_utterance_id="utt_line_merged",
            merged_text="আমি এখানে আছি",
            policy=MergePolicy.ADJACENT_ONLY,
        ),
    )

    merged = result.transcript.utterances[0]
    assert source.utterances == (left, right)
    assert merged.source_range == time_range(1_000, 3_000)
    assert merged.edit_range == time_range(5_000, 7_000)
    assert tuple(item.text for item in merged.words) == ("আমি", "এখানে", "আছি")
    assert merged.source_audio_range is not None
    assert merged.source_audio_range.sample_count == 96_000
    assert merged.revision == 6
    assert result.audit.affected_utterance_ids == (
        "utt_line_left",
        "utt_line_right",
        "utt_line_merged",
    )


def test_overlap_policy_is_explicit_and_never_allows_a_gap() -> None:
    left = utterance(
        "utt_line_left",
        source_start=1_000,
        source_end=2_200,
        edit_start=5_000,
        edit_end=6_200,
        samples=audio_range(48_000, 57_600),
    )
    overlapping = utterance(
        "utt_line_right",
        source_start=2_000,
        source_end=3_000,
        edit_start=6_000,
        edit_end=7_000,
        samples=audio_range(96_000, 48_000),
    )
    source = transcript(left, overlapping)
    adjacent_command = MergeUtterancesCommand(
        expected_revision=0,
        actor=EDITOR,
        occurred_at=NOW,
        left_utterance_id="utt_line_left",
        right_utterance_id="utt_line_right",
        merged_utterance_id="utt_line_merged",
        merged_text="একত্র",
        policy=MergePolicy.ADJACENT_ONLY,
    )
    with pytest.raises(TranscriptInvariantViolation, match="touching"):
        TranscriptCommandService().merge(source, adjacent_command)

    overlap = TranscriptCommandService().merge(
        source,
        adjacent_command.model_copy(update={"policy": MergePolicy.ALLOW_OVERLAP}),
    )
    assert overlap.transcript.utterances[0].source_range == time_range(1_000, 3_000)

    gap_right = utterance(
        "utt_line_gap",
        source_start=2_500,
        source_end=3_000,
        edit_start=6_500,
        edit_end=7_000,
    )
    with pytest.raises(TranscriptInvariantViolation, match="gap"):
        TranscriptCommandService().merge(
            transcript(left.model_copy(update={"source_audio_range": None}), gap_right),
            MergeUtterancesCommand(
                expected_revision=0,
                actor=EDITOR,
                occurred_at=NOW,
                left_utterance_id="utt_line_left",
                right_utterance_id="utt_line_gap",
                merged_utterance_id="utt_gap_merged",
                merged_text="ফাঁক",
                policy=MergePolicy.ALLOW_OVERLAP,
            ),
        )


@settings(max_examples=30, deadline=None)
@given(
    start=st.integers(min_value=0, max_value=100_000),
    left_duration=st.integers(min_value=1, max_value=10_000),
    right_duration=st.integers(min_value=1, max_value=10_000),
)
def test_adjacent_merge_property_exact_cover(
    start: int,
    left_duration: int,
    right_duration: int,
) -> None:
    boundary = start + left_duration
    end = boundary + right_duration
    left = utterance(
        "utt_prop_left",
        source_start=start,
        source_end=boundary,
        edit_start=start,
        edit_end=boundary,
    )
    right = utterance(
        "utt_prop_right",
        source_start=boundary,
        source_end=end,
        edit_start=boundary,
        edit_end=end,
    )

    result = TranscriptCommandService().merge(
        transcript(left, right),
        MergeUtterancesCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            left_utterance_id="utt_prop_left",
            right_utterance_id="utt_prop_right",
            merged_utterance_id="utt_prop_merged",
            merged_text="সম্পূর্ণ সীমা",
            policy=MergePolicy.ADJACENT_ONLY,
        ),
    )

    merged = result.transcript.utterances[0]
    assert merged.source_range.start.ticks == start
    assert merged.source_range.end_exclusive.ticks == end
    assert merged.source_range.duration.ticks == left_duration + right_duration
