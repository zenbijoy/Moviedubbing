"""
MuseTalk fast interactive preview Lip-Sync Engine adapter (Tier 1).

Delivers sub-second per-frame lip animation through an explicitly configured
local MuseTalk command.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aidub.adapters.lipsync_base import (
    LipSyncEngine,
    LipSyncOptions,
    LipSyncQualityTier,
    LipSyncResult,
    run_configured_lipsync,
)
from aidub.contracts.base import Identifier
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


class MuseTalkLipSyncEngine(LipSyncEngine):
    """Tier 1 fast timeline preview lip-sync engine adapter."""

    def synthesize_lip_sync(
        self,
        shot_id: str,
        source_video_path: str,
        target_audio_path: str,
        output_directory: str,
        options: LipSyncOptions | None = None,
        runtime: RecognitionRuntime | None = None,
    ) -> LipSyncResult:
        """Synthesize timeline preview lip-sync sequence."""
        opts = options or LipSyncOptions(quality_tier=LipSyncQualityTier.PREVIEW_FAST)
        if runtime is not None:
            runtime.checkpoint()

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        output_path = out_dir / f"{shot_id}_musetalk_preview.mp4"

        rendered_frames, duration_ms = run_configured_lipsync(
            "AIDUB_MUSETALK_COMMAND",
            source_video_path=source_video_path,
            target_audio_path=target_audio_path,
            output_path=output_path,
        )

        logger.info(
            "musetalk: rendered fast preview lip-sync for shot %s -> %s (color_match=%s, feather=%dpx)",
            shot_id,
            output_path,
            opts.color_match_mode,
            opts.feather_margin_px,
        )

        return LipSyncResult(
            job_id=Identifier(f"job_musetalk_{shot_id}"),
            shot_id=Identifier(shot_id),
            output_video_path=str(output_path),
            quality_tier=LipSyncQualityTier.PREVIEW_FAST,
            rendered_frames=rendered_frames,
            duration_ms=duration_ms,
            color_matched=opts.color_match_mode != "none",
            anti_flicker_applied=opts.anti_flicker_alpha > 0,
        )


__all__ = ["MuseTalkLipSyncEngine"]
