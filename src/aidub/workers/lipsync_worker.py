"""
Worker task handler for AI lip-sync rendering tasks (`lipsync.render`).
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.adapters.lipsync_base import LipSyncOptions, LipSyncQualityTier
from aidub.adapters.lipsync_latentsync import LatentSyncLipSyncEngine
from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


def run_lipsync_render(
    parameters: dict[str, Any], runtime: RecognitionRuntime | None = None
) -> dict[str, Any]:
    """
    Execute AI lip-sync synthesis for a shot video segment.

    Parameters:
      - shot_id: str
      - source_video_path: str
      - target_audio_path: str
      - output_directory: str
      - quality_tier: str ("preview_fast" | "cinema_quality")
    """
    shot_id = str(parameters["shot_id"])
    source_video_path = str(parameters["source_video_path"])
    target_audio_path = str(parameters["target_audio_path"])
    output_dir = str(parameters["output_directory"])
    tier_str = str(parameters.get("quality_tier", "preview_fast"))

    quality_tier = (
        LipSyncQualityTier.CINEMA_QUALITY
        if tier_str == "cinema_quality"
        else LipSyncQualityTier.PREVIEW_FAST
    )

    options = LipSyncOptions(quality_tier=quality_tier)

    if quality_tier == LipSyncQualityTier.CINEMA_QUALITY:
        engine: LatentSyncLipSyncEngine | MuseTalkLipSyncEngine = LatentSyncLipSyncEngine()
    else:
        engine = MuseTalkLipSyncEngine()

    result = engine.synthesize_lip_sync(
        shot_id=shot_id,
        source_video_path=source_video_path,
        target_audio_path=target_audio_path,
        output_directory=output_dir,
        options=options,
        runtime=runtime,
    )

    logger.info("run_lipsync_render: completed %s for shot %s", quality_tier.value, shot_id)
    return result.model_dump()


__all__ = ["run_lipsync_render"]
