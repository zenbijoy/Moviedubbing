"""
Autonomous Continuous Quality Benchmark Suite & Release Certification Harness.

Executes automated golden dataset benchmarks across target languages (English, Bengali, Hindi),
evaluates Word Error Rate (WER), BLEU translation accuracy, Voice Quality (MOS), and Lip-Sync SSIM metrics,
and issues automated Release Readiness Certificates.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import uuid4

from pydantic import Field, computed_field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class BenchmarkMeasurementsUnavailableError(RuntimeError):
    """Raised when no real benchmark measurements were supplied."""


class MetricDirection(StrEnum):
    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"


class BenchmarkMetricScore(ContractModel):
    """Quality metric benchmark score detail."""

    metric_name: str = Field(min_length=1)
    score_value: float = Field(ge=0.0)
    target_threshold: float = Field(ge=0.0)
    direction: MetricDirection

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        if self.direction == MetricDirection.LOWER_IS_BETTER:
            return self.score_value <= self.target_threshold
        return self.score_value >= self.target_threshold


class ReleaseReadinessCertificate(ContractModel):
    """Automated certification document confirming release quality standards."""

    certificate_id: Identifier
    app_version: str = Field(default="1.0.0", min_length=1)
    target_languages: list[str] = Field(default_factory=list)
    overall_quality_score: float = Field(ge=0.0, le=1.0)
    is_approved_for_release: bool = False
    metric_details: dict[str, BenchmarkMetricScore] = Field(default_factory=dict)
    summary: str = Field(min_length=1)


class AutonomousBenchmarkHarness:
    """
    Aggregates measured benchmark results into a release readiness certificate.

    Actual ASR, translation, TTS, lip-sync, and loudness benchmark runners must
    provide their measurements. This class does not invent benchmark scores.
    """

    def run_benchmark_suite(
        self,
        app_version: str = "1.0.0",
        languages: Sequence[str] = ("en-US", "bn-BD", "hi-IN"),
        *,
        measured_metrics: Mapping[str, BenchmarkMetricScore],
    ) -> ReleaseReadinessCertificate:
        """
        Evaluate real measurements collected by configured benchmark runners.
        """
        if not measured_metrics:
            raise BenchmarkMeasurementsUnavailableError(
                "Release certification is unavailable: no measured benchmark results were supplied."
            )
        metrics = dict(measured_metrics)

        all_passed = all(m.passed for m in metrics.values())
        overall = round(sum(1.0 if m.passed else 0.0 for m in metrics.values()) / len(metrics), 2)
        cid = Identifier(f"cert_{uuid4().hex}")
        failed_metrics = [name for name, metric in metrics.items() if not metric.passed]
        result_summary = (
            "All supplied benchmark measurements passed their thresholds."
            if all_passed
            else f"Measurements failed thresholds: {', '.join(failed_metrics)}."
        )

        cert = ReleaseReadinessCertificate(
            certificate_id=cid,
            app_version=app_version,
            target_languages=list(languages),
            overall_quality_score=overall,
            is_approved_for_release=all_passed,
            metric_details=metrics,
            summary=(
                f"Evaluated {len(metrics)} measured metrics for {len(languages)} languages. "
                f"{result_summary}"
            ),
        )

        logger.info(
            "autonomous_harness: generated Release Readiness Certificate %s (Approved: %s)",
            cid,
            all_passed,
        )
        return cert


__all__ = [
    "AutonomousBenchmarkHarness",
    "BenchmarkMeasurementsUnavailableError",
    "BenchmarkMetricScore",
    "MetricDirection",
    "ReleaseReadinessCertificate",
]
