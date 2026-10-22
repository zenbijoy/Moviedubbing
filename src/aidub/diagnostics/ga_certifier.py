"""
Final Studio Production GA Release Certifier.

Executes end-to-end automated system validation across all 20 phases and generates
a signed General Availability (GA) Release Certificate.
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class GACertificationUnavailableError(RuntimeError):
    """Raised when no verified release report and signing key are configured."""


class StudioGAReleaseCertificate(ContractModel):
    """General Availability (GA) Release Certificate container."""

    certificate_id: Identifier
    system_version: str = Field(min_length=1)
    phases_verified: int = Field(ge=0)
    total_unit_tests_passed: int = Field(ge=0)
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: str = Field(default="NOT_CERTIFIED")


class StudioGACertifier:
    """
    Studio GA Certification engine.
    """

    def generate_ga_certificate(self) -> StudioGAReleaseCertificate:
        """
        Refuse to fabricate a certificate without a signed, verified test report.
        """
        raise GACertificationUnavailableError(
            "GA certification is unavailable: no verified phase test report or signing key is "
            "configured. A test count alone cannot certify a release."
        )


__all__ = [
    "GACertificationUnavailableError",
    "StudioGACertifier",
    "StudioGAReleaseCertificate",
]
