from __future__ import annotations

import hashlib

import pytest

from aidub.contracts.jobs import JobDescriptor
from aidub.orchestration.graph import JobGraph


def job(name: str, dependencies: tuple[str, ...] = ()) -> JobDescriptor:
    return JobDescriptor(
        job_id=name,
        idempotency_key=hashlib.sha256(name.encode()).hexdigest(),
        project_id="project-1",
        job_type=name,
        dependencies=dependencies,
    )


def test_topological_order_and_ready_jobs() -> None:
    graph = JobGraph(
        [
            job("source"),
            job("asr", ("source",)),
            job("diarization", ("source",)),
            job("translation", ("asr", "diarization")),
        ]
    )
    order = graph.topological_order()
    assert order.index("source") < order.index("asr")
    assert order.index("asr") < order.index("translation")
    assert [item.job_id for item in graph.ready_jobs(completed=set())] == ["source"]
    assert {item.job_id for item in graph.ready_jobs(completed={"source"})} == {
        "asr",
        "diarization",
    }


def test_missing_dependency_rejected() -> None:
    with pytest.raises(ValueError, match="missing dependencies"):
        JobGraph([job("asr", ("source",))])


def test_cycle_rejected() -> None:
    first = job("one", ("two",))
    second = job("two", ("one",))
    with pytest.raises(ValueError, match="cycle"):
        JobGraph([first, second])


def test_descendants() -> None:
    graph = JobGraph(
        [
            job("translation"),
            job("voice", ("translation",)),
            job("timing", ("voice",)),
            job("mix", ("timing",)),
        ]
    )
    assert graph.descendants("translation") == {"voice", "timing", "mix"}
