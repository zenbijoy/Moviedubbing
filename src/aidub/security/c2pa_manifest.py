"""
C2PA Content Credentials Manifest Builder.

Generates cryptographically signed C2PA JUMBF metadata manifests embedded into exported MP4/MOV files.
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class C2PAManifestUnavailableError(RuntimeError):
    """Raised when no standards-compliant C2PA signing backend is configured."""


class C2PAManifest(ContractModel):
    """C2PA Content Credentials manifest representation."""

    manifest_id: Identifier
    claim_generator: str = Field(min_length=1)
    ai_actions_performed: list[str]
    digital_signature_sha256: str = Field(min_length=64, max_length=64)


class C2PAManifestBuilder:
    """
    Constructs C2PA JUMBF manifests.
    """

    def build_c2pa_manifest(self, project_id: str) -> C2PAManifest:
        """
        Refuse to create a signed-manifest claim without a standards-compliant signing backend.
        """
        del project_id
        raise C2PAManifestUnavailableError(
            "C2PA manifest generation is unavailable: no C2PA/JUMBF writer and signing "
            "credential are configured. No signed credential was created."
        )


__all__ = [
    "C2PAManifest",
    "C2PAManifestBuilder",
    "C2PAManifestUnavailableError",
]
