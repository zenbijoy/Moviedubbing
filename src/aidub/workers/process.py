"""Child-process entry point."""

from __future__ import annotations

import traceback
from typing import Any

from aidub.contracts.jobs import (
    ErrorCategory,
    JobDescriptor,
    JobError,
    JobResult,
)
from aidub.security.redaction import Redactor

from .context import JobCancelledError, WorkerContext
from .handlers import get_handler


def worker_process_main(job_queue: Any, control_queue: Any, result_queue: Any) -> None:
    result_queue.put({"type": "ready"})
    while True:
        message = job_queue.get()
        message_type = message.get("type")
        if message_type == "shutdown":
            result_queue.put({"type": "stopped"})
            return
        if message_type != "job":
            continue
        job = JobDescriptor.model_validate(message["payload"])
        context = WorkerContext(job.job_id, control_queue, result_queue)
        result_queue.put({"type": "started", "job_id": job.job_id})
        try:
            metrics = get_handler(job.job_type)(job, context)
            result = JobResult(job_id=job.job_id, succeeded=True, metrics=metrics)
        except JobCancelledError:
            result = JobResult(
                job_id=job.job_id,
                succeeded=False,
                error=JobError(
                    code="worker.cancelled",
                    category=ErrorCategory.CANCELLED,
                    retryable=False,
                    message_key="errors.worker.cancelled",
                ),
            )
        # Worker handlers are an isolation boundary: convert every ordinary
        # handler failure into a typed, redacted result. Process-ending
        # BaseException subclasses still escape and exercise crash recovery.
        except Exception as exc:
            result = JobResult(
                job_id=job.job_id,
                succeeded=False,
                error=JobError(
                    code="worker.handler_failed",
                    category=ErrorCategory.WORKER,
                    retryable=False,
                    message_key="errors.worker.handler_failed",
                    safe_details={
                        "exception_type": type(exc).__name__,
                        "message": Redactor.text(str(exc))[:500],
                    },
                ),
            )
            result_queue.put(
                {
                    "type": "diagnostic",
                    "job_id": job.job_id,
                    "traceback": Redactor.text(traceback.format_exc())[-8_192:],
                }
            )
        result_queue.put({"type": "result", "payload": result.model_dump(mode="json")})
