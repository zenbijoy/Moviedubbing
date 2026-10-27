from fractions import Fraction

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from aidub.domain.time import (
    AudioSamplePosition,
    AudioSampleRange,
    RationalRate,
    RationalTime,
    RoundingMode,
    TickRescaler,
    TimeRange,
)

FPS_24 = RationalRate(numerator=24)
FPS_25 = RationalRate(numerator=25)
FPS_NTSC = RationalRate(numerator=24_000, denominator=1_001)


def rt(ticks: int, rate: RationalRate = FPS_24) -> RationalTime:
    return RationalTime(ticks=ticks, rate=rate)


def time_range(start: int, duration: int, rate: RationalRate = FPS_24) -> TimeRange:
    return TimeRange(start=rt(start, rate), duration=rt(duration, rate))


def test_rate_is_reduced_and_seconds_are_exact() -> None:
    rate = RationalRate(numerator=48_000, denominator=2_002)

    assert rate == FPS_NTSC
    assert rt(100, rate).seconds == Fraction(1001, 240)


@pytest.mark.parametrize(
    ("numerator", "denominator"),
    [(0, 1), (-1, 1), (1, 0), (1, -1), (2_147_483_648, 1)],
)
def test_rate_rejects_non_positive_or_out_of_contract_values(
    numerator: int, denominator: int
) -> None:
    with pytest.raises(ValidationError):
        RationalRate(numerator=numerator, denominator=denominator)


def test_rescale_is_exact_for_ntsc_frame_to_48khz_samples() -> None:
    sample_rate = RationalRate(numerator=48_000)

    converted = rt(1, FPS_NTSC).rescaled_to(sample_rate)

    assert converted.ticks == 2_002
    assert converted.seconds == rt(1, FPS_NTSC).seconds


def test_precomputed_tick_rescaler_matches_validated_entity_conversion() -> None:
    sample_rate = RationalRate(numerator=48_000)
    to_samples = TickRescaler(FPS_NTSC, sample_rate)
    to_frames = TickRescaler(sample_rate, FPS_NTSC)

    for frame_ticks in (-1_000_000, -1, 0, 1, 1_000_000):
        sample_ticks = to_samples.rescale_ticks(frame_ticks)
        assert sample_ticks == rt(frame_ticks, FPS_NTSC).rescaled_to(sample_rate).ticks
        assert to_frames.rescale_ticks(sample_ticks) == frame_ticks


def test_precomputed_tick_rescaler_requires_explicit_lossy_rounding() -> None:
    transform = TickRescaler(FPS_24, FPS_25)

    with pytest.raises(ValueError, match="rounding policy"):
        transform.rescale_ticks(1)
    assert transform.rescale_ticks(1, rounding=RoundingMode.FLOOR) == 1
    assert transform.rescale_ticks(1, rounding=RoundingMode.CEIL) == 2


def test_lossy_rescale_requires_an_explicit_rounding_policy() -> None:
    value = rt(1, FPS_24)

    with pytest.raises(ValueError, match="rounding policy"):
        value.rescaled_to(FPS_25)

    assert value.rescaled_to(FPS_25, rounding=RoundingMode.FLOOR).ticks == 1
    assert value.rescaled_to(FPS_25, rounding=RoundingMode.CEIL).ticks == 2


@pytest.mark.parametrize(
    ("ticks", "expected_floor", "expected_ceil", "expected_zero", "expected_even"),
    [
        (1, 1, 2, 1, 2),
        (-1, -2, -1, -1, -2),
    ],
)
def test_signed_rounding_is_deterministic(
    ticks: int,
    expected_floor: int,
    expected_ceil: int,
    expected_zero: int,
    expected_even: int,
) -> None:
    half = RationalTime(ticks=ticks, rate=RationalRate(numerator=2))
    target = RationalRate(numerator=3)

    assert half.rescaled_to(target, rounding=RoundingMode.FLOOR).ticks == expected_floor
    assert half.rescaled_to(target, rounding=RoundingMode.CEIL).ticks == expected_ceil
    assert half.rescaled_to(target, rounding=RoundingMode.TOWARD_ZERO).ticks == expected_zero
    assert half.rescaled_to(target, rounding=RoundingMode.NEAREST_EVEN).ticks == expected_even


