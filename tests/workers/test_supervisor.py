from __future__ import annotations

import hashlib
import json
import time

import pytest

from aidub.contracts.jobs import ErrorCategory, JobDescriptor
from aidub.workers.supervisor import LocalWorkerSupervisor, WorkerCrashedError


def make_job(job_id: str, job_type: str, **parameters: object) -> JobDescriptor:
    return JobDescriptor(
        job_id=job_id,
        idempotency_key=hashlib.sha256(job_id.encode()).hexdigest(),
        project_id="project-1",
        job_type=job_type,
        parameters=parameters,
    )


def test_worker_completes_typed_job() -> None:
    with LocalWorkerSupervisor() as worker:
        worker.submit(make_job("job-echo", "system.echo", greeting="নমস্কার"))
        result = worker.wait()
    assert result.succeeded
    assert json.loads(str(result.metrics["echo_json"])) == {"greeting": "নমস্কার"}


def test_worker_cancels_at_safe_checkpoint() -> None:
    with LocalWorkerSupervisor() as worker:
        worker.submit(make_job("job-wait", "system.wait", duration_ms=2_000))
        time.sleep(0.1)
        worker.cancel("job-wait")
        result = worker.wait()
    assert not result.succeeded
    assert result.error is not None
    assert result.error.category is ErrorCategory.CANCELLED


def test_worker_crash_is_contained_and_restartable() -> None:
    worker = LocalWorkerSupervisor()
    try:
        worker.start()
        worker.submit(make_job("job-crash", "system.crash_test"))
        with pytest.raises(WorkerCrashedError):
            worker.wait(timeout_seconds=5)
        worker.restart()
        worker.submit(make_job("job-health", "system.health"))
        assert worker.wait().succeeded
    finally:
        worker.terminate()
