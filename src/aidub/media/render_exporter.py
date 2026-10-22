"""
Multi-Track Master Deliverable Media Exporter.

Constructs FFmpeg stream multiplexing configurations to produce broadcast master files (MP4, MKV, MOV)
containing:
  - Video Stream 0: Primary Video Track (or Fast-Path Passthrough Video Copy)
  - Audio Stream 0: Original Audio Track (e.g. English `en-US`)
  - Audio Stream 1: Primary Dubbed Audio Track (e.g. Bengali `bn-BD`)
  - Audio Stream 2: Secondary Dubbed Audio Track (e.g. Hindi `hi-IN`)
  - Subtitle Stream 0: Primary Language Subtitles (`.srt` / `.ass`)
  - Subtitle Stream 1: Target Language Subtitles
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.media.ffmpeg_ops import _run

logger = logging.getLogger(__name__)


class ContainerFormat(StrEnum):
    MP4 = "mp4"
    MKV = "mkv"
    MOV = "mov"


class AudioChannelLayout(StrEnum):
    STEREO_2_0 = "stereo"
    SURROUND_5_1 = "5.1"
    SURROUND_7_1 = "7.1"


class AudioStreamTrack(ContractModel):
    """Audio stream track mapping descriptor."""

    track_index: int = Field(ge=0)
    language_code: str = Field(default="en", max_length=16)
    title: str = Field(default="Audio Track", max_length=64)
    file_path: str = Field(min_length=1)
    codec: str = Field(default="aac", max_length=32)
    bitrate_kbps: int = Field(default=320, ge=64, le=1536)
    channel_layout: AudioChannelLayout = AudioChannelLayout.STEREO_2_0


class SubtitleStreamTrack(ContractModel):
    """Subtitle stream track mapping descriptor."""

    track_index: int = Field(ge=0)
    language_code: str = Field(default="en", max_length=16)
    title: str = Field(default="Subtitles", max_length=64)
    file_path: str = Field(min_length=1)
    format: str = Field(default="srt", max_length=16)
    is_forced_subtitle: bool = False


class MasterExportOptions(ContractModel):
    """Configuration options for multi-track master media export."""

    output_filename: str = Field(min_length=1)
    output_directory: str = Field(min_length=1)
    container_format: ContainerFormat = ContainerFormat.MKV
    fast_video_copy: bool = True  # Stream copy original video stream if true
    video_codec: str = Field(default="h264", max_length=32)
    audio_tracks: list[AudioStreamTrack] = Field(default_factory=list)
    subtitle_tracks: list[SubtitleStreamTrack] = Field(default_factory=list)
    ebu_r128_normalize: bool = True
    target_lufs: float = Field(default=-24.0, ge=-70.0, le=-5.0)
    burn_in_subtitles: bool = False
    title: str = Field(default="AI Dubbed Movie Master", max_length=128)
    copyright_notice: str = Field(default="Copyright (c) 2026 Studio", max_length=128)


class MasterExportResult(ContractModel):
    """Export summary result for multi-track media container creation."""

    project_id: Identifier
    export_id: Identifier
    output_file_path: str = Field(min_length=1)
    container_format: ContainerFormat
    audio_track_count: int = Field(ge=0)
    subtitle_track_count: int = Field(ge=0)
    fast_copy_used: bool = True
    ebu_r128_applied: bool = True
    ffmpeg_command_args: list[str] = Field(default_factory=list)


class MasterMediaExporter:
    """
    Constructs FFmpeg multiplexing parameters and manages multi-track deliverable exports.
    """

    def build_ffmpeg_args(
        self,
        source_video_path: str,
        options: MasterExportOptions,
    ) -> list[str]:
        """
        Build FFmpeg command line arguments for multi-stream multiplexing.
        """
        args: list[str] = ["ffmpeg", "-y", "-i", source_video_path]

        # Add inputs for audio tracks
        for a_track in options.audio_tracks:
            args.extend(["-i", a_track.file_path])

        # Add inputs for subtitle tracks (unless burning in)
        if not options.burn_in_subtitles:
            for s_track in options.subtitle_tracks:
                args.extend(["-i", s_track.file_path])

        # Global Metadata Tags
        args.extend(["-metadata", f"title={options.title}"])
        args.extend(["-metadata", f"copyright={options.copyright_notice}"])

        # Map video stream 0:v
        args.extend(["-map", "0:v:0"])

        # Map audio streams
        input_idx = 1
        for a_idx, a_track in enumerate(options.audio_tracks):
            args.extend(["-map", f"{input_idx}:a:0"])
            args.extend([f"-metadata:s:a:{a_idx}", f"language={a_track.language_code}"])
            args.extend([f"-metadata:s:a:{a_idx}", f"title={a_track.title}"])
            input_idx += 1

        # Map subtitle streams if not burning in
        if not options.burn_in_subtitles:
            for sub_idx, s_track in enumerate(options.subtitle_tracks):
                args.extend(["-map", f"{input_idx}:s:0"])
                args.extend([f"-metadata:s:s:{sub_idx}", f"language={s_track.language_code}"])
                args.extend([f"-metadata:s:s:{sub_idx}", f"title={s_track.title}"])
                input_idx += 1

        # Video Codec & Subtitle Burn-In
        if options.burn_in_subtitles and options.subtitle_tracks:
            sub_file = options.subtitle_tracks[0].file_path
            args.extend(["-vf", f"subtitles={sub_file}"])
            args.extend(["-c:v", options.video_codec])
        elif options.fast_video_copy:
            args.extend(["-c:v", "copy"])
        else:
            args.extend(["-c:v", options.video_codec])

        # Audio Codec & EBU R128 Loudness Normalization Filter
        if options.ebu_r128_normalize:
            args.extend(["-af", f"loudnorm=I={options.target_lufs:.1f}:LRA=11:TP=-1.5"])

        args.extend(["-c:a", "aac", "-b:a", "320k"])

        if not options.burn_in_subtitles and options.subtitle_tracks:
            if options.container_format == ContainerFormat.MP4:
                args.extend(["-c:s", "mov_text"])
            else:
                args.extend(["-c:s", "srt"])

        out_path = (
            Path(options.output_directory)
            / f"{options.output_filename}.{options.container_format.value}"
        )
        args.append(str(out_path))

        return args

    def export_master_container(
        self,
        project_id: str,
        source_video_path: str,
        options: MasterExportOptions,
    ) -> MasterExportResult:
        """
        Execute a real FFmpeg master-container export.
        """
        pid = Identifier(project_id)
        cmd_args = self.build_ffmpeg_args(source_video_path, options)

        out_path = (
            Path(options.output_directory)
            / f"{options.output_filename}.{options.container_format.value}"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        required_inputs = [Path(source_video_path)]
        required_inputs.extend(Path(track.file_path) for track in options.audio_tracks)
        required_inputs.extend(Path(track.file_path) for track in options.subtitle_tracks)
        missing = [str(path) for path in required_inputs if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"master export inputs do not exist: {', '.join(missing)}")
        _run(cmd_args)
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg completed without producing a master deliverable")

        logger.info("render_exporter: created master container deliverable -> %s", out_path)

        return MasterExportResult(
            project_id=pid,
            export_id=Identifier(f"exp_{project_id}"),
            output_file_path=str(out_path),
            container_format=options.container_format,
            audio_track_count=len(options.audio_tracks),
            subtitle_track_count=len(options.subtitle_tracks),
            fast_copy_used=options.fast_video_copy and not options.burn_in_subtitles,
            ebu_r128_applied=options.ebu_r128_normalize,
            ffmpeg_command_args=cmd_args,
        )


__all__ = [
    "AudioChannelLayout",
    "AudioStreamTrack",
    "ContainerFormat",
    "MasterExportOptions",
    "MasterExportResult",
    "MasterMediaExporter",
    "SubtitleStreamTrack",
]
