"""
EBU R128 / ATSC A/85 loudness normalization and true-peak mastering bus.

Implements:
  - Two-pass integrated loudness measurement and normalization target
  - EBU R128 target: -23 LUFS, ATSC A/85 target: -24 LUFS
  - True-peak limiter to guarantee output peak ≤ -1.0 dBTP
  - Broadcast compliance summary reporting
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

# ── Broadcast loudness standards ──────────────────────────────────────────────

EBU_R128_TARGET_LUFS = -23.0
ATSC_A85_TARGET_LUFS = -24.0
TRUE_PEAK_LIMIT_DBTP = -1.0
LOUDNESS_GATE_RELATIVE_DB = -10.0  # EBU R128 gating relative threshold


class LoudnessStandard(StrEnum):
    EBU_R128 = "ebu_r128"  # -23 LUFS (European broadcast)
    ATSC_A85 = "atsc_a85"  # -24 LUFS (North American broadcast)
    STREAMING = "streaming"  # -14 LUFS (Spotify/YouTube recommendation)
    CUSTOM = "custom"


_STANDARD_TARGETS: dict[LoudnessStandard, float] = {
    LoudnessStandard.EBU_R128: EBU_R128_TARGET_LUFS,
    LoudnessStandard.ATSC_A85: ATSC_A85_TARGET_LUFS,
    LoudnessStandard.STREAMING: -14.0,
    LoudnessStandard.CUSTOM: -23.0,
}


class LoudnessMeasurement(ContractModel):
    """Measured loudness parameters of an audio file (from pass 1)."""

    integrated_lufs: float
    loudness_range_lu: float = Field(ge=0.0)
    true_peak_dbtp: float
    short_term_max_lufs: float


class LoudnessNormalizationConfig(ContractModel):
    """Configuration for the loudness normalization and mastering bus."""

    standard: LoudnessStandard = LoudnessStandard.EBU_R128
    custom_target_lufs: float = Field(default=EBU_R128_TARGET_LUFS, ge=-36.0, le=0.0)
    true_peak_limit_dbtp: float = Field(default=TRUE_PEAK_LIMIT_DBTP, ge=-6.0, le=0.0)
    tolerance_lu: float = Field(default=0.5, ge=0.0, le=2.0)

    @property
    def target_lufs(self) -> float:
        if self.standard == LoudnessStandard.CUSTOM:
            return self.custom_target_lufs
        return _STANDARD_TARGETS[self.standard]


class LoudnessNormalizationResult(ContractModel):
    """Full loudness normalization report."""

    utterance_id: Identifier
    input_measurement: LoudnessMeasurement
    target_lufs: float
    gain_applied_db: float
    output_integrated_lufs: float
    output_true_peak_dbtp: float
    true_peak_limited: bool
    within_tolerance: bool
    broadcast_compliant: bool
    standard: LoudnessStandard


class LoudnessMasteringBus:
    """
    Two-pass loudness normalization and true-peak mastering bus.

    Pass 1: Measure integrated loudness (LUFS), true-peak, and loudness range.
    Pass 2: Apply calculated gain correction + true-peak limiter.

    In production this drives an FFmpeg `loudnorm` filter chain.
    The measurement interface accepts pre-measured values (from ffprobe
    loudnorm analysis) to keep this service testable without audio I/O.
    """

    def __init__(self, config: LoudnessNormalizationConfig | None = None) -> None:
        self._config = config or LoudnessNormalizationConfig()

    def compute_normalization(
        self,
        utterance_id: str,
        measurement: LoudnessMeasurement,
    ) -> LoudnessNormalizationResult:
        """
        Compute the gain correction needed to normalize to target loudness.

        Args:
            utterance_id: Identifier for the utterance being mastered.
            measurement: Pass-1 loudness measurement (integrated LUFS, true-peak, LRA).

        Returns:
            LoudnessNormalizationResult with gain, output metrics, and compliance flags.
        """
        cfg = self._config
        gain_db = cfg.target_lufs - measurement.integrated_lufs

        # Calculate output true-peak after gain
        output_peak_dbtp = measurement.true_peak_dbtp + gain_db
        true_peak_limited = output_peak_dbtp > cfg.true_peak_limit_dbtp

        if true_peak_limited:
            # Reduce gain to keep output peak at limit
            excess_db = output_peak_dbtp - cfg.true_peak_limit_dbtp
            gain_db -= excess_db
            output_peak_dbtp = cfg.true_peak_limit_dbtp
            logger.debug(
                "loudness_bus: %s true-peak limit triggered, gain reduced by %.2fdB",
                utterance_id,
                excess_db,
            )

        output_integrated_lufs = measurement.integrated_lufs + gain_db
        delta_lu = abs(output_integrated_lufs - cfg.target_lufs)
        within_tolerance = delta_lu <= cfg.tolerance_lu
        broadcast_compliant = within_tolerance and output_peak_dbtp <= cfg.true_peak_limit_dbtp

        logger.info(
            "loudness_bus: %s  gain=%.2fdB  out=%.1f LUFS  peak=%.1f dBTP  compliant=%s",
            utterance_id,
            gain_db,
            output_integrated_lufs,
            output_peak_dbtp,
            broadcast_compliant,
        )

        return LoudnessNormalizationResult(
            utterance_id=Identifier(utterance_id),
            input_measurement=measurement,
            target_lufs=cfg.target_lufs,
            gain_applied_db=round(gain_db, 3),
            output_integrated_lufs=round(output_integrated_lufs, 2),
            output_true_peak_dbtp=round(output_peak_dbtp, 2),
            true_peak_limited=true_peak_limited,
            within_tolerance=within_tolerance,
            broadcast_compliant=broadcast_compliant,
            standard=cfg.standard,
        )

    def to_ffmpeg_loudnorm_filter(
        self,
        measurement: LoudnessMeasurement,
    ) -> str:
        """
        Build FFmpeg loudnorm filter string for pass-2 processing.

        Returns a filter string suitable for use in -af argument.
        """
        cfg = self._config
        target = cfg.target_lufs
        tp = cfg.true_peak_limit_dbtp

        return (
            f"loudnorm=I={target:.1f}:TP={tp:.1f}:LRA=7"
            f":measured_I={measurement.integrated_lufs:.2f}"
            f":measured_TP={measurement.true_peak_dbtp:.2f}"
            f":measured_LRA={measurement.loudness_range_lu:.2f}"
            f":linear=true:print_format=none"
        )


__all__ = [
    "ATSC_A85_TARGET_LUFS",
    "EBU_R128_TARGET_LUFS",
    "TRUE_PEAK_LIMIT_DBTP",
    "LoudnessMasteringBus",
    "LoudnessMeasurement",
    "LoudnessNormalizationConfig",
    "LoudnessNormalizationResult",
    "LoudnessStandard",
]
