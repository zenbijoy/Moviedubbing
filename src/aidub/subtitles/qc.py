"""
Subtitle QC rule engine with broadcast-grade validation checks.

Rules enforced:
  - Max characters per line: 37 (configurable)
  - Reading speed: ≤ 17 chars/sec (configurable)
  - Minimum duration: 1.0s
  - Maximum duration: 7.0s
  - Overlapping cues: adjacent cue times must not overlap
  - Gap: minimum 80ms gap between successive cues
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

# Broadcast defaults
DEFAULT_MAX_CHARS_PER_LINE = 37
DEFAULT_MAX_READING_SPEED_CPS = 17.0  # chars per second
DEFAULT_MIN_DURATION_S = 1.0
DEFAULT_MAX_DURATION_S = 7.0
DEFAULT_MIN_GAP_MS = 80


class QcViolationKind(StrEnum):
    LINE_TOO_LONG = "line_too_long"
    READING_SPEED_EXCEEDED = "reading_speed_exceeded"
    DURATION_TOO_SHORT = "duration_too_short"
    DURATION_TOO_LONG = "duration_too_long"
    OVERLAPPING_CUES = "overlapping_cues"
    GAP_TOO_SHORT = "gap_too_short"
    EMPTY_TEXT = "empty_text"


class QcViolation(ContractModel):
    """A single subtitle QC rule violation."""

    cue_index: int = Field(ge=0)
    cue_id: str = Field(default="", max_length=64)
    kind: QcViolationKind
    message: str = Field(max_length=512)
    severity: str = Field(default="error", max_length=16)


class SubtitleQcConfig(ContractModel):
    """Configurable subtitle QC rule thresholds."""

    max_chars_per_line: int = Field(default=DEFAULT_MAX_CHARS_PER_LINE, ge=10, le=80)
    max_reading_speed_cps: float = Field(default=DEFAULT_MAX_READING_SPEED_CPS, ge=5.0, le=30.0)
    min_duration_s: float = Field(default=DEFAULT_MIN_DURATION_S, ge=0.1, le=3.0)
    max_duration_s: float = Field(default=DEFAULT_MAX_DURATION_S, ge=2.0, le=30.0)
    min_gap_ms: int = Field(default=DEFAULT_MIN_GAP_MS, ge=0, le=500)


class SubtitleCue(ContractModel):
    """A normalized subtitle cue for QC checking."""

    cue_id: str = Field(default="", max_length=64)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(default="", max_length=4_000)

    @property
    def duration_s(self) -> float:
        return max(0.0, (self.end_ms - self.start_ms) / 1_000.0)

    @property
    def char_count(self) -> int:
        return sum(len(line) for line in self.text.splitlines())

    @property
    def max_line_length(self) -> int:
        lines = self.text.splitlines()
        return max((len(line) for line in lines), default=0)


class SubtitleQcReport(ContractModel):
    """Full QC report for a subtitle track."""

    track_id: Identifier
    total_cues: int = Field(ge=0)
    violations: list[QcViolation] = Field(default_factory=list)
    passed: bool
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)


class SubtitleQcEngine:
    """
    Broadcast-grade subtitle QC rule checker.

    Validates a sequence of SubtitleCue objects against configurable thresholds
    and returns a full QcReport with per-cue violations.
    """

    def __init__(self, config: SubtitleQcConfig | None = None) -> None:
        self._config = config or SubtitleQcConfig()

    def check(
        self,
        track_id: str,
        cues: list[SubtitleCue],
    ) -> SubtitleQcReport:
        """
        Run all QC rules on a subtitle track.

        Args:
            track_id: Identifier for the subtitle track.
            cues: List of subtitle cues in chronological order.

        Returns:
            SubtitleQcReport with all violations found.
        """
        violations: list[QcViolation] = []
        cfg = self._config

        for idx, cue in enumerate(cues):
            cue_id = cue.cue_id or str(idx + 1)

            # Empty text
            if not cue.text.strip():
                violations.append(
                    QcViolation(
                        cue_index=idx,
                        cue_id=cue_id,
                        kind=QcViolationKind.EMPTY_TEXT,
                        message=f"Cue {cue_id} has empty text",
                    )
                )

            # Line length
            max_line = cue.max_line_length
            if max_line > cfg.max_chars_per_line:
                violations.append(
                    QcViolation(
                        cue_index=idx,
                        cue_id=cue_id,
                        kind=QcViolationKind.LINE_TOO_LONG,
                        message=f"Cue {cue_id}: longest line {max_line} chars exceeds max {cfg.max_chars_per_line}",
                    )
                )

            # Reading speed
            dur_s = cue.duration_s
            if dur_s > 0:
                cps = cue.char_count / dur_s
                if cps > cfg.max_reading_speed_cps:
                    violations.append(
                        QcViolation(
                            cue_index=idx,
                            cue_id=cue_id,
                            kind=QcViolationKind.READING_SPEED_EXCEEDED,
                            message=f"Cue {cue_id}: {cps:.1f} chars/sec exceeds max {cfg.max_reading_speed_cps:.0f}",
                        )
                    )

            # Duration
            if dur_s < cfg.min_duration_s:
                violations.append(
                    QcViolation(
                        cue_index=idx,
                        cue_id=cue_id,
                        kind=QcViolationKind.DURATION_TOO_SHORT,
                        message=f"Cue {cue_id}: {dur_s:.2f}s below min {cfg.min_duration_s:.1f}s",
                    )
                )
            elif dur_s > cfg.max_duration_s:
                violations.append(
                    QcViolation(
                        cue_index=idx,
                        cue_id=cue_id,
                        kind=QcViolationKind.DURATION_TOO_LONG,
                        message=f"Cue {cue_id}: {dur_s:.2f}s exceeds max {cfg.max_duration_s:.1f}s",
                    )
                )

            # Overlap and gap checks against previous cue
            if idx > 0:
                prev = cues[idx - 1]
                if cue.start_ms < prev.end_ms:
                    violations.append(
                        QcViolation(
                            cue_index=idx,
                            cue_id=cue_id,
                            kind=QcViolationKind.OVERLAPPING_CUES,
                            message=(
                                f"Cue {cue_id} starts at {cue.start_ms}ms but previous cue "
                                f"ends at {prev.end_ms}ms (overlap {prev.end_ms - cue.start_ms}ms)"
                            ),
                        )
                    )
                elif (cue.start_ms - prev.end_ms) < cfg.min_gap_ms:
                    violations.append(
                        QcViolation(
                            cue_index=idx,
                            cue_id=cue_id,
                            kind=QcViolationKind.GAP_TOO_SHORT,
                            message=(
                                f"Cue {cue_id}: gap {cue.start_ms - prev.end_ms}ms to previous cue "
                                f"is below minimum {cfg.min_gap_ms}ms"
                            ),
                            severity="warning",
                        )
                    )

        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")

        passed = error_count == 0
        if violations:
            logger.warning(
                "subtitle_qc: %s — %d error(s), %d warning(s) across %d cues",
                track_id,
                error_count,
                warning_count,
                len(cues),
            )

        return SubtitleQcReport(
            track_id=Identifier(track_id),
            total_cues=len(cues),
            violations=violations,
            passed=passed,
            error_count=error_count,
            warning_count=warning_count,
        )


__all__ = [
    "QcViolation",
    "QcViolationKind",
    "SubtitleCue",
    "SubtitleQcConfig",
    "SubtitleQcEngine",
    "SubtitleQcReport",
]
