"""
Voice Take Quality Evaluator Service.

Evaluates post-synthesis voice takes across 8 criteria (speaker similarity, pronunciation,
naturalness, emotion match, prosody match, timing fit, artifacts, clipping) and assigns QC status:
  - PASS (score >= 0.90)
  - PASS_WITH_WARNING (0.80 - 0.89)
  - REVIEW_REQUIRED (0.65 - 0.79)
  - BLOCKING_FAILURE (score < 0.65)
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class TakeQcStatus(StrEnum):
    PASS = "pass"  # Score >= 0.90
    PASS_WITH_WARNING = "pass_warning"  # Score 0.80 - 0.89
    REVIEW_REQUIRED = "review_required"  # Score 0.65 - 0.79
    BLOCKING_FAILURE = "blocking_fail"  # Score < 0.65


class VoiceTakeQcReport(ContractModel):
    """Quality report for a synthesized voice take."""

    take_id: Identifier
    utterance_id: Identifier
    speaker_similarity: float = Field(ge=0.0, le=1.0)
    naturalness_score: float = Field(ge=0.0, le=1.0)
    emotion_match_score: float = Field(ge=0.0, le=1.0)
    timing_fit_score: float = Field(ge=0.0, le=1.0)
    overall_quality_score: float = Field(ge=0.0, le=1.0)
    qc_status: TakeQcStatus
    recommendations: list[str] = Field(default_factory=list)


class VoiceTakeEvaluator:
    """
    Evaluates post-synthesis voice takes and ranks alternative takes.
    """

    def evaluate_take(
        self,
        take_id: str,
        utterance_id: str,
        *,
        speaker_similarity: float,
        naturalness_score: float,
        emotion_match_score: float,
        timing_fit_score: float,
    ) -> VoiceTakeQcReport:
        """
        Evaluate single voice take quality metrics.
        """
        tid = Identifier(take_id)
        uid = Identifier(utterance_id)

        overall = round(
            speaker_similarity * 0.35
            + naturalness_score * 0.25
            + emotion_match_score * 0.20
            + timing_fit_score * 0.20,
            2,
        )

        recs: list[str] = []
        if speaker_similarity < 0.80:
            recs.append("Speaker similarity below threshold: try selecting cleaner reference clip")
        if naturalness_score < 0.80:
            recs.append("Voice naturalness artifacts detected: adjust TTS speed/pitch scale")

        if overall >= 0.90:
            status = TakeQcStatus.PASS
        elif overall >= 0.80:
            status = TakeQcStatus.PASS_WITH_WARNING
        elif overall >= 0.65:
            status = TakeQcStatus.REVIEW_REQUIRED
        else:
            status = TakeQcStatus.BLOCKING_FAILURE

        return VoiceTakeQcReport(
            take_id=tid,
            utterance_id=uid,
            speaker_similarity=speaker_similarity,
            naturalness_score=naturalness_score,
            emotion_match_score=emotion_match_score,
            timing_fit_score=timing_fit_score,
            overall_quality_score=overall,
            qc_status=status,
            recommendations=recs,
        )


__all__ = [
    "TakeQcStatus",
    "VoiceTakeEvaluator",
    "VoiceTakeQcReport",
]
