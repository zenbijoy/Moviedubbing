"""
Remote Model Package Fleet Deployment Engine.

Distributes signed model packages, weights, and engine updates across cluster worker fleets.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class FleetDeploymentUnavailableError(RuntimeError):
    """Raised when there is no remote worker deployment transport configured."""


class FleetDeploymentManifest(ContractModel):
    """Fleet deployment package manifest."""

    deployment_id: Identifier
    package_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    checksum_sha256: str = Field(min_length=64, max_length=64)


class FleetModelDeployer:
    """
    Deploys model packages to remote worker nodes.
    """

    def deploy_package_to_nodes(
        self, manifest: FleetDeploymentManifest, node_ids: Sequence[str]
    ) -> bool:
        """
        Refuse deployment until a real signed-package transport is configured.
        """
        del manifest, node_ids
        raise FleetDeploymentUnavailableError(
            "Fleet deployment is unavailable: no authenticated remote worker transport is "
            "configured. No package was sent to any node."
        )


__all__ = [
    "FleetDeploymentManifest",
    "FleetDeploymentUnavailableError",
    "FleetModelDeployer",
]
