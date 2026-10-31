"""Real video thumbnail and filmstrip extractor using FFmpeg.

Extracts frame snapshots at precise timestamps or regular intervals,
caches thumbnail images to disk, and provides instant QPixmap/path
retrieval for video tracks on the timeline.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

from aidub.media.runtime import MediaRuntime, ensure_media_runtime_on_path

logger = logging.getLogger(__name__)


class ThumbnailExtractor:
    """Extracts and caches video frame thumbnails."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        if cache_dir is None:
            self._cache_dir = Path.home() / ".cache" / "aidub" / "thumbnails"
        else:
            self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ffmpeg_bin: Path | None = None

    def _ensure_ffmpeg(self) -> Path:
        if self._ffmpeg_bin is None or not self._ffmpeg_bin.is_file():
            ffmpeg, _ = ensure_media_runtime_on_path()
            self._ffmpeg_bin = ffmpeg
        return self._ffmpeg_bin

    def _video_key(self, video_path: Path) -> str:
        stat = video_path.stat()
        raw = f"{video_path.resolve()}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def extract_thumbnail(
        self,
        video_path: Path | str,
        timestamp_sec: float,
        height: int = 64,
    ) -> Path | None:
        """Extract a single video thumbnail frame at timestamp_sec."""
        p = Path(video_path)
        if not p.is_file():
            return None

        ffmpeg = self._ensure_ffmpeg()
        video_key = self._video_key(p)
        video_thumb_dir = self._cache_dir / video_key
        video_thumb_dir.mkdir(parents=True, exist_ok=True)

        # Truncate timestamp to 2 decimal places for cache name
        ts_tag = f"{max(0.0, float(timestamp_sec)):.2f}".replace(".", "_")
        out_path = video_thumb_dir / f"frame_{ts_tag}_{height}p.jpg"

        if out_path.is_file() and out_path.stat().st_size > 0:
            return out_path

        cmd = [
            str(ffmpeg),
            "-y",
            "-ss",
            f"{timestamp_sec:.3f}",
            "-i",
            str(p),
            "-vframes",
            "1",
            "-vf",
            f"scale=-2:{height}",
            "-q:v",
            "3",
            str(out_path),
        ]

        try:
            res = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                return out_path
            logger.debug("Thumbnail extraction non-zero exit %d: %s", res.returncode, res.stderr)
        except Exception as exc:
            logger.debug("Failed extracting thumbnail at %.2fs for %s: %s", timestamp_sec, p, exc)

        return None

    def extract_filmstrip(
        self,
        video_path: Path | str,
        duration_sec: float,
        count: int = 15,
        height: int = 64,
    ) -> list[tuple[float, Path]]:
        """Extract a series of evenly spaced thumbnails across clip duration.

        Returns list of (timestamp_sec, thumbnail_path).
        """
        p = Path(video_path)
        if not p.is_file() or duration_sec <= 0.0 or count <= 0:
            return []

        step = duration_sec / max(1, count)
        results: list[tuple[float, Path]] = []
        for i in range(count):
            ts = min(duration_sec, i * step + step * 0.1)
            thumb = self.extract_thumbnail(p, ts, height=height)
            if thumb is not None:
                results.append((ts, thumb))

        return results


# Global singleton instance
_GLOBAL_THUMBNAIL_EXTRACTOR: ThumbnailExtractor | None = None


def get_thumbnail_extractor() -> ThumbnailExtractor:
    """Access global ThumbnailExtractor instance."""
    global _GLOBAL_THUMBNAIL_EXTRACTOR
    if _GLOBAL_THUMBNAIL_EXTRACTOR is None:
        _GLOBAL_THUMBNAIL_EXTRACTOR = ThumbnailExtractor()
    return _GLOBAL_THUMBNAIL_EXTRACTOR


__all__ = [
    "ThumbnailExtractor",
    "get_thumbnail_extractor",
]

