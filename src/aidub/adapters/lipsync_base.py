"""
Base abstract interface and data structures for AI Lip-Sync Synthesis adapters.
"""

from __future__ import annotations

import abc
import os
import shlex
import subprocess
from enum import StrEnum
from fractions import Fraction
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.media.ffmpeg_ops import probe
from aidub.speech.runtime import RecognitionRuntime


class LipSyncQualityTier(StrEnum):
    PREVIEW_FAST = "preview_fast"      # Tier 1 (e.g. MuseTalk) for rapid NLE timeline preview
    CINEMA_QUALITY = "cinema_quality"  # Tier 2 (e.g. LatentSync) for final high-res delivery


class LipSyncOptions(ContractModel):
    """Configuration parameters for lip-sync synthesis adapter."""

    quality_tier: LipSyncQualityTier = LipSyncQualityTier.PREVIEW_FAST
    fps: float = Field(default=24.0, gt=0.0)
    device: str = Field(default="cuda", max_length=32)
    face_padding: int = Field(default=10, ge=0, le=50)
    feather_margin_px: int = Field(default=12, ge=0, le=64)
    color_match_mode: str = Field(default="histogram", max_length=32)  # "none", "histogram", "mean_std"
    poisson_blending: bool = True
    anti_flicker_alpha: float = Field(default=0.85, ge=0.0, le=1.0)


class LipSyncResult(ContractModel):
    """Output descriptor for synthesized lip-sync video track segment."""

    job_id: Identifier
    shot_id: Identifier
    output_video_path: str = Field(min_length=1)
    quality_tier: LipSyncQualityTier
    rendered_frames: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    color_matched: bool = True
    anti_flicker_applied: bool = True


class LipSyncEngine(abc.ABC):
    """Abstract interface for AI lip-sync adapters."""

    @abc.abstractmethod
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


def run_configured_lipsync(
    command_environment_variable: str,
    *,
    source_video_path: str,
    target_audio_path: str,
    output_path: Path,
) -> tuple[int, int]:
    """Run a configured real model command and return measured frames/duration."""

    source_video = Path(source_video_path)
    target_audio = Path(target_audio_path)
    if not source_video.is_file():
        raise FileNotFoundError(f"lip-sync source video does not exist: {source_video}")
    if not target_audio.is_file():
        raise FileNotFoundError(f"lip-sync target audio does not exist: {target_audio}")
    command_template = os.environ.get(command_environment_variable, "").strip()
    if not command_template:
        raise RuntimeError(
            f"{command_environment_variable} is not configured; set it to the installed "
            "model command using {video}, {audio}, and {output} placeholders"
        )
    command = [
        token.format(
            video=str(source_video.resolve()),
            audio=str(target_audio.resolve()),
            output=str(output_path.resolve()),
        )
        for token in shlex.split(command_template, posix=os.name != "nt")
    ]
    if not command:
        raise RuntimeError(f"{command_environment_variable} resolved to an empty command")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(  # noqa: S603
        command,
        check=False,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if process.returncode != 0:
        details = (process.stderr or process.stdout)[-2_000:]
        raise RuntimeError(
            f"lip-sync model failed with exit code {process.returncode}: {details}"
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("lip-sync model completed without producing a video")

    metadata = probe(output_path)
    format_duration = float(metadata.get("format", {}).get("duration") or 0.0)
    video_stream = next(
        (stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if format_duration <= 0 or video_stream is None:
        raise RuntimeError("lip-sync output is not a valid timed video")
    frame_rate = Fraction(str(video_stream.get("avg_frame_rate") or "0/1"))
    rendered_frames = round(format_duration * float(frame_rate))
    return max(1, rendered_frames), round(format_duration * 1_000)


__all__ = [
    "LipSyncEngine",
    "LipSyncOptions",
    "LipSyncQualityTier",
    "LipSyncResult",
    "run_configured_lipsync",
]
