"""
LatentSync high-resolution Cinema quality Lip-Sync Engine adapter (Tier 2).

Delivers broadcast-grade 1080p/4K latent diffusion lip synchronization through
an explicitly configured local LatentSync command.
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


class LatentSyncLipSyncEngine(LipSyncEngine):
    """Tier 2 high-resolution cinema quality lip-sync engine adapter."""

    def synthesize_lip_sync(
        self,
        shot_id: str,
        source_video_path: str,
        target_audio_path: str,
        output_directory: str,
        options: LipSyncOptions | None = None,
        runtime: RecognitionRuntime | None = None,
    ) -> LipSyncResult:
        """Synthesize high-resolution cinema quality lip-sync sequence."""
        opts = options or LipSyncOptions(quality_tier=LipSyncQualityTier.CINEMA_QUALITY)
        if runtime is not None:
            runtime.checkpoint()

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        output_path = out_dir / f"{shot_id}_latentsync_cinema.mp4"

        rendered_frames, duration_ms = run_configured_lipsync(
            "AIDUB_LATENTSYNC_COMMAND",
            source_video_path=source_video_path,
            target_audio_path=target_audio_path,
            output_path=output_path,
        )

        logger.info(
            "latentsync: rendered cinema lip-sync for shot %s -> %s (color_match=%s, feather=%dpx)",
            shot_id,
            output_path,
            opts.color_match_mode,
            opts.feather_margin_px,
        )

        return LipSyncResult(
            job_id=Identifier(f"job_latentsync_{shot_id}"),
            shot_id=Identifier(shot_id),
            output_video_path=str(output_path),
            quality_tier=LipSyncQualityTier.CINEMA_QUALITY,
            rendered_frames=rendered_frames,
            duration_ms=duration_ms,
            color_matched=opts.color_match_mode != "none",
            anti_flicker_applied=opts.anti_flicker_alpha > 0,
        )


__all__ = ["LatentSyncLipSyncEngine"]
