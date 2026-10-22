"""
Multi-Dimensional AI Quality Control (QC) Evaluator & Timeline Heatmap Engine.

Evaluates dubbed movie project assets across 8 distinct quality dimensions:
  1. Transcription Accuracy Score
  2. Diarization Boundary Precision Score
  3. Translation Semantic Meaning Preservation Score
  4. Speech Timing Fit & Alignment Score
  5. Voice Engine Quality (MOS) Score
  6. Visual Lip-Sync Quality Score
  7. Audio Loudness (LUFS) & Clipping Headroom Score
  8. Subtitle Reading Speed (Characters-Per-Second CPS) Score
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class StudioQcPreset(StrEnum):
    BROADCAST_STUDIO = "broadcast_studio"  # Strict EBU R128 (-24 LUFS), high lip-sync threshold
    STREAMING_OTT = "streaming_ott"  # Balanced (-14 to -24 LUFS), subtitle CPS focus
    SOCIAL_MEDIA = "social_media"  # Fast-paced, burn-in subtitle focus


class QcSeverityLevel(StrEnum):
    PASS_GREEN = "pass_green"  # Meets studio standards (> 0.85)
    WARNING_AMBER = "warning_amber"  # Minor defect requiring review (0.70 - 0.85)
    BLOCKING_RED = "blocking_red"  # Major defect failing QC threshold (< 0.70)


class QcDimensionScore(ContractModel):
    """Quality evaluation score for a specific metric dimension."""

    dimension_name: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    severity: QcSeverityLevel = QcSeverityLevel.PASS_GREEN
    detail: str = Field(default="", max_length=256)


class AutoRepairAction(ContractModel):
    """Actionable automated fix trigger for a detected QC defect."""

    action_id: Identifier
    action_type: str = Field(
        min_length=1
    )  # "normalize_loudness", "wsola_timestretch", "condense_translation", "force_lipsync_cinema"
    description: str = Field(min_length=1)
    target_utterance_id: Identifier
    parameters: dict[str, str | float | int] = Field(default_factory=dict)


class UtteranceQcReport(ContractModel):
    """Quality control evaluation report for a single dialogue utterance segment."""

    utterance_id: Identifier
    overall_score: float = Field(ge=0.0, le=1.0)
    severity: QcSeverityLevel = QcSeverityLevel.PASS_GREEN
    dimension_scores: dict[str, QcDimensionScore] = Field(default_factory=dict)
    actionable_recommendations: list[str] = Field(default_factory=list)
    auto_repair_actions: list[AutoRepairAction] = Field(default_factory=list)


class TimelineQualityHeatmap(ContractModel):
    """Full timeline quality heatmap map indexing QC health across project duration."""

    project_id: Identifier
    total_utterances: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    overall_project_quality: float = Field(ge=0.0, le=1.0)
    preset_used: StudioQcPreset = StudioQcPreset.BROADCAST_STUDIO
    reports: list[UtteranceQcReport] = Field(default_factory=list)


class MultiDimensionalQCEvaluator:
    """
    Enterprise multi-dimensional AI quality evaluator engine.
    """

    PRESET_WEIGHTS: ClassVar[dict[StudioQcPreset, dict[str, float]]] = {
        StudioQcPreset.BROADCAST_STUDIO: {
            "transcription": 0.10,
            "diarization": 0.10,
            "translation": 0.15,
            "timing": 0.15,
            "voice_quality": 0.15,
            "lipsync": 0.15,
            "loudness": 0.10,
            "subtitle_speed": 0.10,
        },
        StudioQcPreset.STREAMING_OTT: {
            "transcription": 0.10,
            "diarization": 0.05,
            "translation": 0.20,
            "timing": 0.15,
            "voice_quality": 0.15,
            "lipsync": 0.10,
            "loudness": 0.10,
            "subtitle_speed": 0.15,
        },
        StudioQcPreset.SOCIAL_MEDIA: {
            "transcription": 0.05,
            "diarization": 0.05,
            "translation": 0.20,
            "timing": 0.20,
            "voice_quality": 0.10,
            "lipsync": 0.05,
            "loudness": 0.10,
            "subtitle_speed": 0.25,
        },
    }

    def __init__(
        self,
        preset: StudioQcPreset = StudioQcPreset.BROADCAST_STUDIO,
        warning_threshold: float = 0.85,
        blocking_threshold: float = 0.70,
        target_loudness_lufs: float = -24.0,
        max_cps: float = 20.0,
    ) -> None:
        self.preset = preset
        self.warning_threshold = warning_threshold
        self.blocking_threshold = blocking_threshold
        self.target_loudness_lufs = target_loudness_lufs
        self.max_cps = max_cps

    def _determine_severity(self, score: float) -> QcSeverityLevel:
        if score >= self.warning_threshold:
            return QcSeverityLevel.PASS_GREEN
        if score >= self.blocking_threshold:
            return QcSeverityLevel.WARNING_AMBER
        return QcSeverityLevel.BLOCKING_RED

    def evaluate_utterance(
        self,
        utterance_id: str,
        transcription_acc: float,
        diarization_prec: float,
        translation_meaning: float,
        timing_fit: float,
        voice_quality: float,
        lipsync_score: float,
        integrated_lufs: float,
        subtitle_cps: float,
    ) -> UtteranceQcReport:
        """
        Evaluate single utterance quality across 8 dimensions.
        """
        uid = Identifier(utterance_id)

        # Loudness score calculation
        loudness_diff = abs(integrated_lufs - self.target_loudness_lufs)
        loudness_score = max(0.0, min(1.0, 1.0 - (loudness_diff / 10.0)))

        # Subtitle CPS score calculation
        cps_score = (
            1.0
            if subtitle_cps <= self.max_cps
            else max(0.0, 1.0 - ((subtitle_cps - self.max_cps) / 10.0))
        )

        scores = {
            "transcription": QcDimensionScore(
                dimension_name="Transcription Accuracy",
                score=transcription_acc,
                severity=self._determine_severity(transcription_acc),
            ),
            "diarization": QcDimensionScore(
                dimension_name="Diarization Precision",
                score=diarization_prec,
                severity=self._determine_severity(diarization_prec),
            ),
            "translation": QcDimensionScore(
                dimension_name="Translation Meaning",
                score=translation_meaning,
                severity=self._determine_severity(translation_meaning),
            ),
            "timing": QcDimensionScore(
                dimension_name="Timing Fit",
                score=timing_fit,
                severity=self._determine_severity(timing_fit),
            ),
            "voice_quality": QcDimensionScore(
                dimension_name="Voice Quality MOS",
                score=voice_quality,
                severity=self._determine_severity(voice_quality),
            ),
            "lipsync": QcDimensionScore(
                dimension_name="Visual Lip-Sync",
                score=lipsync_score,
                severity=self._determine_severity(lipsync_score),
            ),
            "loudness": QcDimensionScore(
                dimension_name="Audio Loudness",
                score=round(loudness_score, 2),
                severity=self._determine_severity(loudness_score),
                detail=f"{integrated_lufs:.1f} LUFS",
            ),
            "subtitle_speed": QcDimensionScore(
                dimension_name="Subtitle Speed",
                score=round(cps_score, 2),
                severity=self._determine_severity(cps_score),
                detail=f"{subtitle_cps:.1f} CPS",
            ),
        }

        # Preset weighted overall score
        weights = self.PRESET_WEIGHTS.get(
            self.preset, self.PRESET_WEIGHTS[StudioQcPreset.BROADCAST_STUDIO]
        )
        overall = round(sum(d.score * weights[k] for k, d in scores.items()), 2)
        overall_severity = self._determine_severity(overall)

        recommendations: list[str] = []
        repair_actions: list[AutoRepairAction] = []

        if timing_fit < self.blocking_threshold:
            recommendations.append(
                "Timing duration mismatch: apply WSOLA time-stretching or adjust speed ratio"
            )
            repair_actions.append(
                AutoRepairAction(
                    action_id=Identifier(f"fix_timing_{utterance_id}"),
                    action_type="wsola_timestretch",
                    description="Apply WSOLA time-stretching to align duration with target window",
                    target_utterance_id=uid,
                    parameters={"target_speed_ratio": 1.15},
                )
            )

        if loudness_score < self.blocking_threshold:
            recommendations.append(
                f"Loudness deviation ({integrated_lufs:.1f} LUFS): apply EBU R128 normalization"
            )
            repair_actions.append(
                AutoRepairAction(
                    action_id=Identifier(f"fix_loudness_{utterance_id}"),
                    action_type="normalize_loudness",
                    description=f"Normalize integrated audio loudness to {self.target_loudness_lufs:.1f} LUFS",
                    target_utterance_id=uid,
                    parameters={"target_lufs": self.target_loudness_lufs},
                )
            )

        if cps_score < self.blocking_threshold:
            recommendations.append(
                f"Subtitle reading speed ({subtitle_cps:.1f} CPS) exceeds target: condense translation text"
            )
            repair_actions.append(
                AutoRepairAction(
                    action_id=Identifier(f"fix_subtitle_{utterance_id}"),
                    action_type="condense_translation",
                    description="Trigger LLM translation condenser to fit target CPS limit",
                    target_utterance_id=uid,
                    parameters={"target_cps": self.max_cps},
                )
            )

        if lipsync_score < self.blocking_threshold:
            recommendations.append(
                "Visual lip-sync artifact: check visual QC fallback or force preview tier"
            )
            repair_actions.append(
                AutoRepairAction(
                    action_id=Identifier(f"fix_lipsync_{utterance_id}"),
                    action_type="force_lipsync_cinema",
                    description="Re-render shot using LatentSync Cinema Quality engine tier",
                    target_utterance_id=uid,
                    parameters={"quality_tier": "cinema_quality"},
                )
            )

        return UtteranceQcReport(
            utterance_id=uid,
            overall_score=overall,
            severity=overall_severity,
            dimension_scores=scores,
            actionable_recommendations=recommendations,
            auto_repair_actions=repair_actions,
        )

    def generate_heatmap(
        self,
        project_id: str,
        reports: Sequence[UtteranceQcReport],
    ) -> TimelineQualityHeatmap:
        """
        Generate full timeline heatmap indexing pass/warning/blocking counts.
        """
        pid = Identifier(project_id)
        if not reports:
            return TimelineQualityHeatmap(
                project_id=pid,
                total_utterances=0,
                passed_count=0,
                warning_count=0,
                blocking_count=0,
                overall_project_quality=0.0,
                preset_used=self.preset,
                reports=[],
            )

        passed = sum(1 for r in reports if r.severity == QcSeverityLevel.PASS_GREEN)
        warning = sum(1 for r in reports if r.severity == QcSeverityLevel.WARNING_AMBER)
        blocking = sum(1 for r in reports if r.severity == QcSeverityLevel.BLOCKING_RED)
        avg_quality = round(sum(r.overall_score for r in reports) / len(reports), 2)

        return TimelineQualityHeatmap(
            project_id=pid,
            total_utterances=len(reports),
            passed_count=passed,
            warning_count=warning,
            blocking_count=blocking,
            overall_project_quality=avg_quality,
            preset_used=self.preset,
            reports=list(reports),
        )


__all__ = [
    "AutoRepairAction",
    "MultiDimensionalQCEvaluator",
    "QcDimensionScore",
    "QcSeverityLevel",
    "StudioQcPreset",
    "TimelineQualityHeatmap",
    "UtteranceQcReport",
]
