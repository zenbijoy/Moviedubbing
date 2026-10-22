"""Fail-closed visual lip-sync QC score classification."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class VisualQCScore(ContractModel):
    """Classification of a measured visual sync score supplied by a real evaluator."""

    shot_id: Identifier
    sync_confidence: float = Field(ge=0.0, le=1.0)
    seam_artifact_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fallback_to_original_required: bool
    passed: bool
    passed_qc: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    rejection_reason: str = ""
    diagnostic_recommendations: list[str] = Field(default_factory=list)

    @property
    def should_fallback_to_original(self) -> bool:
        return self.fallback_to_original_required


class VisualQCEvaluator(ContractModel):
    """Classify measured lip-sync confidence; this class does not infer video quality."""

    pass_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    def evaluate_shot(self, shot_id: str, sync_conf: float) -> VisualQCScore:
        """Classify a confidence value measured by a separately configured model."""
        sid = Identifier(shot_id)
        fallback = sync_conf < self.pass_threshold
        reason = (
            "Measured lip-sync confidence is below the configured threshold" if fallback else ""
        )
        recommendations = (
            ["Review the generated shot and keep the original video if sync artifacts are visible"]
            if fallback
            else []
        )
        logger.info(
            "visual_qc: classified measured confidence for shot %s (%.2f, passed=%s)",
            sid,
            sync_conf,
            not fallback,
        )
        return VisualQCScore(
            shot_id=sid,
            sync_confidence=sync_conf,
            fallback_to_original_required=fallback,
            passed=not fallback,
            passed_qc=not fallback,
            confidence_score=sync_conf,
            rejection_reason=reason,
            diagnostic_recommendations=recommendations,
        )

    def evaluate_shot_video(
        self,
        shot_id: str,
        video_path: str,
        *,
        measured_sync_confidence: float | None = None,
        measured_seam_artifact_score: float | None = None,
    ) -> VisualQCScore:
        """Classify supplied model measurements and reject unmeasured video input."""
        if not Path(video_path).is_file():
            raise FileNotFoundError(f"lip-sync QC video does not exist: {video_path}")
        if measured_sync_confidence is None:
            raise RuntimeError(
                "No visual lip-sync QC model is configured; no pass score was produced."
            )
        result = self.evaluate_shot(shot_id, measured_sync_confidence)
        if measured_seam_artifact_score is not None:
            result = result.model_copy(update={"seam_artifact_score": measured_seam_artifact_score})
        return result

    def evaluate(self, shot_id: str, sync_conf: float) -> VisualQCScore:
        """Compatibility alias for classifying an explicitly measured score."""
        return self.evaluate_shot(shot_id, sync_conf)


VisualQcEvaluator = VisualQCEvaluator
VisualQcReport = VisualQCScore
VisualQcResult = VisualQCScore


__all__ = [
    "VisualQCEvaluator",
    "VisualQCScore",
    "VisualQcEvaluator",
    "VisualQcReport",
    "VisualQcResult",
]
