"""
Subtitle Exporter module.

Exports SubtitleTrack segments to SRT, VTT, ASS, or TXT formats with reindexing and timestamp formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from aidub.subtitles.models import SubtitleTrack
from aidub.subtitles.srt_parser import ms_to_srt_timestamp

logger = logging.getLogger(__name__)


class SubtitleExporter:
    """Exporter for SubtitleTrack segments."""

    @staticmethod
    def export_to_srt(
        track: SubtitleTrack,
        output_path: Path | str,
        use_translated: bool = False,
        use_adapted: bool = False,
        reindex: bool = True,
    ) -> Path:
        """
        Export track segments to standard SRT file.

        Args:
            track: SubtitleTrack instance.
            output_path: Target .srt file path.
            use_translated: If True, export translated_text.
            use_adapted: If True, export adapted_text (dub text).
            reindex: If True, renumber subtitle blocks 1, 2, 3...

        Returns:
            Path to generated file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        sorted_segs = sorted(track.segments, key=lambda s: s.start_ms)

        lines: list[str] = []
        for i, seg in enumerate(sorted_segs, start=1):
            idx = i if reindex else seg.subtitle_index
            start_ts = ms_to_srt_timestamp(seg.start_ms)
            end_ts = ms_to_srt_timestamp(seg.end_ms)

            text = seg.original_text
            if use_adapted and seg.adapted_text:
                text = seg.adapted_text
            elif use_translated and seg.translated_text:
                text = seg.translated_text

            lines.append(f"{idx}")
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        logger.info("Exported SRT file to '%s' (%d segments)", path, len(sorted_segs))
        return path

    @staticmethod
    def export_to_vtt(
        track: SubtitleTrack,
        output_path: Path | str,
        use_translated: bool = False,
    ) -> Path:
        """Export track segments to WebVTT format."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        sorted_segs = sorted(track.segments, key=lambda s: s.start_ms)

        lines: list[str] = ["WEBVTT", ""]
        for i, seg in enumerate(sorted_segs, start=1):
            start_ts = ms_to_srt_timestamp(seg.start_ms).replace(",", ".")
            end_ts = ms_to_srt_timestamp(seg.end_ms).replace(",", ".")
            text = seg.translated_text if (use_translated and seg.translated_text) else seg.original_text

            lines.append(f"{i}")
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    @staticmethod
    def export_to_txt(
        track: SubtitleTrack,
        output_path: Path | str,
        use_translated: bool = False,
    ) -> Path:
        """Export raw script text without timestamps."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        sorted_segs = sorted(track.segments, key=lambda s: s.start_ms)
        lines = [
            (seg.translated_text if (use_translated and seg.translated_text) else seg.original_text)
            for seg in sorted_segs
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


__all__ = ["SubtitleExporter"]
