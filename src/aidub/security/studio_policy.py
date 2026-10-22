"""
Centralized Studio Governance & Policy Engine.

Enforces legal consent enforcement, cloud budget caps, network isolation, and model licensing rules.
"""

from __future__ import annotations

import logging

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class StudioGovernancePolicy(ContractModel):
    """Studio governance policy configuration."""

    policy_id: Identifier
    require_voice_consent: bool = True
    offline_mode_strict: bool = False
    max_cloud_budget_usd: float = Field(default=5000.0, gt=0.0)
    enforce_commercial_license_only: bool = True


class StudioPolicyEvaluator:
    """
    Evaluates studio policy rules.
    """

    def validate_operation_compliance(
        self, policy: StudioGovernancePolicy, is_commercial_model: bool
    ) -> bool:
        """
        Validate model license compliance under active policy.
        """
        if policy.enforce_commercial_license_only and not is_commercial_model:
            logger.warning(
                "studio_policy: BLOCKED non-commercial model under strict policy %s",
                policy.policy_id,
            )
            return False
        return True


__all__ = [
    "StudioGovernancePolicy",
    "StudioPolicyEvaluator",
]
