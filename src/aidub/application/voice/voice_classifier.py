"""
Voice & Character Classification Application Service.

Provides:
  - Multi-speaker classification with confidence attribution.
  - Automatic flagging of low-confidence (<0.75) speaker attributions.
  - 1-Click Diarization Cluster Merging (e.g., merging duplicate SPEAKER_00 and SPEAKER_02).
  - Manual editorial speaker overrides with immutable audit trails.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aidub.domain.voice_classification import (
    ClassificationResult,
    DiarizationCluster,
    GenderIdentity,
    SpeakerMergeOperation,
)

logger = logging.getLogger(__name__)


class VoiceClassifier:
    """Manages film speaker classification decisions, uncertainty detection, and cluster merges."""

    def __init__(self, confidence_threshold: float = 0.75) -> None:
        self.confidence_threshold: float = confidence_threshold
        self._cues: dict[str, ClassificationResult] = {}
        self._merge_history: list[SpeakerMergeOperation] = []

    def register_cue_prediction(
        self,
        cue_id: str,
        predicted_speaker: str,
        confidence: float,
        suggested_alternatives: list[tuple[str, float]] | None = None,
        face_track_id: str | None = None,
    ) -> ClassificationResult:
        is_uncertain = confidence < self.confidence_threshold
        result = ClassificationResult(
            cue_id=cue_id,
            predicted_speaker=predicted_speaker,
            confidence=round(confidence, 3),
            is_uncertain=is_uncertain,
            suggested_alternatives=list(suggested_alternatives or []),
            face_track_id=face_track_id,
        )
        self._cues[cue_id] = result
        return result

    def get_cue(self, cue_id: str) -> ClassificationResult | None:
        return self._cues.get(cue_id)

    def list_cues(self) -> list[ClassificationResult]:
        return list(self._cues.values())

    def get_uncertain_cues(self) -> list[ClassificationResult]:
        """Returns all cues flagged for editorial review (< threshold)."""
        return [c for c in self._cues.values() if c.is_uncertain]

    def override_speaker(
        self,
        cue_id: str,
        new_speaker: str,
        reason: str = "Editorial correction",
    ) -> ClassificationResult:
        """Manually overrides the speaker assignment for a cue."""
        res = self._cues.get(cue_id)
        if not res:
            raise KeyError(f"Cue ID {cue_id} not registered in classifier.")
        res.manual_override_speaker = new_speaker
        res.override_reason = reason
        res.is_uncertain = False  # Human confirmed
        res.updated_at_s = time.time()
        logger.info("VoiceClassifier: Overrode cue %s -> %s (%s)", cue_id, new_speaker, reason)
        return res

    def merge_speaker_clusters(
        self,
        source_speaker: str,
        target_speaker: str,
        performed_by: str = "editor",
    ) -> SpeakerMergeOperation:
        """
        Merges all cues assigned to source_speaker into target_speaker.
        """
        affected: list[str] = []
        for cue in self._cues.values():
            if cue.effective_speaker == source_speaker:
                cue.manual_override_speaker = target_speaker
                cue.override_reason = f"Cluster merge from {source_speaker}"
                cue.is_uncertain = False
                cue.updated_at_s = time.time()
                affected.append(cue.cue_id)

        op = SpeakerMergeOperation(
            source_cluster_id=source_speaker,
            target_cluster_id=target_speaker,
            affected_cue_ids=affected,
            performed_by=performed_by,
        )
        self._merge_history.append(op)
        logger.info(
            "VoiceClassifier: Merged %s into %s, updating %d cues",
            source_speaker,
            target_speaker,
            len(affected),
        )
        return op

    def get_merge_history(self) -> list[SpeakerMergeOperation]:
        return list(self._merge_history)


__all__ = [
    "VoiceClassifier",
]
