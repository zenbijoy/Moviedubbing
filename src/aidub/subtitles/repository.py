"""
Subtitle Repository module.

Handles project persistence, storing normalized JSON representations and original SRT source files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from aidub.subtitles.models import SubtitleTrack

logger = logging.getLogger(__name__)


class SubtitleRepository:
    """Persistence manager for project subtitle tracks."""

    def __init__(self, project_dir: Path | str) -> None:
        self.project_dir = Path(project_dir)
        self.subtitles_dir = self.project_dir / "subtitles"
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_hash(content: str | bytes) -> str:
        """Calculate SHA-256 hash of text or byte content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def save_track(self, track: SubtitleTrack, filename: str = "imported.json") -> Path:
        """
        Save normalized SubtitleTrack to JSON file in project/subtitles/ directory.

        Args:
            track: SubtitleTrack instance.
            filename: Target JSON filename.

        Returns:
            Path to saved JSON file.
        """
        if not track.created_at:
            track.created_at = datetime.now().isoformat()

        json_path = self.subtitles_dir / filename
        data = track.to_dict()
        
        # Calculate content hash if empty
        data_str = json.dumps(data, sort_keys=True)
        if not track.content_hash:
            track.content_hash = self.calculate_hash(data_str)
            data["content_hash"] = track.content_hash

        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved subtitle track '%s' to '%s'", track.name, json_path)
        return json_path

    def load_track(self, filename: str = "imported.json") -> SubtitleTrack | None:
        """
        Load SubtitleTrack from JSON file in project/subtitles/ directory.

        Returns:
            SubtitleTrack or None if file does not exist.
        """
        json_path = self.subtitles_dir / filename
        if not json_path.is_file():
            return None

        try:
            raw_text = json_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            track = SubtitleTrack.from_dict(data)
            logger.info("Loaded subtitle track '%s' (%d segments) from '%s'", track.name, len(track.segments), json_path)
            return track
        except Exception as e:
            logger.error("Failed to load subtitle track from '%s': %e", json_path, e)
            return None

    def save_original_srt(self, raw_srt_content: str, filename: str = "original.srt") -> Path:
        """Store copy of original imported SRT file in project directory."""
        path = self.subtitles_dir / filename
        path.write_text(raw_srt_content, encoding="utf-8")
        return path


__all__ = ["SubtitleRepository"]
