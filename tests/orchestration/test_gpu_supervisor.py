from __future__ import annotations

import hashlib

import pytest

from aidub.contracts.jobs import JobDescriptor
from aidub.contracts.worker_ipc import (
    CURRENT_IPC_PROTOCOL_VERSION,
    GpuCapabilitySpec,
    IpcMessageType,
    WorkerIpcEnvelope,
)
from aidub.contracts.workers import WorkerCapability
from aidub.orchestration.gpu_supervisor import GpuWorkerSupervisor, WorkerCrashedError


def make_gpu_job(job_id: str, job_type: str, **parameters: object) -> JobDescriptor:
    return JobDescriptor(
        job_id=job_id,
        idempotency_key=hashlib.sha256(job_id.encode()).hexdigest(),
        project_id="prj_gpu_test",
        job_type=job_type,
        parameters=parameters,
    )


def test_ipc_envelope_construction() -> None:
    envelope = WorkerIpcEnvelope(
        message_id="msg_001",
        message_type=IpcMessageType.HANDSHAKE,
        sender_id="gpu_worker_0",
        payload={"gpu_ids": [0]},
    )
    assert envelope.is_type(IpcMessageType.HANDSHAKE)
    assert envelope.sender_id == "gpu_worker_0"


def test_gpu_capability_spec_validation() -> None:
    spec = GpuCapabilitySpec(
        device_index=0,
        device_name="NVIDIA GeForce RTX 4090",
        total_vram_mb=24576,
        available_vram_mb=20480,
        supported_capabilities=frozenset([WorkerCapability.ASR, WorkerCapability.VOICE]),
    )
    assert spec.device_index == 0
    assert "float16" in spec.supported_precisions


def test_gpu_worker_supervisor_lifecycle() -> None:
    supervisor = GpuWorkerSupervisor(
        gpu_id=0,
        required_capabilities=frozenset([WorkerCapability.ASR]),
    )
    with supervisor:
        assert supervisor.is_alive
        assert supervisor.process_id is not None
        assert supervisor.handshake is not None
        assert supervisor.handshake.protocol == CURRENT_IPC_PROTOCOL_VERSION

        # Submit test job
        job = make_gpu_job("job_gpu_echo", "system.echo", message="GPU test")
        supervisor.submit(job)
        result = supervisor.wait(timeout_seconds=5.0)

        assert result.succeeded
        assert result.job_id == "job_gpu_echo"


def test_gpu_worker_crash_containment_and_restart() -> None:
    supervisor = GpuWorkerSupervisor(gpu_id=0)
    supervisor.start()
    try:
        job = make_gpu_job("job_crash", "system.crash_test")
        supervisor.submit(job)

        with pytest.raises(WorkerCrashedError):
            supervisor.wait(timeout_seconds=5.0)

        # Worker is dead, but main app context survives
        assert not supervisor.is_alive

        # Supervisor can restart cleanly
        supervisor.restart()
        assert supervisor.is_alive

        job_health = make_gpu_job("job_health", "system.health")
        supervisor.submit(job_health)
        result = supervisor.wait(timeout_seconds=5.0)
        assert result.succeeded
    finally:
        supervisor.terminate()
