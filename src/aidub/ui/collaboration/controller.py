"""
Collaboration Studio Presentation UI Controller.

Binds real-time session sync, multi-engine render orchestration status,
master distribution export triggers, and audit log verification to Qt Quick QML views.
"""

from __future__ import annotations

import logging

from aidub.collaboration.session_sync import CollaborativeSessionSync
from aidub.export.distribution_exporter import DistributionFormat, DistributionPackageExporter
from aidub.orchestration.render_orchestrator import (
    MultiEngineRenderOrchestrator,
    RenderExecutionUnavailableError,
    RenderPlan,
)
from aidub.security.audit_logger import CryptographicAuditLogger

logger = logging.getLogger(__name__)


class CollaborationStudioController:
    """
    Controller binding Phase 10 enterprise features to Qt Quick QML presentation layer.
    """

    def __init__(self, session_id: str = "sess_01", project_id: str = "proj_01") -> None:
        self.session_sync = CollaborativeSessionSync(session_id, project_id)
        self.render_orchestrator = MultiEngineRenderOrchestrator()
        self.distribution_exporter = DistributionPackageExporter()
        self.audit_logger = CryptographicAuditLogger()

    def register_editor_session(self, user_id: str, display_name: str, role: str = "editor") -> str:
        """
        Register new active participant session.
        """
        editor = self.session_sync.register_editor(user_id, display_name, role)
        self.audit_logger.log_event(
            event_id=f"evt_join_{user_id}",
            event_type="SESSION_JOIN",
            actor_id=user_id,
            details=f"Editor '{display_name}' joined session as {role}",
        )
        return editor.client_id

    def trigger_render_orchestration(self, job_id: str) -> RenderPlan:
        """
        Build a plan, then report that the render workers are unavailable.
        """
        plan = self.render_orchestrator.create_render_plan(job_id)
        try:
            return self.render_orchestrator.execute_render_plan(plan)
        except RenderExecutionUnavailableError:
            self.audit_logger.log_event(
                event_id=f"evt_render_{job_id}",
                event_type="RENDER_BLOCKED",
                actor_id="system_orchestrator",
                details="Render plan blocked because no render workers are configured",
            )
            raise

    def export_distribution_package(
        self, project_id: str, format_type: str = "DCP"
    ) -> DistributionFormat:
        """
        Export master studio distribution package.
        """
        if format_type.upper() == "DCP":
            dist = self.distribution_exporter.export_dcp_manifest(
                project_id, "Movie Title", ["en-US", "bn-BD"]
            )
        elif format_type.upper() in ["MXF", "BROADCAST"]:
            dist = self.distribution_exporter.export_broadcast_layback(project_id, "7.1_Surround")
        else:
            dist = self.distribution_exporter.export_ott_streaming_package(
                project_id, ["en-US", "bn-BD", "es-ES"]
            )

        self.audit_logger.log_event(
            event_id=f"evt_export_{project_id}",
            event_type="EXPORT_PACKAGE",
            actor_id="system_exporter",
            details=f"Exported {dist.format_type} package to {dist.manifest_file_path}",
        )
        return dist

    def verify_audit_log_integrity(self) -> bool:
        """
        Verify audit log tamper-evident integrity chain.
        """
        return self.audit_logger.verify_chain_integrity()


__all__ = [
    "CollaborationStudioController",
]
