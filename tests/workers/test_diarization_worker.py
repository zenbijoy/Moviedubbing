from __future__ import annotations

import hashlib

from aidub.contracts.jobs import JobDescriptor
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.workers.supervisor import LocalWorkerSupervisor


def make_diarize_job(job_id: str) -> JobDescriptor:
    audio_range = AudioSampleRange(
        start=AudioSamplePosition(sample_index=0, sample_rate=48_000),
        sample_count=96_000,
    )
    return JobDescriptor(
        job_id=job_id,
        idempotency_key=hashlib.sha256(job_id.encode()).hexdigest(),
        project_id="prj_diar_worker",
        job_type="speech.diarize",
        parameters={
            "audio_range": audio_range.model_dump(mode="json"),
            "source_audio_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "options": {"device": "cpu"},
        },
    )


def test_diarization_worker_rejects_job_without_real_audio_source() -> None:
    with LocalWorkerSupervisor() as supervisor:
        job = make_diarize_job("job_diar_001")
        supervisor.submit(job)
        result = supervisor.wait(timeout_seconds=30.0)

        assert not result.succeeded
        assert result.error is not None
        assert "real source_audio_path" in result.error.safe_details["message"]
