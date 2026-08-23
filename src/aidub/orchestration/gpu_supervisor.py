"""GPU Worker Supervisor for isolated GPU inference lifecycle, OOM recovery, and telemetry."""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue
import time
from dataclasses import dataclass
from typing import Any, Self, cast

from aidub.contracts.jobs import JobDescriptor, JobProgress, JobResult
from aidub.contracts.worker_ipc import (
    CURRENT_IPC_PROTOCOL_VERSION,
    GpuCapabilitySpec,
    GpuOomPayload,
)
from aidub.contracts.workers import HealthState, WorkerCapability, WorkerHandshake, WorkerHeartbeat
from aidub.workers.supervisor import WorkerCrashedError, WorkerTimeoutError

logger = logging.getLogger(__name__)


class GpuOomError(RuntimeError):
    """Raised when a GPU worker encounters a CUDA Out-Of-Memory error."""

    def __init__(self, payload: GpuOomPayload) -> None:
        super().__init__(
            f"GPU device {payload.device_index} OOM: requested {payload.requested_vram_mb} MB, "
            f"free {payload.free_vram_mb} MB"
        )
        self.payload = payload


@dataclass(frozen=True, slots=True)
class GpuWorkerState:
    worker_id: str
    gpu_id: int
    handshake: WorkerHandshake
    latest_heartbeat: WorkerHeartbeat | None = None
    is_active: bool = False


class GpuWorkerSupervisor:
    """Manages an isolated GPU worker process, CUDA lifecycle, telemetry, and OOM recovery."""

    def __init__(
        self,
        *,
        gpu_id: int = 0,
        required_capabilities: frozenset[WorkerCapability] | None = None,
        startup_timeout_seconds: float = 15.0,
    ) -> None:
        self.gpu_id = gpu_id
        self.required_capabilities = required_capabilities or frozenset()
        self._startup_timeout_seconds = startup_timeout_seconds
        self._ctx = mp.get_context("spawn")
        self._job_queue: Any | None = None
        self._control_queue: Any | None = None
        self._result_queue: Any | None = None
        self._process: Any | None = None
        self._active_job_id: str | None = None
        self._handshake: WorkerHandshake | None = None
        self._latest_heartbeat: WorkerHeartbeat | None = None
        self._gpu_spec: GpuCapabilitySpec | None = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def handshake(self) -> WorkerHandshake | None:
        return self._handshake

    @property
    def latest_heartbeat(self) -> WorkerHeartbeat | None:
        return self._latest_heartbeat

    @property
    def active_job_id(self) -> str | None:
        return self._active_job_id

    def start(self) -> None:
        if self.is_alive:
            return
        self._job_queue = self._ctx.Queue()
        self._control_queue = self._ctx.Queue()
        self._result_queue = self._ctx.Queue()

        from aidub.workers.process import worker_process_main

        proc = self._ctx.Process(
            target=worker_process_main,
            args=(self._job_queue, self._control_queue, self._result_queue),
            name=f"aidub-gpu-worker-{self.gpu_id}",
            daemon=True,
        )
        self._process = proc
        proc.start()

        # Execute Handshake Protocol
        raw_msg = self._receive(self._startup_timeout_seconds)
        if raw_msg is None or raw_msg.get("type") != "ready":
            self.terminate()
            raise RuntimeError("GPU worker process failed initial startup handshake")

        # Synthesize & validate worker handshake
        self._handshake = WorkerHandshake(
            worker_id=f"gpu_worker_{self.gpu_id}_{self.process_id}",
            worker_version="0.1.0",
            engine_id=f"cuda_engine_{self.gpu_id}",
            protocol=CURRENT_IPC_PROTOCOL_VERSION,
            process_id=self.process_id or 1,
            capabilities=self.required_capabilities or frozenset([WorkerCapability.ASR]),
            gpu_ids=(self.gpu_id,),
        )
        self._latest_heartbeat = WorkerHeartbeat(
            worker_id=self._handshake.worker_id,
            state=HealthState.HEALTHY,
        )

    def restart(self) -> None:
        """Cleanly terminate and restart GPU worker (e.g. after CUDA fault or OOM)."""
        logger.warning(f"Restarting GPU worker on device {self.gpu_id}")
        self.terminate()
        self.start()

    def submit(self, job: JobDescriptor) -> None:
        self._ensure_alive()
        if self._active_job_id is not None:
            raise RuntimeError(f"GPU worker already running job {self._active_job_id}")
        assert self._job_queue is not None
        self._active_job_id = job.job_id
        self._job_queue.put({"type": "job", "payload": job.model_dump(mode="json")})

    def cancel(self, job_id: str) -> None:
        self._ensure_alive()
        if job_id != self._active_job_id:
            raise ValueError(f"Job {job_id} is not active on GPU worker {self.gpu_id}")
        assert self._control_queue is not None
        self._control_queue.put({"type": "cancel", "job_id": job_id})

    def wait(
        self,
        *,
        timeout_seconds: float = 60.0,
        on_progress: Any | None = None,
        on_heartbeat: Any | None = None,
    ) -> JobResult:
        if self._active_job_id is None:
            raise RuntimeError("No active job on GPU worker")
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerTimeoutError(
                    f"GPU Job {self._active_job_id} exceeded timeout of {timeout_seconds}s"
                )
            message = self._receive(min(remaining, 0.25), allow_empty=True)
            if message is None:
                self._ensure_alive()
                continue

            msg_type = message.get("type")
            if msg_type == "progress":
                progress = JobProgress.model_validate(message["payload"])
                if on_progress is not None:
                    on_progress(progress)
            elif msg_type == "heartbeat":
                heartbeat = WorkerHeartbeat.model_validate(message["payload"])
                self._latest_heartbeat = heartbeat
                if on_heartbeat is not None:
                    on_heartbeat(heartbeat)
            elif msg_type == "oom_error":
                payload = GpuOomPayload.model_validate(message["payload"])
                self._active_job_id = None
                raise GpuOomError(payload)
            elif msg_type == "result":
                result = JobResult.model_validate(message["payload"])
                if result.job_id != self._active_job_id:
                    raise RuntimeError("GPU worker returned result for unexpected job ID")
                self._active_job_id = None
                return result

    def terminate(self) -> None:
        if self._process is not None and self._process.is_alive():
            self._process.terminate()
            self._process.join(5)
        self._close_queues()
        self._process = None
        self._active_job_id = None
        self._handshake = None

    def _receive(
        self, timeout_seconds: float, *, allow_empty: bool = False
    ) -> dict[str, Any] | None:
        assert self._result_queue is not None
        try:
            return cast("dict[str, Any]", self._result_queue.get(timeout=timeout_seconds))
        except queue.Empty:
            if allow_empty:
                return None
            self._ensure_alive()
            raise WorkerTimeoutError("Timed out waiting for GPU worker response") from None

    def _ensure_alive(self) -> None:
        if self._process is None:
            raise RuntimeError("GPU worker has not been started")
        if not self._process.is_alive():
            exit_code = self._process.exitcode
            self._active_job_id = None
            raise WorkerCrashedError(exit_code)

    def _close_queues(self) -> None:
        for item in (self._job_queue, self._control_queue, self._result_queue):
            if item is not None:
                item.close()
                item.join_thread()
        self._job_queue = None
        self._control_queue = None
        self._result_queue = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.terminate()


__all__ = [
    "GpuOomError",
    "GpuWorkerState",
    "GpuWorkerSupervisor",
]
