"""
Subtitle Service module.

Orchestrates import, parsing, validation, persistence, track operations, and event notifications.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aidub.subtitles.encoding import detect_and_read_subtitle_file
from aidub.subtitles.exceptions import SubtitleImportError
from aidub.subtitles.models import (
    DialogueSegment,
    ImportSummary,
    SubtitleTrack,
)
from aidub.subtitles.repository import SubtitleRepository
from aidub.subtitles.srt_parser import SRTParser
from aidub.subtitles.validator import SubtitleValidator

logger = logging.getLogger(__name__)


class SubtitleService:
    """Service layer for subtitle domain operations."""

    def __init__(self, repository: SubtitleRepository | None = None) -> None:
        self.repository = repository
        self._parsers = {
            "srt": SRTParser(),
        }
        self._listeners: list[Callable[[str, Any], None]] = []

    def add_listener(self, listener: Callable[[str, Any], None]) -> None:
        """Register event notification listener."""
        self._listeners.append(listener)

    def _emit(self, event_name: str, payload: Any) -> None:
        for listener in self._listeners:
            try:
                listener(event_name, payload)
            except Exception as e:
                logger.error("Error in subtitle event listener for '%s': %e", event_name, e)

    def import_subtitle_file(
        self,
        file_path: Path | str,
        movie_duration_ms: int | None = None,
    ) -> tuple[SubtitleTrack, ImportSummary]:
        """
        Import, parse, validate, and store a subtitle file.

        Args:
            file_path: Path to .srt (or other supported format) subtitle file.
            movie_duration_ms: Optional movie duration in ms for boundary checking.

        Returns:
            (SubtitleTrack, ImportSummary)

        Raises:
            SubtitleImportError: If parsing or import fails.
        """
        path = Path(file_path)
        if not path.is_file():
            raise SubtitleImportError(f"Subtitle file not found: {path}")

        ext = path.suffix.lower().lstrip(".")
        if ext not in self._parsers:
            # Fallback to SRT parser if extension is not explicitly registered
            ext = "srt"

        self._emit("subtitle_import_started", {"path": str(path)})

        # 1. Detect encoding & read raw text
        raw_text, encoding = detect_and_read_subtitle_file(path)

        # 2. Parse text into DialogueSegments
        parser = self._parsers[ext]
        segments = parser.parse_text(raw_text)
        if not segments:
            raise SubtitleImportError(f"No valid subtitle segments found in file '{path.name}'.")

        # 3. Validate segments & compile report
        report = SubtitleValidator.validate_segments(segments, movie_duration_ms)

        # 4. Construct SubtitleTrack
        content_hash = SubtitleRepository.calculate_hash(raw_text)
        track = SubtitleTrack(
            name=path.stem.replace(".", " ").title(),
            source_file=str(path),
            source_format=ext,
            source_language="en",
            encoding=encoding,
            segments=segments,
            content_hash=content_hash,
        )

        # 5. Persist if repository exists
        if self.repository:
            self.repository.save_track(track, "imported.json")
            self.repository.save_original_srt(raw_text, "original.srt")

        # 6. Build ImportSummary
        first_ms = segments[0].start_ms if segments else 0
        last_ms = segments[-1].end_ms if segments else 0

        summary = ImportSummary(
            file_name=path.name,
            format=ext.upper(),
            encoding=encoding,
            detected_language="English",
            segment_count=len(segments),
            first_timestamp_ms=first_ms,
            last_timestamp_ms=last_ms,
            movie_duration_ms=movie_duration_ms,
            multi_speaker_count=report.multi_speaker_count,
            timing_overlaps=report.overlap_count,
            warning_count=report.warning_count,
            status_message="Successfully imported and validated.",
            validation_report=report,
        )

        self._emit("subtitle_import_completed", {"track": track, "summary": summary})
        logger.info("Imported subtitle file '%s': %d segments", path.name, len(segments))
        return track, summary

    def split_segment(
        self,
        track: SubtitleTrack,
        segment_id: str,
        split_time_ms: int,
        first_text: str,
        second_text: str,
    ) -> tuple[DialogueSegment, DialogueSegment] | None:
        """Split a DialogueSegment at a specified timecode and text boundary."""
        for i, seg in enumerate(track.segments):
            if seg.id == segment_id:
                if not (seg.start_ms < split_time_ms < seg.end_ms):
                    split_time_ms = seg.start_ms + (seg.duration_ms // 2)

                seg1 = DialogueSegment(
                    subtitle_index=seg.subtitle_index,
                    start_ms=seg.start_ms,
                    end_ms=split_time_ms,
                    original_text=first_text,
                    translated_text=seg.translated_text,
                    speaker_id=seg.speaker_id,
                    character_name=seg.character_name,
                )
                seg2 = DialogueSegment(
                    subtitle_index=seg.subtitle_index + 1,
                    start_ms=split_time_ms,
                    end_ms=seg.end_ms,
                    original_text=second_text,
                    translated_text="",
                    speaker_id=seg.speaker_id,
                    character_name=seg.character_name,
                )
                track.segments[i : i + 1] = [seg1, seg2]
                self._emit("subtitle_updated", {"track": track})
                return seg1, seg2
        return None

    def merge_segments(
        self, track: SubtitleTrack, segment_ids: list[str]
    ) -> DialogueSegment | None:
        """Merge multiple adjacent segments into a single segment."""
        matching = [s for s in track.segments if s.id in segment_ids]
        if len(matching) < 2:
            return None

        matching.sort(key=lambda s: s.start_ms)
        first_seg = matching[0]
        last_seg = matching[-1]

        merged_orig = "\n".join(s.original_text for s in matching if s.original_text)
        merged_trans = "\n".join(s.translated_text for s in matching if s.translated_text)

        merged = DialogueSegment(
            subtitle_index=first_seg.subtitle_index,
            start_ms=first_seg.start_ms,
            end_ms=last_seg.end_ms,
            original_text=merged_orig,
            translated_text=merged_trans,
            speaker_id=first_seg.speaker_id,
            character_name=first_seg.character_name,
        )

        # Remove merged segments and insert new one
        track.segments = [s for s in track.segments if s.id not in segment_ids]
        track.segments.append(merged)
        track.segments.sort(key=lambda s: s.start_ms)

        self._emit("subtitle_updated", {"track": track})
        return merged


__all__ = ["SubtitleService"]