def test_nearest_even_uses_the_even_integer_on_a_tie() -> None:
    value = RationalTime(ticks=1, rate=RationalRate(numerator=2))

    # 0.5 seconds at 5 ticks/second is exactly 2.5 ticks.
    assert (
        value.rescaled_to(RationalRate(numerator=5), rounding=RoundingMode.NEAREST_EVEN).ticks == 2
    )


def test_cross_rate_arithmetic_and_comparison_remain_exact() -> None:
    one_second_at_24 = rt(24, FPS_24)
    one_second_at_25 = rt(25, FPS_25)

    result = one_second_at_24 + one_second_at_25

    assert result.seconds == 2
    assert one_second_at_24 == one_second_at_25
    assert rt(23, FPS_24) < one_second_at_25


def test_time_range_rejects_negative_and_mixed_rate_state() -> None:
    with pytest.raises(ValidationError, match="start cannot be negative"):
        time_range(-1, 1)
    with pytest.raises(ValidationError, match="duration cannot be negative"):
        time_range(0, -1)
    with pytest.raises(ValidationError, match="same rate"):
        TimeRange(start=rt(0, FPS_24), duration=rt(1, FPS_25))


def test_ranges_are_half_open_and_adjacent_ranges_do_not_overlap() -> None:
    left = time_range(10, 5)
    right = time_range(15, 7)

    assert left.contains(rt(10))
    assert left.contains(rt(14))
    assert not left.contains(rt(15))
    assert not left.overlaps(right)
    assert left.intersection(right) is None


def test_cross_rate_intersection_chooses_an_exact_common_clock() -> None:
    left = time_range(0, 48, FPS_24)  # 0..2 seconds
    right = time_range(25, 50, FPS_25)  # 1..3 seconds

    intersection = left.intersection(right)

    assert intersection is not None
    assert intersection.start.seconds == 1
    assert intersection.duration.seconds == 1


@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    start=st.integers(min_value=0, max_value=10**9),
    duration=st.integers(min_value=2, max_value=10**7),
    offset=st.integers(min_value=1, max_value=10**7),
)
def test_split_preserves_range_for_all_interior_positions(
    start: int, duration: int, offset: int
) -> None:
    offset = 1 + (offset % (duration - 1))
    original = time_range(start, duration, FPS_NTSC)

    left, right = original.split_at(rt(start + offset, FPS_NTSC))

    assert left.start == original.start
    assert left.end_exclusive == right.start
    assert right.end_exclusive == original.end_exclusive
    assert left.duration.ticks + right.duration.ticks == original.duration.ticks


@given(
    ticks=st.integers(min_value=-(10**12), max_value=10**12),
    numerator=st.integers(min_value=1, max_value=100_000),
    denominator=st.integers(min_value=1, max_value=10_000),
)
def test_exact_rescale_round_trip_via_common_integer_rate(
    ticks: int, numerator: int, denominator: int
) -> None:
    value = RationalTime(
        ticks=ticks,
        rate=RationalRate(numerator=numerator, denominator=denominator),
    )
    common = RationalRate(numerator=value.rate.numerator)

    assert value.rescaled_to(common).rescaled_to(value.rate) == value


def test_audio_sample_range_is_exact_and_half_open() -> None:
    start = AudioSamplePosition(sample_index=48_000, sample_rate=48_000)
    audio_range = AudioSampleRange(start=start, sample_count=2_002)

    assert audio_range.to_time_range().start.seconds == 1
    assert audio_range.to_time_range().duration.seconds == Fraction(1001, 24_000)
    assert audio_range.contains(start)
    assert not audio_range.contains(audio_range.end_exclusive)


def test_audio_positions_reject_implicit_cross_rate_math() -> None:
    left = AudioSamplePosition(sample_index=1, sample_rate=44_100)
    right = AudioSamplePosition(sample_index=1, sample_rate=48_000)

    with pytest.raises(ValueError, match="different sample rates"):
        _ = left < right
    with pytest.raises(ValueError, match="different sample rates"):
        _ = left - right


def test_negative_rational_time_cannot_become_an_audio_position() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        AudioSamplePosition.from_rational_time(
            rt(-1), sample_rate=48_000, rounding=RoundingMode.FLOOR
        )
