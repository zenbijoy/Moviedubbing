from __future__ import annotations

import hashlib
from pathlib import Path

from aidub.contracts.jobs import JobDescriptor
from aidub.workers.supervisor import LocalWorkerSupervisor


def make_separation_job(job_id: str, tmp_path: Path) -> JobDescriptor:
    out_dir = tmp_path / "worker_stems"
    return JobDescriptor(
        job_id=job_id,
        idempotency_key=hashlib.sha256(job_id.encode()).hexdigest(),
        project_id="prj_sep_worker",
        job_type="media.separate_stems",
        parameters={
            "source_audio_path": "source.wav",
            "output_directory": str(out_dir),
            "policy": "force_ai_separation",
            "options": {"device": "cpu"},
        },
    )


def test_separation_worker_rejects_missing_source(tmp_path: Path) -> None:
    with LocalWorkerSupervisor() as supervisor:
        job = make_separation_job("job_sep_001", tmp_path)
        supervisor.submit(job)
        result = supervisor.wait(timeout_seconds=10.0)

        assert not result.succeeded
        assert result.error is not None
        assert "source audio does not exist" in result.error.safe_details["message"]
