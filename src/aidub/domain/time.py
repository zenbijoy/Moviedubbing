"""Exact video-time and audio-sample primitives.

No type in this module stores floating-point seconds. Ranges are half-open and canonical edit
ranges reject negative positions. A caller must name a rounding policy whenever an exact conversion
is not guaranteed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from functools import total_ordering
from math import gcd, lcm
from typing import Self

from pydantic import Field, model_validator

from .base import DomainModel


class RoundingMode(StrEnum):
    """Supported deterministic policies for lossy time-base conversion."""

    FLOOR = "floor"
    CEIL = "ceil"
    TOWARD_ZERO = "toward_zero"
    NEAREST_EVEN = "nearest_even"


def _round_fraction(value: Fraction, mode: RoundingMode) -> int:
    numerator = value.numerator
    denominator = value.denominator

    if mode is RoundingMode.FLOOR:
        return numerator // denominator
    if mode is RoundingMode.CEIL:
        return -((-numerator) // denominator)
    if mode is RoundingMode.TOWARD_ZERO:
        quotient = abs(numerator) // denominator
        return quotient if numerator >= 0 else -quotient

    sign = 1 if numerator >= 0 else -1
    quotient, remainder = divmod(abs(numerator), denominator)
    comparison = remainder * 2 - denominator
    if comparison > 0 or (comparison == 0 and quotient % 2 == 1):
        quotient += 1
    return sign * quotient


@total_ordering
class RationalRate(DomainModel):
    """A positive exact number of ticks or frames per second."""

    numerator: int = Field(gt=0, le=2_147_483_647)
    denominator: int = Field(default=1, gt=0, le=2_147_483_647)

    @model_validator(mode="after")
    def _reduce(self) -> Self:
        divisor = gcd(self.numerator, self.denominator)
        if divisor != 1:
            object.__setattr__(self, "numerator", self.numerator // divisor)
            object.__setattr__(self, "denominator", self.denominator // divisor)
        return self

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RationalRate):
            return NotImplemented
        return self.fraction < other.fraction

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"

    @classmethod
    def from_fps(
        cls,
        fps: float | int | str | RationalRate | tuple[int, int],
    ) -> RationalRate:
        """Create exact RationalRate from integer, float, string, or tuple.

        Accurately maps standard cinematic and broadcast frame rates:
        - 23.976 / 23.98 fps -> 24000/1001 (NTSC Cinema)
        - 24.0 fps -> 24/1 (Cinema Standard)
        - 25.0 fps -> 25/1 (PAL)
        - 29.97 fps -> 30000/1001 (NTSC Broadcast)
        - 30.0 fps -> 30/1
        - 50.0 fps -> 50/1 (PAL High Frame Rate)
        - 59.94 fps -> 60000/1001 (NTSC High Frame Rate)
        - 60.0 fps -> 60/1
        """
        if isinstance(fps, RationalRate):
            return fps
        if isinstance(fps, tuple) and len(fps) == 2:
            return cls(numerator=int(fps[0]), denominator=int(fps[1]))
        if isinstance(fps, str):
            fps_str = fps.strip()
            if "/" in fps_str:
                parts = fps_str.split("/", 1)
                return cls(numerator=int(parts[0]), denominator=int(parts[1]))
            try:
                fps = float(fps_str)
            except ValueError as exc:
                raise ValueError(f"Cannot parse rate from string {fps!r}") from exc

        fps_float = float(fps)
        if fps_float <= 0:
            raise ValueError(f"Framerate must be positive, got {fps_float}")

        # Integer rates (24, 25, 30, 48, 50, 60, 120, etc.)
        if round(fps_float) == fps_float:
            return cls(numerator=int(round(fps_float)), denominator=1)

        # Standard NTSC / Cinema rates within common floating point tolerances
        if abs(fps_float - 23.976023976) < 0.01 or abs(fps_float - 23.976) < 0.005 or abs(fps_float - 23.98) < 0.005:
            return cls(numerator=24_000, denominator=1_001)
        if abs(fps_float - 29.97002997) < 0.01 or abs(fps_float - 29.97) < 0.005:
            return cls(numerator=30_000, denominator=1_001)
        if abs(fps_float - 59.94005994) < 0.01 or abs(fps_float - 59.94) < 0.005:
            return cls(numerator=60_000, denominator=1_001)

        frac = Fraction(fps_float).limit_denominator(1001)
        return cls(numerator=frac.numerator, denominator=frac.denominator)


@dataclass(frozen=True, slots=True)
class TickRescaler:
    """Precomputed exact clock transform for editor and media hot loops.

    Domain entities remain validated ``RationalTime`` objects at boundaries. Bulk
    timeline, waveform, and sample-placement code can reuse this transform over
    integer tick arrays without allocating a Pydantic object per element.
    """

    source_rate: RationalRate
    target_rate: RationalRate
    _numerator: int = field(init=False, repr=False)
    _denominator: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        numerator = self.source_rate.denominator * self.target_rate.numerator
        denominator = self.source_rate.numerator * self.target_rate.denominator
        divisor = gcd(numerator, denominator)
        object.__setattr__(self, "_numerator", numerator // divisor)
        object.__setattr__(self, "_denominator", denominator // divisor)

    def rescale_ticks(
        self,
        ticks: int,
        *,
        rounding: RoundingMode | None = None,
    ) -> int:
        """Convert integer ticks, rejecting a lossy conversion without policy."""

        target_numerator = ticks * self._numerator
        quotient, remainder = divmod(target_numerator, self._denominator)
        if remainder == 0:
            return quotient
        if rounding is None:
            raise ValueError("tick value is not exactly representable; provide a rounding policy")
        return _round_fraction(Fraction(target_numerator, self._denominator), rounding)


@total_ordering
class RationalTime(DomainModel):
    """An integer tick count at an exact rate.

    ``seconds == ticks / rate``. Signed values are supported because decoded source PTS can be
    negative. Persisted edit ranges apply their own non-negative invariant.
    """

    ticks: int
    rate: RationalRate

    @property
    def seconds(self) -> Fraction:
        return Fraction(self.ticks * self.rate.denominator, self.rate.numerator)

    def rescaled_to(
        self,
        rate: RationalRate,
        *,
        rounding: RoundingMode | None = None,
    ) -> RationalTime:
        """Represent the same instant at ``rate``.

        Conversion is exact by default. Supplying a rounding mode is mandatory when the new time
        base cannot represent the value exactly, preventing accidental frame/sample drift.
        """

        try:
            ticks = TickRescaler(self.rate, rate).rescale_ticks(self.ticks, rounding=rounding)
        except ValueError as exc:
            raise ValueError(
                f"{self} is not exactly representable at {rate}; provide a rounding policy"
            ) from exc
        return RationalTime(ticks=ticks, rate=rate)

    @staticmethod
    def common_rate(left: RationalRate, right: RationalRate) -> RationalRate:
        """Return a rate at which ticks from both input rates are integral."""

        return RationalRate(numerator=lcm(left.numerator, right.numerator), denominator=1)

    def _coerce_pair(self, other: RationalTime) -> tuple[RationalTime, RationalTime]:
        if self.rate == other.rate:
            return self, other
        rate = self.common_rate(self.rate, other.rate)
        return self.rescaled_to(rate), other.rescaled_to(rate)

    def __add__(self, other: object) -> RationalTime:
        if not isinstance(other, RationalTime):
            return NotImplemented
        left, right = self._coerce_pair(other)
        return RationalTime(ticks=left.ticks + right.ticks, rate=left.rate)

    def __sub__(self, other: object) -> RationalTime:
        if not isinstance(other, RationalTime):
            return NotImplemented
        left, right = self._coerce_pair(other)
        return RationalTime(ticks=left.ticks - right.ticks, rate=left.rate)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RationalTime):
            return NotImplemented
        return (
            self.ticks * self.rate.denominator * other.rate.numerator
            < other.ticks * other.rate.denominator * self.rate.numerator
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RationalTime):
            return NotImplemented
        return (
            self.ticks * self.rate.denominator * other.rate.numerator
            == other.ticks * other.rate.denominator * self.rate.numerator
        )

    def __hash__(self) -> int:
        return hash(self.seconds)

    def __str__(self) -> str:
        return f"{self.ticks}@{self.rate}"

    @classmethod
    def from_seconds(
        cls,
        seconds: float | int | Fraction,
        rate: RationalRate,
        *,
        rounding: RoundingMode = RoundingMode.NEAREST_EVEN,
    ) -> RationalTime:
        """Construct exact RationalTime from seconds and target rate using explicit rounding."""
        frac_s = Fraction(seconds) if not isinstance(seconds, Fraction) else seconds
        tick_fraction = frac_s * Fraction(rate.numerator, rate.denominator)
        ticks = _round_fraction(tick_fraction, rounding)
        return cls(ticks=ticks, rate=rate)

    def to_seconds_float(self) -> float:
        """Floating point seconds for ephemeral UI or telemetry displays ONLY (ADR-001)."""
        return float(self.seconds)

    def to_audio_sample_position(
        self,
        sample_rate: int = 48_000,
        *,
        rounding: RoundingMode = RoundingMode.NEAREST_EVEN,
    ) -> AudioSamplePosition:
        """Directly map editorial RationalTime to sample-accurate AudioSamplePosition."""
        return AudioSamplePosition.from_rational_time(
            self,
            sample_rate=sample_rate,
            rounding=rounding,
        )


class TimeRange(DomainModel):
    """A non-negative, half-open edit range ``[start, end)``."""

    start: RationalTime
    duration: RationalTime

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.start.rate != self.duration.rate:
            raise ValueError("range start and duration must use the same rate")
        if self.start.ticks < 0:
            raise ValueError("range start cannot be negative")
        if self.duration.ticks < 0:
            raise ValueError("range duration cannot be negative")
        return self

    @classmethod
    def from_start_end(cls, start: RationalTime, end: RationalTime) -> Self:
        if start.rate != end.rate:
            raise ValueError("range start and end must use the same rate")
        if end.ticks < start.ticks:
            raise ValueError("range end cannot precede start")
        return cls(
            start=start,
            duration=RationalTime(ticks=end.ticks - start.ticks, rate=start.rate),
        )

    @property
    def rate(self) -> RationalRate:
        return self.start.rate

    @property
    def end_exclusive(self) -> RationalTime:
        return RationalTime(ticks=self.start.ticks + self.duration.ticks, rate=self.rate)

    @property
    def is_empty(self) -> bool:
        return self.duration.ticks == 0

    def rescaled_to(
        self,
        rate: RationalRate,
        *,
        rounding: RoundingMode | None = None,
    ) -> TimeRange:
        """Rescale endpoints, then derive duration to avoid cumulative rounding error."""

        start = self.start.rescaled_to(rate, rounding=rounding)
        end = self.end_exclusive.rescaled_to(rate, rounding=rounding)
        return TimeRange.from_start_end(start, end)

    def contains(self, value: RationalTime) -> bool:
        return not self.is_empty and self.start <= value < self.end_exclusive

    def contains_range(self, other: TimeRange) -> bool:
        return self.start <= other.start and other.end_exclusive <= self.end_exclusive

    def overlaps(self, other: TimeRange) -> bool:
        if self.is_empty or other.is_empty:
            return False
        return self.start < other.end_exclusive and other.start < self.end_exclusive

    def intersection(self, other: TimeRange) -> TimeRange | None:
        if not self.overlaps(other):
            return None
        rate = RationalTime.common_rate(self.rate, other.rate)
        left = self.rescaled_to(rate)
        right = other.rescaled_to(rate)
        start = max(left.start, right.start)
        end = min(left.end_exclusive, right.end_exclusive)
        return TimeRange.from_start_end(start, end)

    def split_at(self, position: RationalTime) -> tuple[TimeRange, TimeRange]:
        if not self.start < position < self.end_exclusive:
            raise ValueError("split position must be strictly inside the range")
        exact = position.rescaled_to(self.rate)
        return (
            TimeRange.from_start_end(self.start, exact),
            TimeRange.from_start_end(exact, self.end_exclusive),
        )


@total_ordering
class AudioSamplePosition(DomainModel):
    """A non-negative position in an audio stream's integer sample clock."""

    sample_index: int = Field(ge=0)
    sample_rate: int = Field(gt=0, le=768_000)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AudioSamplePosition):
            return NotImplemented
        self._require_same_rate(other)
        return self.sample_index < other.sample_index

    def _require_same_rate(self, other: AudioSamplePosition) -> None:
        if self.sample_rate != other.sample_rate:
            raise ValueError("audio positions use different sample rates")

    def __sub__(self, other: object) -> int:
        if not isinstance(other, AudioSamplePosition):
            return NotImplemented
        self._require_same_rate(other)
        return self.sample_index - other.sample_index

    def to_rational_time(self) -> RationalTime:
        return RationalTime(
            ticks=self.sample_index,
            rate=RationalRate(numerator=self.sample_rate),
        )

    @classmethod
    def from_rational_time(
        cls,
        value: RationalTime,
        *,
        sample_rate: int,
        rounding: RoundingMode | None = None,
    ) -> AudioSamplePosition:
        converted = value.rescaled_to(
            RationalRate(numerator=sample_rate),
            rounding=rounding,
        )
        if converted.ticks < 0:
            raise ValueError("audio sample position cannot be negative")
        return cls(sample_index=converted.ticks, sample_rate=sample_rate)


