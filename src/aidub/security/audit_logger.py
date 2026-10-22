"""
Cryptographic Tamper-Evident Studio Audit Logger.

Maintains immutable, hash-chained security audit logs for consent checks,
voice profile modifications, render passes, and master distribution exports.
"""

from __future__ import annotations

import hashlib
import logging

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class AuditEvent(ContractModel):
    """Single audit log entry with SHA-256 hash chaining."""

    event_id: Identifier
    event_type: str = Field(
        min_length=1
    )  # e.g. "CONSENT_CHECK", "VOICE_CLONE", "RENDER_PASS", "EXPORT_DCP"
    actor_id: Identifier
    details: str = Field(min_length=1)
    timestamp_iso: str = Field(min_length=1)
    previous_hash: str = Field(default="0" * 64, min_length=64, max_length=64)
    current_hash: str = Field(default="", max_length=64)

    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of this entry combined with previous_hash."""
        raw = f"{self.event_id}:{self.event_type}:{self.actor_id}:{self.details}:{self.timestamp_iso}:{self.previous_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CryptographicAuditLogger:
    """
    Cryptographic audit logger maintaining tamper-evident chain of studio events.
    """

    def __init__(self) -> None:
        self.chain: list[AuditEvent] = []

    def log_event(
        self,
        event_id: str,
        event_type: str,
        actor_id: str,
        details: str,
        timestamp_iso: str = "2026-08-14T10:00:00Z",
    ) -> AuditEvent:
        """
        Append entry to tamper-evident audit chain.
        """
        eid = Identifier(event_id)
        aid = Identifier(actor_id)

        prev_hash = self.chain[-1].current_hash if self.chain else "0" * 64

        entry = AuditEvent(
            event_id=eid,
            event_type=event_type,
            actor_id=aid,
            details=details,
            timestamp_iso=timestamp_iso,
            previous_hash=prev_hash,
        )
        chash = entry.calculate_hash()
        final_entry = entry.model_copy(update={"current_hash": chash})
        self.chain.append(final_entry)

        logger.info("audit_logger: logged event %s (%s) [Hash: %s...]", eid, event_type, chash[:12])
        return final_entry

    def verify_chain_integrity(self) -> bool:
        """
        Verify every link in the hash chain. Returns True if valid, False if tampered.
        """
        if not self.chain:
            return True

        for i, item in enumerate(self.chain):
            expected_prev = self.chain[i - 1].current_hash if i > 0 else "0" * 64
            if item.previous_hash != expected_prev:
                logger.error("audit_logger: BROKEN CHAIN at index %d (Previous hash mismatch)", i)
                return False

            if item.current_hash != item.calculate_hash():
                logger.error("audit_logger: TAMPERED ENTRY at index %d (Current hash mismatch)", i)
                return False

        return True


__all__ = [
    "AuditEvent",
    "CryptographicAuditLogger",
]
