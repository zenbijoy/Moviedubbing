from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from aidub.benchmarks.models import (
    BenchmarkConfiguration,
    BenchmarkReport,
    MachineFingerprint,
    PerformanceThresholds,
)
from aidub.benchmarks.runner import (
    BenchmarkExecutionError,
    BenchmarkRunner,
    nearest_rank_percentile,
)


class SequenceClock:
    def __init__(self, values: list[int]) -> None:
        self._values = iter(values)

    def __call__(self) -> int:
        return next(self._values)


class SequenceNow:
    def __init__(self, values: list[datetime]) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def machine(*, processor: str = "Test CPU") -> MachineFingerprint:
    return MachineFingerprint(
        system="TestOS",
        release="1",
        machine="x86_64",
        processor=processor,
        pointer_bits=64,
        python_implementation="CPython",
        python_version="3.12.10",
        logical_cpu_count=8,
    )


def configuration(
    *,
    item_count: int = 10,
    warmups: int = 2,
    repetitions: int = 5,
    thresholds: PerformanceThresholds | None = None,
) -> BenchmarkConfiguration:
    return BenchmarkConfiguration(
        workload_name="synthetic_exact_workload",
        item_count=item_count,
        warmups=warmups,
        repetitions=repetitions,
        thresholds=thresholds
        or PerformanceThresholds(
            max_median_ms=3.0,
            max_p95_ms=5.0,
            min_throughput_items_per_second=100.0,
        ),
    )


def test_runner_uses_injected_clock_and_computes_median_nearest_rank_p95() -> None:
    calls: list[int] = []

    def workload(item_count: int) -> int:
        calls.append(item_count)
        return item_count

    start = datetime(2026, 8, 14, tzinfo=UTC)
    clock = SequenceClock(
        [
            0,
            1_000_000,
            10_000_000,
            15_000_000,
            20_000_000,
            22_000_000,
            30_000_000,
            34_000_000,
            40_000_000,
            43_000_000,
        ]
    )
    runner = BenchmarkRunner(
        clock=clock,
        now=SequenceNow([start, start + timedelta(seconds=1)]),
        run_id_factory=lambda: "bench_test_run",
    )

    result = runner.run(configuration(), workload, machine=machine())

    assert calls == [10] * 7  # two untimed warmups plus five measured repetitions
    assert result.median_ms == 3.0
    assert result.p95_ms == 5.0
    assert result.throughput_items_per_second == pytest.approx(50 * 1e9 / 15_000_000)
    assert result.passed
    assert result.threshold_failures == ()
    assert [sample.elapsed_ns for sample in result.samples] == [
        1_000_000,
        5_000_000,
        2_000_000,
        4_000_000,
        3_000_000,
    ]


def test_runner_reports_every_failed_gate_without_wallclock_assertions() -> None:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    runner = BenchmarkRunner(
        clock=SequenceClock([0, 4_000_000, 10_000_000, 16_000_000, 20_000_000, 25_000_000]),
        now=SequenceNow([start, start]),
        run_id_factory=lambda: "bench_failed_gates",
    )
    thresholds = PerformanceThresholds(
        max_median_ms=3.0,
        max_p95_ms=5.0,
        min_throughput_items_per_second=2_100.0,
    )

    result = runner.run(
        configuration(warmups=0, repetitions=3, thresholds=thresholds),
        lambda count: count,
        machine=machine(),
    )

    assert not result.passed
    assert {failure.metric for failure in result.threshold_failures} == {
        "median_ms",
        "p95_ms",
        "throughput_items_per_second",
    }


def test_runner_rejects_bad_work_accounting_and_non_monotonic_clock() -> None:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    bad_count_runner = BenchmarkRunner(
        clock=SequenceClock([0, 1]),
        now=SequenceNow([start]),
    )
    with pytest.raises(BenchmarkExecutionError, match="expected 10"):
        bad_count_runner.run(
            configuration(warmups=0, repetitions=1),
            lambda count: count - 1,
            machine=machine(),
        )

    stopped_clock_runner = BenchmarkRunner(
        clock=SequenceClock([10, 10]),
        now=SequenceNow([start]),
    )
    with pytest.raises(BenchmarkExecutionError, match="did not advance"):
        stopped_clock_runner.run(
            configuration(warmups=0, repetitions=1),
            lambda count: count,
            machine=machine(),
        )


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [(0.01, 1), (0.50, 3), (0.95, 5), (1.0, 5)],
)
def test_nearest_rank_percentile(percentile: float, expected: int) -> None:
    assert nearest_rank_percentile((5, 1, 4, 2, 3), percentile) == expected


def test_result_and_report_json_include_raw_samples_machine_and_gate_state() -> None:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    fingerprint = machine()
    result = BenchmarkRunner(
        clock=SequenceClock([0, 2_000_000]),
        now=SequenceNow([start, start]),
        run_id_factory=lambda: "bench_json_contract",
    ).run(
        configuration(warmups=0, repetitions=1),
        lambda count: count,
        machine=fingerprint,
    )
    report = BenchmarkReport(generated_at=start, machine=fingerprint, results=(result,))

    payload = json.loads(report.to_json())

    assert payload["schema_version"] == 1
    assert payload["passed"] is True
    assert payload["machine"]["fingerprint_sha256"] == fingerprint.fingerprint_sha256
    assert payload["results"][0]["samples"][0]["elapsed_ns"] == 2_000_000
    assert payload["results"][0]["configuration"]["warmups"] == 0


def test_report_rejects_results_from_a_different_machine() -> None:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    result = BenchmarkRunner(
        clock=SequenceClock([0, 1]),
        now=SequenceNow([start, start]),
        run_id_factory=lambda: "bench_machine_a",
    ).run(
        configuration(warmups=0, repetitions=1),
        lambda count: count,
        machine=machine(processor="CPU A"),
    )

    with pytest.raises(ValueError, match="machine fingerprint"):
        BenchmarkReport(
            generated_at=start,
            machine=machine(processor="CPU B"),
            results=(result,),
        )


def test_result_rejects_statistics_that_do_not_match_raw_samples() -> None:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    result = BenchmarkRunner(
        clock=SequenceClock([0, 1_000_000]),
        now=SequenceNow([start, start]),
        run_id_factory=lambda: "bench_consistency",
    ).run(
        configuration(warmups=0, repetitions=1),
        lambda count: count,
        machine=machine(),
    )
    with pytest.raises(ValueError, match="does not match raw"):
        replace(result, median_ms=2.0)
