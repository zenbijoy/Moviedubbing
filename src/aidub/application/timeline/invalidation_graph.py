"""
Fine-Grained Timeline Artifact Invalidation Graph.

Prevents redundant multi-minute AI rerenders:
  - Maps directed dependency stages for every cue/line in the movie.
  - Cascades invalidation ONLY to affected downstream artifacts.
  - Leaves unaffected scenes, character stems, and upstream transcripts untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aidub.domain.edit_ops import EditCommandType

logger = logging.getLogger(__name__)


class PipelineStage(StrEnum):
    """Sequential processing and artifact stages for a dialogue cue."""

    TRANSCRIPT = "transcript"
    TRANSLATION = "translation"
    TTS_BASE_AUDIO = "tts_base_audio"
    RVC_CLONE_AUDIO = "rvc_clone_audio"
    TIMED_AUDIO = "timed_audio"
    PROCESSED_AUDIO = "processed_audio"
    LIPSYNC_VIDEO = "lipsync_video"
    FINAL_MIX = "final_mix"


# Downstream dependency ordering: earlier stages invalidate later stages
STAGE_DEPENDENCY_ORDER: list[PipelineStage] = [
    PipelineStage.TRANSCRIPT,
    PipelineStage.TRANSLATION,
    PipelineStage.TTS_BASE_AUDIO,
    PipelineStage.RVC_CLONE_AUDIO,
    PipelineStage.TIMED_AUDIO,
    PipelineStage.PROCESSED_AUDIO,
    PipelineStage.LIPSYNC_VIDEO,
    PipelineStage.FINAL_MIX,
]

# Map edit types to the root stage they directly invalidate
EDIT_TYPE_TO_ROOT_STAGE: dict[EditCommandType, PipelineStage] = {
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
    """Artifact cache status for a single cue across pipeline stages."""

    cue_id: str
    stage_artifacts: dict[PipelineStage, str] = field(default_factory=dict)
    invalidated_stages: set[PipelineStage] = field(default_factory=set)

    def set_artifact(self, stage: PipelineStage, artifact_path: str) -> None:
        self.stage_artifacts[stage] = artifact_path
        self.invalidated_stages.discard(stage)

    def is_stage_valid(self, stage: PipelineStage) -> bool:
        return stage in self.stage_artifacts and stage not in self.invalidated_stages


class InvalidationGraph:
    """
    Manages dependency graphs and tracks cached vs invalidated artifacts across cues.
    """

    def __init__(self) -> None:
        self._cues: dict[str, CueArtifactRecord] = {}

    def register_cue(self, cue_id: str) -> CueArtifactRecord:
        if cue_id not in self._cues:
            self._cues[cue_id] = CueArtifactRecord(cue_id=cue_id)
        return self._cues[cue_id]

    def get_cue(self, cue_id: str) -> CueArtifactRecord | None:
        return self._cues.get(cue_id)

    def record_artifact(
        self, cue_id: str, stage: PipelineStage, artifact_path: str
    ) -> None:
        record = self.register_cue(cue_id)
        record.set_artifact(stage, artifact_path)

    def invalidate_for_edit(
        self,
        cue_ids: list[str],
        edit_type: EditCommandType,
        custom_root_stage: PipelineStage | None = None,
    ) -> dict[str, set[PipelineStage]]:
        """
        Invalidates downstream stages for the given cues based on the edit command type.
        Returns a mapping of cue_id -> set of newly invalidated stages.
        """
        root_stage = custom_root_stage or EDIT_TYPE_TO_ROOT_STAGE.get(
            edit_type, PipelineStage.FINAL_MIX
        )
        try:
            root_idx = STAGE_DEPENDENCY_ORDER.index(root_stage)
        except ValueError:
            root_idx = len(STAGE_DEPENDENCY_ORDER) - 1

        downstream_stages = set(STAGE_DEPENDENCY_ORDER[root_idx:])
        invalidated_map: dict[str, set[PipelineStage]] = {}

        for cid in cue_ids:
            record = self.register_cue(cid)
            record.invalidated_stages.update(downstream_stages)
            invalidated_map[cid] = set(downstream_stages)

        logger.info(
            "InvalidationGraph: Edit %s on cues %s invalidated stages: %s",
            edit_type.value,
            cue_ids,
            [s.value for s in downstream_stages],
        )
        return invalidated_map

    def get_stages_requiring_rerender(self, cue_id: str) -> list[PipelineStage]:
        """Returns in dependency order all stages for cue_id that must be regenerated."""
        record = self.get_cue(cue_id)
        if not record:
            return list(STAGE_DEPENDENCY_ORDER)
        return [
            s
            for s in STAGE_DEPENDENCY_ORDER
            if s in record.invalidated_stages or s not in record.stage_artifacts
        ]

    def get_all_invalidated_cues(self) -> dict[str, set[PipelineStage]]:
        """Returns all cues currently possessing invalid stages."""
        return {
            cid: set(rec.invalidated_stages)
            for cid, rec in self._cues.items()
            if rec.invalidated_stages
        }

    def clear_all_invalidations(self) -> None:
        """Resets invalidation flags (e.g. after a full project render)."""
        for rec in self._cues.values():
            rec.invalidated_stages.clear()


__all__ = [
    "EDIT_TYPE_TO_ROOT_STAGE",
    "CueArtifactRecord",
    "InvalidationGraph",
    "PipelineStage",
    "STAGE_DEPENDENCY_ORDER",
]
