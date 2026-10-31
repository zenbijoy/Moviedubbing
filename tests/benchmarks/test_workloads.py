from __future__ import annotations

import pytest

from aidub.benchmarks.workloads import (
    JOB_DAG_WORKLOAD,
    RATIONAL_TIME_WORKLOAD,
    build_job_dag,
    job_dag_configuration,
    job_dag_construction_traversal,
    rational_time_configuration,
    rational_time_operations,
)


def test_rational_time_workload_completes_configured_exact_operations() -> None:
    assert rational_time_operations(25) == 25
    with pytest.raises(ValueError, match="positive"):
        rational_time_operations(0)


def test_job_dag_workload_builds_and_traverses_every_configured_node() -> None:
    graph = build_job_dag(31)

    assert len(graph.jobs) == 31
    assert graph.topological_order()[0] == "bench-job-00000000"
    assert len(graph.descendants("bench-job-00000000")) == 30
    assert job_dag_construction_traversal(31) == 31
    with pytest.raises(ValueError, match="positive"):
        build_job_dag(0)


def test_default_workload_configurations_publish_explicit_provisional_gates() -> None:
    rational = rational_time_configuration()
    dag = job_dag_configuration()

    assert rational.workload_name == RATIONAL_TIME_WORKLOAD
    assert rational.item_count == 100_000
    assert rational.thresholds.provisional
    assert rational.thresholds.max_median_ms is not None
    assert rational.thresholds.max_p95_ms is not None
    assert rational.thresholds.min_throughput_items_per_second is not None

    assert dag.workload_name == JOB_DAG_WORKLOAD
    assert dag.item_count == 10_000
    assert dag.thresholds.provisional
    assert dag.thresholds.max_median_ms is not None
    assert dag.thresholds.max_p95_ms is not None
    assert dag.thresholds.min_throughput_items_per_second is not None


def test_configuration_counts_are_caller_configurable() -> None:
    rational = rational_time_configuration(item_count=7, warmups=0, repetitions=2)
    dag = job_dag_configuration(item_count=9, warmups=3, repetitions=4)

    assert (rational.item_count, rational.warmups, rational.repetitions) == (7, 0, 2)
    assert (dag.item_count, dag.warmups, dag.repetitions) == (9, 3, 4)
