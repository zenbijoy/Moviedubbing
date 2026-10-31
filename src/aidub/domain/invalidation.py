"""
Domain contracts for Artifact Invalidation and Dependency Tracking.

Defines:
  - ArtifactDependency: Directional dependency between upstream and downstream pipeline stages.
  - InvalidationRule: Rule determining stage cascade when a timeline property is edited.
  - InvalidationGraph: Stage-level dependency and cache tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aidub.domain.edit_ops import EditCommandType


class PipelineStage(StrEnum):
    """Core artifact generation and transformation stages."""

    TRANSCRIPT = "transcript"
    TRANSLATION = "translation"
    TTS_BASE_AUDIO = "tts_base_audio"
    RVC_CLONE_AUDIO = "rvc_clone_audio"
    TIMED_AUDIO = "timed_audio"
    PROCESSED_AUDIO = "processed_audio"
    LIPSYNC_VIDEO = "lipsync_video"
    FINAL_MIX = "final_mix"


# Strictly ordered topological pipeline stages
STAGE_ORDER: list[PipelineStage] = [
    PipelineStage.TRANSCRIPT,
    PipelineStage.TRANSLATION,
    PipelineStage.TTS_BASE_AUDIO,
    PipelineStage.RVC_CLONE_AUDIO,
    PipelineStage.TIMED_AUDIO,
    PipelineStage.PROCESSED_AUDIO,
    PipelineStage.LIPSYNC_VIDEO,
    PipelineStage.FINAL_MIX,
]


@dataclass(frozen=True)
class ArtifactDependency:
    """Represents a direct causal edge between an upstream and downstream stage."""

    upstream_stage: PipelineStage
    downstream_stage: PipelineStage
    reason: str = ""


# Default causal DAG edges
DEFAULT_DEPENDENCY_EDGES: list[ArtifactDependency] = [
    ArtifactDependency(PipelineStage.TRANSCRIPT, PipelineStage.TRANSLATION, "Source text required for translation"),
    ArtifactDependency(PipelineStage.TRANSLATION, PipelineStage.TTS_BASE_AUDIO, "Translated text required for synthesis"),
    ArtifactDependency(PipelineStage.TTS_BASE_AUDIO, PipelineStage.RVC_CLONE_AUDIO, "Base acoustic voice required for RVC conversion"),
    ArtifactDependency(PipelineStage.RVC_CLONE_AUDIO, PipelineStage.TIMED_AUDIO, "Cloned speech required for WSOLA duration budgeting"),
    ArtifactDependency(PipelineStage.TIMED_AUDIO, PipelineStage.PROCESSED_AUDIO, "Timed speech required for EQ/dynamics DSP"),
    ArtifactDependency(PipelineStage.PROCESSED_AUDIO, PipelineStage.LIPSYNC_VIDEO, "Clean master dialogue required for viseme/face sync"),
    ArtifactDependency(PipelineStage.PROCESSED_AUDIO, PipelineStage.FINAL_MIX, "Master dialogue required for EBU R128 ducked mixdown"),
]


# Direct entry stage for each edit operation
EDIT_COMMAND_STAGE_MAP: dict[EditCommandType, PipelineStage] = {
    EditCommandType.TEXT_EDIT: PipelineStage.TRANSLATION,
    EditCommandType.EMOTION_TWEAK: PipelineStage.TTS_BASE_AUDIO,
    EditCommandType.VOICE_RECAST: PipelineStage.TTS_BASE_AUDIO,
    EditCommandType.TIMING_SHIFT: PipelineStage.TIMED_AUDIO,
    EditCommandType.DSP_PARAM_CHANGE: PipelineStage.PROCESSED_AUDIO,
    EditCommandType.VISEME_OVERRIDE: PipelineStage.LIPSYNC_VIDEO,
    EditCommandType.TAKE_SELECT: PipelineStage.PROCESSED_AUDIO,
    EditCommandType.BLADE_SPLIT: PipelineStage.TIMED_AUDIO,
    EditCommandType.RIPPLE_DELETE: PipelineStage.FINAL_MIX,
    EditCommandType.MARKER_MUTATION: PipelineStage.FINAL_MIX,
    EditCommandType.CUSTOM: PipelineStage.FINAL_MIX,
}


@dataclass
class CueArtifactRecord:
    """Tracks artifact references and invalidation state for an individual cue."""

    cue_id: str
    stage_artifacts: dict[PipelineStage, str] = field(default_factory=dict)
    invalidated_stages: set[PipelineStage] = field(default_factory=set)

    def set_artifact(self, stage: PipelineStage, artifact_uri: str) -> None:
        self.stage_artifacts[stage] = artifact_uri
        self.invalidated_stages.discard(stage)

    def is_valid(self, stage: PipelineStage) -> bool:
        return stage in self.stage_artifacts and stage not in self.invalidated_stages


class InvalidationGraph:
    """
    Project-level dependency graph computing exact invalidation cascades.
    """

    def __init__(self) -> None:
        self._cues: dict[str, CueArtifactRecord] = {}

    def get_or_create_cue(self, cue_id: str) -> CueArtifactRecord:
        if cue_id not in self._cues:
            self._cues[cue_id] = CueArtifactRecord(cue_id=cue_id)
        return self._cues[cue_id]

    def register_artifact(self, cue_id: str, stage: PipelineStage, uri: str) -> None:
        rec = self.get_or_create_cue(cue_id)
        rec.set_artifact(stage, uri)

    def compute_downstream_stages(self, root_stage: PipelineStage) -> list[PipelineStage]:
        """Returns root_stage and all downstream stages in topological order."""
        try:
            idx = STAGE_ORDER.index(root_stage)
            return STAGE_ORDER[idx:]
        except ValueError:
            return [root_stage]

    def invalidate_cues(
        self,
        cue_ids: list[str],
        command_type: EditCommandType,
        explicit_stage: PipelineStage | None = None,
    ) -> dict[str, set[PipelineStage]]:
        """
        Invalidates only the strictly necessary downstream pipeline stages.
        """
        root_stage = explicit_stage or EDIT_COMMAND_STAGE_MAP.get(
            command_type, PipelineStage.FINAL_MIX
        )
        downstream = set(self.compute_downstream_stages(root_stage))
        result: dict[str, set[PipelineStage]] = {}

        for cid in cue_ids:
            rec = self.get_or_create_cue(cid)
            rec.invalidated_stages.update(downstream)
            result[cid] = set(downstream)

        return result

    def get_rerender_queue(self, cue_id: str) -> list[PipelineStage]:
        """Returns the ordered list of stages that need rerendering for cue_id."""
        rec = self.get_or_create_cue(cue_id)
        return [
            s for s in STAGE_ORDER
            if s in rec.invalidated_stages or s not in rec.stage_artifacts
        ]


__all__ = [
    "ArtifactDependency",
    "CueArtifactRecord",
    "DEFAULT_DEPENDENCY_EDGES",
    "EDIT_COMMAND_STAGE_MAP",
    "InvalidationGraph",
    "PipelineStage",
    "STAGE_ORDER",
]
