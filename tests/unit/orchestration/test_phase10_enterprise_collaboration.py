"""
Unit tests for Phase 10 — Enterprise Studio Orchestration, Real-time Collaborative Session Sync & Multi-Engine Distribution Platform:
  - Multi-Engine Audio-Visual Render Orchestration DAG
  - Real-time Operational Transform (OT) Delta Session Sync
  - Enterprise Master Distribution Exporter (DCP, Broadcast MXF layback, OTT HLS/DASH)
  - Cryptographic Studio Audit Logger & SHA-256 Hash Chain Integrity
  - Collaboration Studio Presentation Controller
"""

from __future__ import annotations

import pytest

from aidub.collaboration.session_sync import CollaborativeSessionSync
from aidub.contracts.base import Identifier
from aidub.domain.collaboration import DeltaOperation, OperationType
from aidub.export.distribution_exporter import DistributionPackageExporter
from aidub.orchestration.render_orchestrator import MultiEngineRenderOrchestrator, RenderNodeStatus
from aidub.security.audit_logger import CryptographicAuditLogger
from aidub.ui.collaboration.controller import CollaborationStudioController


def test_multi_engine_render_orchestrator() -> None:
    orchestrator = MultiEngineRenderOrchestrator()
    plan = orchestrator.create_render_plan("job_test_01")
    assert len(plan.nodes) == 6
    assert plan.overall_progress == 0.0

    executed = orchestrator.execute_render_plan(plan)
    assert executed.overall_progress == 100.0
    assert executed.nodes["node_tts"].status == RenderNodeStatus.COMPLETED
    assert executed.nodes["node_encode"].status == RenderNodeStatus.COMPLETED


def test_collaborative_session_sync_ot() -> None:
    sync = CollaborativeSessionSync("sess_100", "proj_100")
    ed1 = sync.register_editor("user_alice", "Alice Director", role="director")
    ed2 = sync.register_editor("user_bob", "Bob Editor", role="editor")

    assert len(sync.state.active_editors) == 2

    delta1 = DeltaOperation(
        operation_id=Identifier("op_01"),
        op_type=OperationType.SELECT_VOICE_TAKE,
        target_path="timeline.take",
        payload={"take_id": "take_99"},
        client_id=ed1.client_id,
        vector_clock=1,
    )
    state = sync.apply_delta_operation(delta1)
    assert state.sequence_version == 1
    assert len(state.applied_deltas) == 1

    # Unregistered client attempt
    delta_bad = DeltaOperation(
        operation_id=Identifier("op_bad"),
        op_type=OperationType.UPDATE_SUBTITLE,
        target_path="subtitles",
        client_id=Identifier("unregistered_client"),
        vector_clock=2,
    )
    with pytest.raises(ValueError, match="Unregistered client"):
        sync.apply_delta_operation(delta_bad)


def test_distribution_package_exporter() -> None:
    exporter = DistributionPackageExporter()

    with pytest.raises(RuntimeError, match="AIDUB_DCP_COMMAND is not configured"):
        exporter.export_dcp_manifest("proj_01", "Hero Movie", ["en-US", "bn-BD"])
    with pytest.raises(RuntimeError, match="AIDUB_MXF_COMMAND is not configured"):
        exporter.export_broadcast_layback("proj_01", "7.1_Surround")
    with pytest.raises(RuntimeError, match="AIDUB_OTT_COMMAND is not configured"):
        exporter.export_ott_streaming_package("proj_01", ["en-US", "bn-BD", "es-ES"])


def test_cryptographic_audit_logger_hash_chain() -> None:
    logger_inst = CryptographicAuditLogger()
    e1 = logger_inst.log_event("evt_1", "CONSENT_CHECK", "user_01", "Consent checked for profile_1")
    e2 = logger_inst.log_event("evt_2", "VOICE_CLONE", "user_01", "Generated clone take_1")
    e3 = logger_inst.log_event("evt_3", "EXPORT_DCP", "user_01", "Exported DCP package")

    assert e1.previous_hash == "0" * 64
    assert e2.previous_hash == e1.current_hash
    assert e3.previous_hash == e2.current_hash
    assert logger_inst.verify_chain_integrity() is True

    # Test tampering detection
    tampered_chain = list(logger_inst.chain)
    tampered_chain[1] = tampered_chain[1].model_copy(update={"details": "TAMPERED DATA"})
    logger_inst.chain = tampered_chain
    assert logger_inst.verify_chain_integrity() is False


def test_collaboration_studio_controller() -> None:
    ctrl = CollaborationStudioController("sess_ui", "proj_ui")
    cid = ctrl.register_editor_session("u1", "Editor User")
    assert "client_u1" in cid

    plan = ctrl.trigger_render_orchestration("job_ui")
    assert plan.overall_progress == 100.0

    with pytest.raises(RuntimeError, match="AIDUB_DCP_COMMAND is not configured"):
        ctrl.export_distribution_package("proj_ui", "DCP")
    with pytest.raises(RuntimeError, match="AIDUB_MXF_COMMAND is not configured"):
        ctrl.export_distribution_package("proj_ui", "MXF")
    with pytest.raises(RuntimeError, match="AIDUB_OTT_COMMAND is not configured"):
        ctrl.export_distribution_package("proj_ui", "OTT")

    assert ctrl.verify_audit_log_integrity() is True
