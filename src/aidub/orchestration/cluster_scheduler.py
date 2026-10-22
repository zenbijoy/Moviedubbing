"""
Distributed Multi-GPU Cluster Scheduler.

Schedules AI jobs across LAN/WAN multi-GPU worker nodes with dynamic load-balancing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class ClusterWorkerNode(ContractModel):
    """Cluster worker node container."""

    node_id: Identifier
    hostname: str = Field(min_length=1)
    available_vram_gb: float = Field(ge=0.0)
    gpu_model: str = Field(default="NVIDIA RTX 4090", max_length=64)
    active_jobs: int = Field(default=0, ge=0)


class DistributedClusterScheduler:
    """
    Schedules AI jobs across cluster worker nodes.
    """

    def select_best_worker_node(
        self, nodes: Sequence[ClusterWorkerNode], required_vram_gb: float = 8.0
    ) -> ClusterWorkerNode | None:
        """
        Select cluster worker node with highest available VRAM.
        """
        eligible = [n for n in nodes if n.available_vram_gb >= required_vram_gb]
        if not eligible:
            logger.warning(
                "cluster_scheduler: no eligible worker node with >= %.1f GB VRAM", required_vram_gb
            )
            return None

        eligible.sort(key=lambda n: n.available_vram_gb, reverse=True)
        selected = eligible[0]
        logger.info(
            "cluster_scheduler: assigned job to node %s (%s)", selected.node_id, selected.hostname
        )
        return selected


__all__ = [
    "ClusterWorkerNode",
    "DistributedClusterScheduler",
]
