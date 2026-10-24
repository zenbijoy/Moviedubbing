"""
Studio Viseme & Speech-Envelope Lip Synchronization Engine Adapter.

Implements the LipSyncEngine interface using VisemeLipSyncEngine.
Provides deterministic, zero-latency, local mouth synchronization for any movie shot.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aidub.adapters.lipsync_base import (
    LipSyncEngine,
    LipSyncOptions,
    LipSyncQualityTier,
    LipSyncResult,
)
from aidub.contracts.base import Identifier
from aidub.media.ffmpeg_ops import probe
from aidub.media.viseme_lipsync import VisemeLipSyncEngine
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


class VisemeLipSyncAdapter(LipSyncEngine):
    """Universal local viseme lip-synchronization adapter."""

    def __init__(self, feather_margin_px: int = 16) -> None:
        self.engine = VisemeLipSyncEngine(feather_margin_px=feather_margin_px)

    def synthesize_lip_sync(
        self,
        shot_id: str,
        source_video_path: str,
        target_audio_path: str,
        output_directory: str,
        options: LipSyncOptions | None = None,
        runtime: RecognitionRuntime | None = None,
    ) -> LipSyncResult:
        """Synthesize visual lip movement matching target audio track."""
        if runtime is not None:
            runtime.checkpoint()

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_video = out_dir / f"{shot_id}_viseme_synced.mp4"

        opts = options or LipSyncOptions(quality_tier=LipSyncQualityTier.STUDIO_VISEME)

        self.engine.synthesize_lip_sync(
            source_video_path=source_video_path,
            target_audio_path=target_audio_path,
            output_video_path=out_video,
            work_dir=out_dir,
        )

        metadata = probe(out_video)
        dur_s = float(metadata.get("format", {}).get("duration") or 0.0)
        fps = opts.fps
        rendered_frames = max(1, round(dur_s * fps))

        logger.info("viseme_adapter: successfully rendered lip-synced shot %s -> %s", shot_id, out_video.name)

        return LipSyncResult(
            job_id=Identifier(f"job_viseme_{shot_id}"),
            shot_id=Identifier(shot_id),
            output_video_path=str(out_video),
            quality_tier=LipSyncQualityTier.STUDIO_VISEME,
            rendered_frames=rendered_frames,
            duration_ms=round(dur_s * 1000),
            color_matched=True,
            anti_flicker_applied=True,
        )


__all__ = ["VisemeLipSyncAdapter"]
