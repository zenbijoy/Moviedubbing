"""
Abstract subtitle parser interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from aidub.subtitles.models import DialogueSegment


class SubtitleParser(ABC):
    """Abstract generic interface for all subtitle format parsers."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Returns lowercase extension/format name (e.g., 'srt', 'vtt', 'ass')."""

    @abstractmethod
    def parse_text(self, text_content: str) -> list[DialogueSegment]:
        """
        Parse raw decoded subtitle text content into structured DialogueSegments.

        Args:
            text_content: Raw decoded subtitle file content.

        Returns:
            List of DialogueSegment objects.
        """

    def parse_file(self, file_path: Path | str) -> tuple[list[DialogueSegment], str]:
        """
        Detect encoding and parse subtitle file.

        Returns:
            (segments, detected_encoding_name)
        """
        from aidub.subtitles.encoding import detect_and_read_subtitle_file
        text, encoding = detect_and_read_subtitle_file(file_path)
        segments = self.parse_text(text)
        return segments, encoding


__all__ = ["SubtitleParser"]
