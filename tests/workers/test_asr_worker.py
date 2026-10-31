from __future__ import annotations

import hashlib

from aidub.contracts.jobs import JobDescriptor
from aidub.domain.identifiers import MediaAssetId, ProjectId
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.domain.types import LanguageTag, Sha256
from aidub.speech.contracts import SpeechRecognitionRequest
from aidub.workers.supervisor import LocalWorkerSupervisor


def make_asr_job(job_id: str) -> JobDescriptor:
    audio_range = AudioSampleRange(
        start=AudioSamplePosition(sample_index=0, sample_rate=48_000),
        sample_count=96_000,
    )
    request = SpeechRecognitionRequest(
        request_id=f"req_{job_id}",
        project_id=ProjectId("prj_asr_worker"),
        media_asset_id=MediaAssetId("med_audio_worker"),
        source_audio_sha256=Sha256(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        language=LanguageTag("en-US"),
        full_audio_range=audio_range,
        audio_range=audio_range,
    )
    return JobDescriptor(
        job_id=job_id,
        idempotency_key=hashlib.sha256(job_id.encode()).hexdigest(),
        project_id="prj_asr_worker",
        job_type="speech.asr",
        parameters={
            "request": request.model_dump(mode="json"),
            "options": {"device": "cpu", "compute_type": "float32"},
        },
    )


def test_asr_worker_rejects_job_without_real_audio_source() -> None:
    with LocalWorkerSupervisor() as supervisor:
        job = make_asr_job("job_asr_001")
        supervisor.submit(job)
        result = supervisor.wait(timeout_seconds=30.0)

        assert not result.succeeded
        assert result.error is not None
        assert "real source_audio_path" in result.error.safe_details["message"]
