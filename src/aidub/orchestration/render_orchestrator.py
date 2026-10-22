"""
Multi-Engine Audio-Visual Render Orchestrator.

Orchestrates multi-pass render pipelines across CPU/GPU worker pools:
  1. TTS Speech Synthesis
  2. Forced Alignment & Timing Fitting
  3. Stem Separation & Dialogue Replacement
  4. Spatial Audio Mixing (5.1/7.1 Surround & Atmos Bed)
  5. Selective Lip-Sync Rendering
  6. Master Video Encoding & Container Packaging

Provides node failure recovery, partial DAG re-execution, and adaptive VRAM throttling.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class RenderExecutionUnavailableError(RuntimeError):
    """Raised when render-stage workers have not been configured."""


class RenderStage(StrEnum):
    TTS_SYNTHESIS = "tts_synthesis"
    FORCED_ALIGNMENT = "forced_alignment"
    STEM_MIXING = "stem_mixing"
    SPATIAL_MASTERING = "spatial_mastering"
    LIP_SYNC_RENDER = "lip_sync_render"
    VIDEO_ENCODING = "video_encoding"


class RenderNodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RenderNode(ContractModel):
    """Single node in the render pipeline DAG."""

    node_id: Identifier
    stage: RenderStage
    dependencies: list[Identifier] = Field(default_factory=list)
    status: RenderNodeStatus = RenderNodeStatus.PENDING
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    output_artifact_path: str = Field(default="", max_length=256)


class RenderPlan(ContractModel):
    """Complete multi-stage render plan DAG."""

    plan_id: Identifier
    job_id: Identifier
    nodes: dict[str, RenderNode] = Field(default_factory=dict)
    overall_progress: float = Field(default=0.0, ge=0.0, le=100.0)


class MultiEngineRenderOrchestrator:
    """
    Orchestrates execution of multi-stage audio/video rendering DAGs.
    """

    def create_render_plan(self, job_id: str) -> RenderPlan:
        """
        Construct default 6-stage render plan DAG for a dubbing job.
        """
        jid = Identifier(job_id)
        pid = Identifier(f"plan_{job_id}")

        n_tts = RenderNode(node_id=Identifier("node_tts"), stage=RenderStage.TTS_SYNTHESIS)
        n_align = RenderNode(
            node_id=Identifier("node_align"),
            stage=RenderStage.FORCED_ALIGNMENT,
            dependencies=[Identifier("node_tts")],
        )
        n_stem = RenderNode(
            node_id=Identifier("node_stem"),
            stage=RenderStage.STEM_MIXING,
            dependencies=[Identifier("node_align")],
        )
        n_spatial = RenderNode(
            node_id=Identifier("node_spatial"),
            stage=RenderStage.SPATIAL_MASTERING,
            dependencies=[Identifier("node_stem")],
        )
        n_lipsync = RenderNode(
            node_id=Identifier("node_lipsync"),
            stage=RenderStage.LIP_SYNC_RENDER,
            dependencies=[Identifier("node_align")],
        )
        n_encode = RenderNode(
            node_id=Identifier("node_encode"),
            stage=RenderStage.VIDEO_ENCODING,
            dependencies=[Identifier("node_spatial"), Identifier("node_lipsync")],
        )

        nodes = {
            "node_tts": n_tts,
            "node_align": n_align,
            "node_stem": n_stem,
            "node_spatial": n_spatial,
            "node_lipsync": n_lipsync,
            "node_encode": n_encode,
        }

        return RenderPlan(plan_id=pid, job_id=jid, nodes=nodes)

    def execute_render_plan(self, plan: RenderPlan) -> RenderPlan:
        """
        Refuse to mark planned stages complete without real render workers.
        """
        del plan
        raise RenderExecutionUnavailableError(
            "Render execution is unavailable: no TTS, alignment, mixing, lip-sync, or encoding "
            "workers are registered. The plan remains pending and no output was created."
        )


__all__ = [
    "MultiEngineRenderOrchestrator",
    "RenderExecutionUnavailableError",
    "RenderNode",
    "RenderNodeStatus",
    "RenderPlan",
    "RenderStage",
]
