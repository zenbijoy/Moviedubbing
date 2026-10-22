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
import re
from collections.abc import Mapping
from dataclasses import dataclass

from aidub.security.privacy import DataClass, NetworkPolicy, PrivacyPolicy

logger = logging.getLogger(__name__)


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


def configure_secure_logging(
    *,
    level: int = logging.INFO,
    redact: bool = True,
) -> None:
    """
    Configure root logger with optional redaction filter and structured format.

    Should be called once at application startup before any log output.
    """
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)

    if redact:
        handler.addFilter(RedactionFilter())

    root.addHandler(handler)
    logger.debug("secure logging configured (redact=%s)", redact)


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
    "PrivateStudioGuard",
    "PrivateStudioViolation",
    "RedactionFilter",
    "configure_secure_logging",
]
