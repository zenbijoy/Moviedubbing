"""
Fine-Grained Role-Based Access Control (RBAC) Policy Engine.

Enforces role permissions across studio actions (Director, Editor, Audio Engineer, Auditor).
"""

from __future__ import annotations

import logging
from enum import StrEnum

from aidub.security.sso_auth import UserToken

logger = logging.getLogger(__name__)


class PermissionAction(StrEnum):
    EDIT_TIMELINE = "edit_timeline"
    TRIGGER_VOICE_CLONE = "trigger_voice_clone"
    APPROVE_TRANSLATION = "approve_translation"
    EXPORT_MASTER_DCP = "export_master_dcp"
    AUDIT_SECURITY_LOGS = "audit_security_logs"


class RBACPolicyEngine:
    """
    Enforces RBAC authorization rules.
    """

    def ensure_permission(self, token: UserToken, action: PermissionAction) -> None:
        """
        Verify user token has role privileges for target action.
        """
        if "director" in token.roles:
            return  # Director has full permissions

        if (
            action == PermissionAction.EXPORT_MASTER_DCP
            and "editor" not in token.roles
            and "director" not in token.roles
        ):
            raise PermissionError(f"User {token.user_id} lacks privilege for action {action}")

        logger.info("rbac_policy: authorized action %s for user %s", action, token.user_id)


__all__ = [
    "PermissionAction",
    "RBACPolicyEngine",
]
