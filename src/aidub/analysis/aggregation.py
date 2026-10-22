"""Deterministic aggregation for source-analysis progress and confidence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from aidub.domain.base import normalize_utc
from aidub.domain.types import require_unique

from .models import (
    BASIS_POINTS,
    AnalysisProgress,
    AnalysisRunId,
    AnalysisStage,
    AnalysisStageProgress,
    ConfidenceAggregate,
    ConfidenceAssessment,
    can_transition_stage_status,
    derive_run_status,
)


class AnalysisProgressRegressionError(ValueError):
    """Raised when a publisher attempts to make one analysis run move backward."""


class ConfidenceAggregationError(ValueError):
    """Raised when incomparable confidence assessments are combined."""


def aggregate_progress(
    run_id: AnalysisRunId,
    stages: Iterable[AnalysisStage],
    *,
    emitted_at: datetime,
    previous: AnalysisProgress | None = None,
) -> AnalysisProgress:
    """Build a canonical weighted progress snapshot from complete stage state.

    The arithmetic uses only integers.  Stage summaries are ordered by stable ID,
    so an adapter's incidental input iteration order cannot affect the published
    contract.  When a previous snapshot is supplied, all stage and run progress
    must be monotonic; a retry requires a fresh run ID instead.
    """

    ordered_stages = tuple(sorted(stages, key=lambda stage: stage.stage_id))
    if not ordered_stages:
        raise ValueError("analysis progress requires at least one stage")
    require_unique(
        tuple(stage.stage_id for stage in ordered_stages), field_name="analysis stage_ids"
    )
    instant = normalize_utc(emitted_at)
    latest_stage_update = max(stage.updated_at for stage in ordered_stages)
    if instant < latest_stage_update:
        raise ValueError("analysis progress cannot be emitted before its latest stage update")

    completed_weighted_units = sum(
        stage.weight_units * stage.progress_basis_points for stage in ordered_stages
    )
    total_weighted_units = sum(stage.weight_units * BASIS_POINTS for stage in ordered_stages)
    candidate = AnalysisProgress(
        run_id=run_id,
        status=derive_run_status(ordered_stages),
        stages=tuple(AnalysisStageProgress.from_stage(stage) for stage in ordered_stages),
        completed_weighted_units=completed_weighted_units,
        total_weighted_units=total_weighted_units,
        progress_basis_points=(completed_weighted_units * BASIS_POINTS) // total_weighted_units,
        emitted_at=instant,
    )
    if previous is not None:
        _validate_monotonic_progress(previous, candidate)
    return candidate


def aggregate_confidence(
    assessments: Iterable[ConfidenceAssessment],
    *,
    aggregated_at: datetime,
) -> ConfidenceAggregate:
    """Compute an exact weighted confidence only for the same calibrated metric."""

    values = tuple(assessments)
    if not values:
        raise ConfidenceAggregationError("confidence aggregation requires at least one assessment")
    require_unique(
        tuple(item.assessment_id for item in values), field_name="confidence assessment_ids"
    )
    first = values[0]
    incompatible = tuple(
        item.assessment_id
        for item in values
        if (
            item.metric is not first.metric
            or item.calibration_id != first.calibration_id
            or item.source_sha256 != first.source_sha256
        )
    )
    if incompatible:
        joined = ", ".join(sorted(incompatible))
        raise ConfidenceAggregationError(
            "confidence assessments require identical metric, calibration, and source hash: "
            + joined
        )
    instant = normalize_utc(aggregated_at)
    latest_assessment = max(item.assessed_at for item in values)
    if instant < latest_assessment:
        raise ConfidenceAggregationError("confidence cannot be aggregated before it was assessed")
    total_weight = sum(item.weight_units for item in values)
    weighted_score = sum(item.confidence_basis_points * item.weight_units for item in values)
    return ConfidenceAggregate(
        metric=first.metric,
        calibration_id=first.calibration_id,
        source_sha256=first.source_sha256,
        confidence_basis_points=weighted_score // total_weight,
        total_weight_units=total_weight,
        assessment_ids=tuple(sorted(item.assessment_id for item in values)),
        aggregated_at=instant,
    )


def _validate_monotonic_progress(previous: AnalysisProgress, current: AnalysisProgress) -> None:
    if previous.run_id != current.run_id:
        raise AnalysisProgressRegressionError(
            "progress snapshots belong to different analysis runs"
        )
    if current.emitted_at < previous.emitted_at:
        raise AnalysisProgressRegressionError("analysis progress timestamp cannot move backwards")
    previous_stages = {stage.stage_id: stage for stage in previous.stages}
    current_stages = {stage.stage_id: stage for stage in current.stages}
    if previous_stages.keys() != current_stages.keys():
        raise AnalysisProgressRegressionError(
            "analysis run stage plan cannot change after publication"
        )
    for stage_id, prior_stage in previous_stages.items():
        next_stage = current_stages[stage_id]
        if not can_transition_stage_status(prior_stage.status, next_stage.status):
            raise AnalysisProgressRegressionError(
                f"stage {stage_id} cannot transition from {prior_stage.status} to {next_stage.status}"
            )
        if next_stage.completed_units * prior_stage.total_units < (
            prior_stage.completed_units * next_stage.total_units
        ):
            raise AnalysisProgressRegressionError(
                f"stage {stage_id} progress cannot move backwards"
            )
    if current.progress_basis_points < previous.progress_basis_points:
        raise AnalysisProgressRegressionError("aggregate analysis progress cannot move backwards")


__all__ = [
    "AnalysisProgressRegressionError",
    "ConfidenceAggregationError",
    "aggregate_confidence",
    "aggregate_progress",
]
