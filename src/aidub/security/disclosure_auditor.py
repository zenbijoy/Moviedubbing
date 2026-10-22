"""
Data Disclosure & Privacy Compliance Auditor.

Audits outbound cloud LLM/TTS provider data disclosures for legal compliance.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class DisclosureRecord(ContractModel):
    """Data disclosure record."""

    record_id: Identifier
    provider_name: str = Field(min_length=1)
    data_category: str = Field(min_length=1)  # "translation_prompt", "voice_reference"
    retained_by_provider: bool = False


class DataDisclosureAuditor:
    """
    Audits provider data disclosures.
    """

    def audit_disclosures(self, records: Sequence[DisclosureRecord]) -> bool:
        """
        Audit disclosure records for compliance.
        """
        compliant = all(not r.retained_by_provider for r in records)
        logger.info(
            "disclosure_auditor: audited %d disclosure records (Compliant: %s)",
            len(records),
            compliant,
        )
        return compliant


__all__ = [
    "DataDisclosureAuditor",
    "DisclosureRecord",
]