class AudioSampleRange(DomainModel):
    """A non-negative, half-open audio range measured only in integer samples."""

    start: AudioSamplePosition
    sample_count: int = Field(ge=0)

    @property
    def sample_rate(self) -> int:
        return self.start.sample_rate

    @property
    def end_exclusive(self) -> AudioSamplePosition:
        return AudioSamplePosition(
            sample_index=self.start.sample_index + self.sample_count,
            sample_rate=self.sample_rate,
        )

    @property
    def is_empty(self) -> bool:
        return self.sample_count == 0

    def contains(self, position: AudioSamplePosition) -> bool:
        self.start._require_same_rate(position)
        return not self.is_empty and self.start <= position < self.end_exclusive

    def overlaps(self, other: AudioSampleRange) -> bool:
        self.start._require_same_rate(other.start)
        if self.is_empty or other.is_empty:
            return False
        return self.start < other.end_exclusive and other.start < self.end_exclusive

    def intersection(self, other: AudioSampleRange) -> AudioSampleRange | None:
        if not self.overlaps(other):
            return None
        start_index = max(self.start.sample_index, other.start.sample_index)
        end_index = min(self.end_exclusive.sample_index, other.end_exclusive.sample_index)
        return AudioSampleRange(
            start=AudioSamplePosition(sample_index=start_index, sample_rate=self.sample_rate),
            sample_count=end_index - start_index,
        )

    def to_time_range(self) -> TimeRange:
        rate = RationalRate(numerator=self.sample_rate)
        return TimeRange(
            start=RationalTime(ticks=self.start.sample_index, rate=rate),
            duration=RationalTime(ticks=self.sample_count, rate=rate),
        )


__all__ = [
    "AudioSamplePosition",
    "AudioSampleRange",
    "RationalRate",
    "RationalTime",
    "RoundingMode",
    "TickRescaler",
    "TimeRange",
]
