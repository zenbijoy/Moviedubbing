"""Typed Pipeline Error System and Exit Code Mapping (from KrillinAI + open-dubbing)."""

from __future__ import annotations

from enum import StrEnum


class ErrorKind(StrEnum):
    """Classification of pipeline error severity and retryability."""

    USAGE = "usage"  # Invalid arguments or missing files (non-retryable)
    RETRYABLE = "retryable"  # Temporary rate limits, API timeout, GPU OOM (retryable)
    DEPENDENCY = "dependency"  # Missing system dependencies (ffmpeg, demucs)
    INTERNAL = "internal"  # Code bug or assertion error


class PipelineError(Exception):
    """Typed pipeline exception carrying metadata for API responses and manifests."""

    def __init__(
        self,
        kind: ErrorKind,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.message = message
        self.retryable = retryable or (kind == ErrorKind.RETRYABLE)

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "kind": self.kind.value,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


def exit_code_for_error(err: PipelineError) -> int:
    """Map ErrorKind to CLI exit status codes."""
    mapping = {
        ErrorKind.USAGE: 1,
        ErrorKind.RETRYABLE: 2,
        ErrorKind.DEPENDENCY: 3,
        ErrorKind.INTERNAL: 4,
    }
    return mapping.get(err.kind, 1)


__all__ = ["ErrorKind", "PipelineError", "exit_code_for_error"]
