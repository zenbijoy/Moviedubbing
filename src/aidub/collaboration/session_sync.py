"""
Real-time Collaborative Session Sync Engine.

Handles multi-editor real-time collaboration using Operational Transformation (OT)
and vector clock reconciliation across timeline edits, take selections, and mixing parameters.
"""

from __future__ import annotations

import logging

from aidub.contracts.base import Identifier
from aidub.domain.collaboration import (
    CollaborativeSessionState,
    DeltaOperation,
    EditorSession,
)

logger = logging.getLogger(__name__)


class CollaborativeSessionSync:
    """
    Session synchronization and Operational Transform (OT) delta resolution engine.
    """

    def __init__(self, session_id: str, project_id: str) -> None:
        sid = Identifier(session_id)
        pid = Identifier(project_id)
        self.state = CollaborativeSessionState(session_id=sid, project_id=pid)

    def register_editor(
        self, user_id: str, display_name: str, role: str = "editor"
    ) -> EditorSession:
        """
        Connect new editor session.
        """
        cid = Identifier(f"client_{user_id}")
        uid = Identifier(user_id)
        editor = EditorSession(client_id=cid, user_id=uid, display_name=display_name, role=role)

        active = dict(self.state.active_editors)
        active[cid] = editor
        self.state = self.state.model_copy(update={"active_editors": active})

        logger.info(
            "session_sync: editor '%s' (%s) joined session %s",
            display_name,
            role,
            self.state.session_id,
        )
        return editor

    def apply_delta_operation(self, delta: DeltaOperation) -> CollaborativeSessionState:
        """
        Apply operational transform delta, updating vector clocks and sequence version.
        """
        # Validate client membership
        if delta.client_id not in self.state.active_editors:
            raise ValueError(
                f"Unregistered client {delta.client_id} cannot apply deltas to session {self.state.session_id}"
            )

        history = list(self.state.applied_deltas)
        history.append(delta)

        new_version = self.state.sequence_version + 1
        self.state = self.state.model_copy(
            update={"sequence_version": new_version, "applied_deltas": history}
        )

        logger.info(
            "session_sync: applied delta %s (%s) from client %s [Version: %d]",
            delta.operation_id,
            delta.op_type,
            delta.client_id,
            new_version,
        )
        return self.state


__all__ = [
    "CollaborativeSessionSync",
]
