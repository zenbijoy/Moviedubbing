from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aidub.domain.artifact import ArtifactType
from aidub.domain.base import InvalidStateTransition
from aidub.domain.job import (
    Job,
    JobError,
    JobErrorCategory,
    JobProgress,
    JobStatus,
    ResourceRequest,
    RetryPolicy,
    can_transition_job_status,
)

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)


def job(**updates: object) -> Job:
    values: dict[str, object] = {
        "job_id": "job_asr_feature",
        "project_id": "prj_feature_film",
        "job_type": "analysis.asr",
        "idempotency_key": "asr:feature-film:source-a:v1",
        "expected_output_types": (ArtifactType.TRANSCRIPT,),
        "progress": JobProgress(completed_units=0, total_units=100, unit_name="utterances"),
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(updates)
    return Job.model_validate(values)


def failure() -> JobError:
    return JobError(
        category=JobErrorCategory.WORKER_CRASH,
        code="worker_process_exit",
        message="ASR worker exited unexpectedly",
        retryable=True,
        remediation_hint="The job can be retried from its last checkpoint.",
        diagnostics={"exit_code": 137},
    )


def test_job_happy_path_is_an_immutable_state_machine() -> None:
    queued = job()
    preparing = queued.transition_to(JobStatus.PREPARING, at=NOW + timedelta(seconds=1))
    running = preparing.transition_to(JobStatus.RUNNING, at=NOW + timedelta(seconds=2))
    succeeded = running.transition_to(JobStatus.SUCCEEDED, at=NOW + timedelta(seconds=3))

    assert queued.status is JobStatus.QUEUED
    assert running.attempt == 1
    assert running.started_at == NOW + timedelta(seconds=2)
    assert succeeded.status is JobStatus.SUCCEEDED
    assert succeeded.finished_at == NOW + timedelta(seconds=3)
    assert succeeded.progress.fraction == 1.0


def test_invalid_transition_and_backwards_timestamp_are_rejected() -> None:
    queued = job()
    with pytest.raises(InvalidStateTransition):
        queued.transition_to(JobStatus.SUCCEEDED, at=NOW + timedelta(seconds=1))

    preparing = queued.transition_to(JobStatus.PREPARING, at=NOW + timedelta(seconds=2))
    with pytest.raises(ValueError, match="backwards"):
        preparing.transition_to(JobStatus.RUNNING, at=NOW + timedelta(seconds=1))


def test_failed_job_requires_structured_error_and_can_be_requeued() -> None:
    running = (
        job()
        .transition_to(JobStatus.PREPARING, at=NOW + timedelta(seconds=1))
        .transition_to(JobStatus.RUNNING, at=NOW + timedelta(seconds=2))
    )

    with pytest.raises(ValueError, match="structured error"):
        running.transition_to(JobStatus.FAILED, at=NOW + timedelta(seconds=3))

    failed = running.transition_to(
        JobStatus.FAILED,
        at=NOW + timedelta(seconds=3),
        error=failure(),
    )
    requeued = failed.transition_to(JobStatus.QUEUED, at=NOW + timedelta(seconds=4))

    assert failed.error == failure()
    assert requeued.error is None
    assert requeued.finished_at is None


def test_terminal_job_cannot_be_constructed_without_consistent_fields() -> None:
    with pytest.raises(ValidationError, match="finish timestamp"):
        job(status=JobStatus.CANCELLED)
    with pytest.raises(ValidationError, match="structured error"):
        job(status=JobStatus.FAILED, finished_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError, match="complete progress"):
        job(status=JobStatus.SUCCEEDED, started_at=NOW, finished_at=NOW)


def test_job_dependencies_and_output_contracts_are_nonempty_unique_and_acyclic_locally() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        job(expected_output_types=())
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        job(expected_output_types=(ArtifactType.TRANSCRIPT, ArtifactType.TRANSCRIPT))
    with pytest.raises(ValidationError, match="depend on itself"):
        job(dependency_job_ids=("job_asr_feature",))


def test_resource_reservations_require_consistent_gpu_and_positive_provider_quota() -> None:
    assert ResourceRequest(gpu_count=1, vram_mib=8_192).vram_mib == 8_192

    with pytest.raises(ValidationError, match="requires at least one GPU"):
        ResourceRequest(gpu_count=0, vram_mib=1_024)
    with pytest.raises(ValidationError, match="explicit VRAM"):
        ResourceRequest(gpu_count=1, vram_mib=0)
    with pytest.raises(ValidationError, match="must be positive"):
        ResourceRequest(provider_quota_units={"openai": 0})


def test_retry_policy_and_attempt_count_are_bounded() -> None:
    with pytest.raises(ValidationError, match="smaller"):
        RetryPolicy(initial_backoff_ms=2_000, max_backoff_ms=1_000)
    with pytest.raises(ValidationError, match="exceed"):
        job(attempt=4, retry_policy=RetryPolicy(max_attempts=3))


def test_canonical_transition_policy_is_exhaustive_and_rejects_same_state() -> None:
    expected: dict[JobStatus, frozenset[JobStatus]] = {
        JobStatus.QUEUED: frozenset(
            {
                JobStatus.BLOCKED,
                JobStatus.PREPARING,
                JobStatus.CANCELLING,
                JobStatus.CANCELLED,
                JobStatus.STALE,
            }
        ),
        JobStatus.BLOCKED: frozenset(
            {JobStatus.QUEUED, JobStatus.CANCELLING, JobStatus.CANCELLED, JobStatus.STALE}
        ),
        JobStatus.PREPARING: frozenset(
            {JobStatus.RUNNING, JobStatus.CANCELLING, JobStatus.FAILED, JobStatus.STALE}
        ),
        JobStatus.RUNNING: frozenset(
            {
                JobStatus.PAUSING,
                JobStatus.CANCELLING,
                JobStatus.FAILED,
                JobStatus.SUCCEEDED,
                JobStatus.STALE,
            }
        ),
        JobStatus.PAUSING: frozenset(
            {JobStatus.PAUSED, JobStatus.CANCELLING, JobStatus.FAILED, JobStatus.STALE}
        ),
        JobStatus.PAUSED: frozenset(
            {
                JobStatus.QUEUED,
                JobStatus.PREPARING,
                JobStatus.CANCELLING,
                JobStatus.CANCELLED,
                JobStatus.STALE,
            }
        ),
        JobStatus.CANCELLING: frozenset({JobStatus.CANCELLED, JobStatus.FAILED}),
        JobStatus.CANCELLED: frozenset({JobStatus.QUEUED, JobStatus.STALE}),
        JobStatus.FAILED: frozenset({JobStatus.QUEUED, JobStatus.STALE}),
        JobStatus.SUCCEEDED: frozenset({JobStatus.STALE}),
        JobStatus.STALE: frozenset({JobStatus.QUEUED}),
    }

    observed = {
        (current, target): can_transition_job_status(current, target)
        for current in JobStatus
        for target in JobStatus
    }

    assert len(observed) == 121
    assert all(
        allowed is (current is not target and target in expected[current])
        for (current, target), allowed in observed.items()
    )
