from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aidub.contracts.jobs import (
    ErrorCategory,
    JobDescriptor,
    JobError,
    JobProgress,
    JobResult,
    ResourceRequest,
)
from aidub.contracts.providers import (
    ProviderConstraints,
    ProviderRequest,
    ProviderTask,
)
from aidub.contracts.workers import ProtocolVersion

HASH = hashlib.sha256(b"test").hexdigest()


def test_vram_requires_gpu() -> None:
    with pytest.raises(ValidationError):
        ResourceRequest(vram_mb=1024)


def test_progress_is_bounded_and_has_fraction() -> None:
    progress = JobProgress(job_id="job-1", completed_units=3, total_units=4)
    assert progress.fraction == 0.75
    with pytest.raises(ValidationError):
        JobProgress(job_id="job-1", completed_units=5, total_units=4)


def test_failed_result_requires_error() -> None:
    with pytest.raises(ValidationError):
        JobResult(job_id="job-1", succeeded=False)
    error = JobError(
        code="provider.timeout",
        category=ErrorCategory.PROVIDER,
        retryable=True,
        message_key="errors.provider.timeout",
    )
    assert JobResult(job_id="job-1", succeeded=False, error=error).error == error


def test_job_cannot_depend_on_itself() -> None:
    with pytest.raises(ValidationError):
        JobDescriptor(
            job_id="job-1",
            idempotency_key=HASH,
            project_id="project-1",
            job_type="asr",
            dependencies=("job-1",),
        )


def test_provider_request_is_strict_and_locale_aware() -> None:
    request = ProviderRequest(
        request_id="request-1",
        task=ProviderTask.TRANSLATE,
        project_id="project-1",
        utterance_id="utterance-1",
        source_language="en",
        target_language="bn-BD",
        source_text="Where are you going?",
        constraints=ProviderConstraints(response_schema="translation.v1"),
        prompt_id="translation",
        prompt_version="1.0",
        request_hash=HASH,
    )
    assert request.target_language == "bn-BD"
    with pytest.raises(ValidationError):
        ProviderRequest.model_validate({**request.model_dump(), "unknown": True})


def test_protocol_compatibility_requires_same_major() -> None:
    server = ProtocolVersion(major=1, minor=3)
    assert server.is_compatible_with(ProtocolVersion(major=1, minor=2))
    assert not server.is_compatible_with(ProtocolVersion(major=2, minor=0))
