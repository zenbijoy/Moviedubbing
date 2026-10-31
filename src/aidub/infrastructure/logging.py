"""
Secure logging infrastructure: API key redaction, PII masking, and audit log formatting.

Provides:
  - RedactionFilter: strips API keys, tokens, and phone numbers from all log records
  - configure_secure_logging(): one-call setup for production log config
  - PrivateStudioGuard: raises PrivateStudioViolation if any network call is
    attempted while PrivacyPolicy is set to OFFLINE
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import platformdirs

from aidub.security.privacy import DataClass, NetworkPolicy, PrivacyPolicy

logger = logging.getLogger(__name__)


def get_default_log_file() -> Path:
    """Return default writable log file in user's application log directory."""
    log_dir = Path(platformdirs.user_log_dir("aidub", "AIDubStudio"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "aidub_desktop.log"


# ── Redaction patterns ────────────────────────────────────────────────────────

_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Generic bearer / API tokens
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_\.]{16,}", re.IGNORECASE), r"\1[REDACTED]"),
    # OpenAI-style keys  sk-...
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[API_KEY_REDACTED]"),
    # Anthropic keys  sk-ant-...
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"), "[API_KEY_REDACTED]"),
    # Generic 40-char hex API keys
    (re.compile(r"\b[A-Fa-f0-9]{40}\b"), "[HEX_TOKEN_REDACTED]"),
    # HuggingFace tokens  hf_...
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "[HF_TOKEN_REDACTED]"),
    # phone numbers  +880-1234-567890
    (re.compile(r"\+?\d[\d\s\-]{8,14}\d"), "[PHONE_REDACTED]"),
    # email addresses
    (re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"), "[EMAIL_REDACTED]"),
]


class RedactionFilter(logging.Filter):
    """Log filter that strips sensitive data from all log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(str(record.msg))
        record.args = _redact_args(record.args)
        return True


def _redact(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redact_args(
    args: tuple[object, ...] | Mapping[str, object] | None,
) -> tuple[object, ...] | Mapping[str, object] | None:
    if isinstance(args, tuple):
        return tuple(_redact(str(a)) if isinstance(a, str) else a for a in args)
    if isinstance(args, dict):
        return {k: _redact(str(v)) if isinstance(v, str) else v for k, v in args.items()}
    return args


class InAppLogHandler(logging.Handler):
    """Thread-safe in-memory ring buffer of log records for in-app UI display."""

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        from collections import deque
        import threading

        self._records: deque[str] = deque(maxlen=capacity)
        self._callbacks: list[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._records.append(msg)
                cbs = list(self._callbacks)
            for cb in cbs:
                try:
                    cb(msg)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_lines(self) -> list[str]:
        with self._lock:
            return list(self._records)

    def add_callback(self, cb: Callable[[str], None]) -> None:
        with self._lock:
            if cb not in self._callbacks:
                self._callbacks.append(cb)

    def remove_callback(self, cb: Callable[[str], None]) -> None:
        with self._lock:
            if cb in self._callbacks:
                self._callbacks.remove(cb)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


_IN_APP_HANDLER: InAppLogHandler | None = None


def get_in_app_log_handler() -> InAppLogHandler:
    global _IN_APP_HANDLER
    if _IN_APP_HANDLER is None:
        _IN_APP_HANDLER = InAppLogHandler()
    return _IN_APP_HANDLER


def configure_secure_logging(
    *,
    level: int = logging.INFO,
    redact: bool = True,
    log_file: Path | str | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """Configure root logger with optional redaction filter, structured format, and log rotation.

    Should be called once at application startup before any log output.
    """
    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    # Console stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    if redact:
        stream_handler.addFilter(RedactionFilter())
    root.addHandler(stream_handler)

    # In-app log handler for live UI viewing
    in_app = get_in_app_log_handler()
    in_app.setLevel(level)
    in_app.setFormatter(formatter)
    if redact:
        in_app.addFilter(RedactionFilter())
    if in_app not in root.handlers:
        root.addHandler(in_app)

    # Optional bounded rotating file handler
    if log_file is not None:
        target_path = Path(log_file)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(target_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        if redact:
            file_handler.addFilter(RedactionFilter())
        root.addHandler(file_handler)

    logger.debug(
        "secure logging configured (redact=%s, log_file=%s)",
        redact,
        str(log_file) if log_file else "None",
    )


# ── Private Studio Guard ──────────────────────────────────────────────────────


class PrivateStudioViolation(PermissionError):
    """Raised when a network operation is attempted in Private Studio (offline) mode."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"Private Studio Mode is active. Network operation blocked: {operation!r}")
        self.operation = operation


@dataclass(frozen=True)
class PrivateStudioGuard:
    """
    Fail-closed guard for Private Studio Mode.

    Wrap any code block that may perform network I/O:

        guard = PrivateStudioGuard(policy)
        guard.require_network_allowed("openai.complete")
    """

    policy: PrivacyPolicy

    def require_network_allowed(
        self,
        operation: str,
        *,
        provider_id: str = "",
        data_class: DataClass = DataClass.TEXT,
    ) -> None:
        """
        Assert that the network operation is permitted by the active privacy policy.

        Raises PrivateStudioViolation if policy is OFFLINE or STUDIO_LOCKED and
        the operation is not internally routed.
        """
        if self.policy.network == NetworkPolicy.OFFLINE:
            raise PrivateStudioViolation(operation)

        if provider_id:
            decision = self.policy.evaluate(
                provider_id=provider_id,
                data_class=data_class,
            )
            if not decision.allowed:
                raise PrivateStudioViolation(f"{operation} ({decision.reason_code})")


__all__ = [
    "InAppLogHandler",
    "PrivateStudioGuard",
    "PrivateStudioViolation",
    "RedactionFilter",
    "configure_secure_logging",
    "get_default_log_file",
    "get_in_app_log_handler",
]
