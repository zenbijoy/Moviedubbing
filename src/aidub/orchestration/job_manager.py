"""Central background Job Manager and execution queue.

Provides:
  - JobStatus: lifecycle states (queued, running, done, failed, cancelled)
  - Job: tracks individual job metadata, progress (0.0..1.0), ETA, cancellation, and log stream.
  - JobManager: thread-safe central queue with worker thread pool, signal dispatch,
    active job accounting, and dummy job runner for testing.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QObject, Signal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    QObject = object  # type: ignore
    Signal = lambda *args: None  # type: ignore


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_active(self) -> bool:
        return self in (JobStatus.QUEUED, JobStatus.RUNNING)

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)


@dataclass
class Job:
    """Descriptor and state of a single background unit of work."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Background Job"
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0  # 0.0 to 1.0
    eta_seconds: float | None = None
    log_lines: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    cancel_requested: bool = False
    _cancel_callback: Callable[[], None] | None = None
    _last_progress_update: float = field(default=0.0, repr=False)

    def cancel(self) -> None:
        """Request immediate job cancellation."""
        if self.status.is_terminal:
            return
        self.cancel_requested = True
        logger.info("Job %s (%s) cancellation requested", self.id, self.name)
        if self._cancel_callback is not None:
            try:
                self._cancel_callback()
            except Exception as exc:
                logger.warning("Error running cancel callback on job %s: %s", self.id, exc)
        self.status = JobStatus.CANCELLED
        self.ended_at = time.time()
        self.add_log("Job was cancelled by user.")

    def add_log(self, text: str) -> None:
        """Append log line to job history."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {text}")

    def update_progress(self, progress: float, eta_seconds: float | None = None) -> None:
        """Update progress ratio (0.0 to 1.0) and optional ETA."""
        self.progress = max(0.0, min(1.0, float(progress)))
        if eta_seconds is not None:
            self.eta_seconds = max(0.0, float(eta_seconds))
        self._last_progress_update = time.time()


if _HAS_QT:
    class _JobManagerSignals(QObject):
        active_count_changed = Signal(int)
        job_added = Signal(object)
        job_updated = Signal(object)
        job_finished = Signal(object)


class JobManager:
    """Authoritative singleton job queue and background executor."""

    _instance: JobManager | None = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4) -> None:
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aidub_worker")
        self._listeners: list[Callable[[Job], None]] = []
        self._state_lock = threading.RLock()
        self.signals = _JobManagerSignals() if _HAS_QT else None

    @classmethod
    def get_instance(cls) -> JobManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def active_jobs_count(self) -> int:
        with self._state_lock:
            return sum(1 for j in self._jobs.values() if j.status.is_active)

    def _notify_count_changed(self) -> None:
        count = self.active_jobs_count
        if self.signals is not None:
            try:
                self.signals.active_count_changed.emit(count)
            except Exception:
                pass

    def _notify_job_event(self, job: Job, event_type: str) -> None:
        if self.signals is not None:
            try:
                if event_type == "added":
                    self.signals.job_added.emit(job)
                elif event_type == "updated":
                    self.signals.job_updated.emit(job)
                elif event_type == "finished":
                    self.signals.job_finished.emit(job)
            except Exception:
                pass
        for listener in list(self._listeners):
            try:
                listener(job)
            except Exception as exc:
                logger.error("Job listener error: %s", exc)

    def add_listener(self, callback: Callable[[Job], None]) -> None:
        with self._state_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Job], None]) -> None:
        with self._state_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def get_job(self, job_id: str) -> Job | None:
        with self._state_lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._state_lock:
            return list(self._jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        with self._state_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.cancel()
            future = self._futures.get(job_id)
            if future is not None:
                future.cancel()
        self._notify_count_changed()
        self._notify_job_event(job, "finished")
        return True

    def submit_job(
        self,
        name: str,
        task_fn: Callable[[Job], Any],
        cancel_callback: Callable[[], None] | None = None,
    ) -> Job:
        """Submit a unit of work to the central thread pool."""
        job = Job(name=name, _cancel_callback=cancel_callback)
        job.add_log(f"Job queued: {name}")

        with self._state_lock:
            self._jobs[job.id] = job

        self._notify_count_changed()
        self._notify_job_event(job, "added")

        def _runner() -> None:
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                job.ended_at = time.time()
                self._notify_count_changed()
                self._notify_job_event(job, "finished")
                return

            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.add_log(f"Job running on worker thread: {name}")
            self._notify_count_changed()
            self._notify_job_event(job, "updated")

            try:
                task_fn(job)
                if not job.cancel_requested:
                    job.status = JobStatus.DONE
                    job.progress = 1.0
                    job.ended_at = time.time()
                    job.add_log("Job completed successfully.")
            except Exception as exc:
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                    job.ended_at = time.time()
                else:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    job.ended_at = time.time()
                    job.add_log(f"Job failed with error: {exc}")
                    logger.exception("Job %s (%s) failed", job.id, job.name)
            finally:
                self._notify_count_changed()
                self._notify_job_event(job, "finished")

        future = self._executor.submit(_runner)
        with self._state_lock:
            self._futures[job.id] = future

        return job

    def start_dummy_job(self, name: str = "Test Background Job", duration: float = 3.0) -> Job:
        """Execute a controlled test job for UI binding and cancellation verification."""
        def _dummy_task(job: Job) -> None:
            steps = 30
            step_sleep = duration / steps
            start_t = time.time()
            for i in range(1, steps + 1):
                if job.cancel_requested:
                    job.add_log("Dummy job observed cancel flag.")
                    break
                time.sleep(step_sleep)
                elapsed = time.time() - start_t
                rem = max(0.0, duration - elapsed)
                pct = i / steps
                job.update_progress(pct, eta_seconds=rem)
                job.add_log(f"Dummy progress: {int(pct * 100)}% (ETA: {rem:.1f}s)")
                self._notify_job_event(job, "updated")

        return self.submit_job(name=name, task_fn=_dummy_task)


def get_job_manager() -> JobManager:
    """Access application-wide JobManager instance."""
    return JobManager.get_instance()


__all__ = [
    "Job",
    "JobManager",
    "JobStatus",
    "get_job_manager",
]
