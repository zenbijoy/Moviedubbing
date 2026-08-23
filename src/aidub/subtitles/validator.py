"""
Subtitle Validator module.

Performs timing validation, overlap detection, duplicate checking, and duration bounds checking.
"""

from __future__ import annotations

import logging
from aidub.subtitles.models import (
    DialogueSegment,
    ValidationReport,
    ValidationWarning,
)

logger = logging.getLogger(__name__)

MAX_RECOMMENDED_DURATION_MS = 30_000  # 30 seconds
MAX_RECOMMENDED_CHAR_COUNT = 250


class SubtitleValidator:
    """Validator for DialogueSegments and SubtitleTracks."""

    @staticmethod
    def validate_segments(
        segments: list[DialogueSegment],
        movie_duration_ms: int | None = None,
    ) -> ValidationReport:
        """
        Validate list of DialogueSegments and compile a comprehensive ValidationReport.

        Args:
            segments: List of DialogueSegments to validate.
            movie_duration_ms: Optional movie duration in milliseconds for boundary checking.

        Returns:
            ValidationReport instance.
        """
        report = ValidationReport(total_parsed=len(segments))
        if not segments:
            return report

        # Sort segments by start_ms for accurate overlap detection
        sorted_segs = sorted(segments, key=lambda s: (s.start_ms, s.end_ms))

        seen_indices: set[int] = set()

        for i, seg in enumerate(sorted_segs):
            is_valid = True

            # 1. Invalid timestamp / negative duration
            if seg.start_ms < 0 or seg.end_ms < 0 or seg.end_ms < seg.start_ms:
                is_valid = False
                report.warnings.append(
                    ValidationWarning(
                        category="invalid_timestamp",
                        message=f"Subtitle #{seg.subtitle_index} has invalid timestamp range ({seg.start_ms}ms -> {seg.end_ms}ms).",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="critical",
                    )
                )

            # 2. Empty text
            if not seg.original_text or not seg.original_text.strip():
                is_valid = False
                report.warnings.append(
                    ValidationWarning(
                        category="missing_text",
                        message=f"Subtitle #{seg.subtitle_index} has empty dialogue text.",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="warning",
                    )
                )

            # 3. Duplicate index
            if seg.subtitle_index in seen_indices:
                report.duplicate_count += 1
                report.warnings.append(
                    ValidationWarning(
                        category="duplicate_index",
                        message=f"Duplicate subtitle index #{seg.subtitle_index} detected.",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="warning",
                    )
                )
            seen_indices.add(seg.subtitle_index)

            # 4. Extremely long duration or text
            if seg.duration_ms > MAX_RECOMMENDED_DURATION_MS:
                report.warnings.append(
                    ValidationWarning(
                        category="long_duration",
                        message=f"Subtitle #{seg.subtitle_index} has long duration ({seg.duration_ms / 1000.0:.1f}s > 30s).",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="info",
                    )
                )

            if len(seg.original_text) > MAX_RECOMMENDED_CHAR_COUNT:
                report.warnings.append(
                    ValidationWarning(
                        category="long_text",
                        message=f"Subtitle #{seg.subtitle_index} has high character count ({len(seg.original_text)} chars).",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="info",
                    )
                )

            # 5. Multi-speaker detection count
            if seg.possible_multi_speaker:
                report.multi_speaker_count += 1

            # 6. Overlap with previous segment
            if i > 0:
                prev = sorted_segs[i - 1]
                if seg.start_ms < prev.end_ms:
                    report.overlap_count += 1
                    overlap_ms = prev.end_ms - seg.start_ms
                    report.warnings.append(
                        ValidationWarning(
                            category="timing_overlap",
                            message=f"Subtitle #{seg.subtitle_index} overlaps with #{prev.subtitle_index} by {overlap_ms}ms.",
                            subtitle_index=seg.subtitle_index,
                            segment_id=seg.id,
                            severity="warning",
                        )
                    )

            # 7. Movie duration bounds check
            if movie_duration_ms and seg.end_ms > movie_duration_ms:
                diff_sec = (seg.end_ms - movie_duration_ms) / 1000.0
                report.warnings.append(
                    ValidationWarning(
                        category="exceeds_movie_duration",
                        message=f"Subtitle #{seg.subtitle_index} timestamp ({seg.end_ms}ms) extends {diff_sec:.1f}s beyond movie duration.",
                        subtitle_index=seg.subtitle_index,
                        segment_id=seg.id,
                        severity="warning",
                    )
                )

            if is_valid:
                report.valid_count += 1
            else:
                report.skipped_count += 1

        report.warning_count = len(report.warnings)
        logger.info(
            "Validation completed: %d valid, %d warnings, %d overlaps, %d multi-speaker",
            report.valid_count,
            report.warning_count,
            report.overlap_count,
            report.multi_speaker_count,
        )
        return report


__all__ = ["SubtitleValidator", "MAX_RECOMMENDED_DURATION_MS"]
