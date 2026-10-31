from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch

from aidub.benchmarks import __main__ as benchmark_cli
from aidub.benchmarks.models import (
    BenchmarkConfiguration,
    BenchmarkResult,
    BenchmarkSample,
    MachineFingerprint,
)
from aidub.benchmarks.runner import BenchmarkWorkload


class StubRunner:
    """Deterministic runner seam; the CLI test never measures wall-clock time."""

    def run(
        self,
        configuration: BenchmarkConfiguration,
        workload: BenchmarkWorkload,
        *,
        machine: MachineFingerprint | None = None,
    ) -> BenchmarkResult:
        del workload
        assert machine is not None
        now = datetime(2026, 8, 14, tzinfo=UTC)
        elapsed_ns = 1
        throughput = configuration.item_count * 1_000_000_000 / elapsed_ns
        return BenchmarkResult(
            run_id=f"bench_cli_{configuration.workload_name}",
            started_at=now,
            finished_at=now,
            machine=machine,
            configuration=configuration,
            samples=(
                BenchmarkSample(
                    repetition=1,
                    elapsed_ns=elapsed_ns,
                    completed_items=configuration.item_count,
                    throughput_items_per_second=throughput,
                ),
            ),
            median_ms=elapsed_ns / 1_000_000,
            p95_ms=elapsed_ns / 1_000_000,
            throughput_items_per_second=throughput,
        )


def test_module_main_writes_a_suite_report_without_a_console_entry_point(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(benchmark_cli, "BenchmarkRunner", StubRunner)
    output = tmp_path / "benchmark-report.json"

    exit_code = benchmark_cli.main(
        [
            "--workload",
            "all",
            "--rational-items",
            "2",
            "--dag-items",
            "3",
            "--warmups",
            "0",
            "--repetitions",
            "1",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["passed"] is True
    assert [result["configuration"]["workload_name"] for result in payload["results"]] == [
        "rational_time_operations",
        "job_dag_construction_traversal",
    ]
