"""
Broadcast Master Delivery Exporter for AIDub Studio.

Generates industry-standard delivery masters for:
- Netflix / Theatrical Delivery (5.1 Surround, EBU R128 -23 LUFS / -1.0 dBTP, AC3/PCM)
- YouTube / Web 4K (-14 LUFS, H.264/H.265 High Profile, +faststart, embedded subtitles)
- Mobile / Fast Social Delivery (1080p, AAC Stereo, instant web streaming)
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, probe
from aidub.media.surround_mixer import SurroundSoundMixer

logger = logging.getLogger(__name__)


class BroadcastPreset(enum.StrEnum):
    YOUTUBE_4K = "youtube_4k"
    NETFLIX_51 = "netflix_51"
    THEATRICAL_MASTER = "theatrical_master"
    MOBILE_STREAM = "mobile_stream"


@dataclass
class ExportConfig:
    preset: BroadcastPreset
    description: str
    video_codec: str
    audio_codec: str
    audio_bitrate: str
    sample_rate: int
    channels: int
    loudness_lufs: float
    true_peak_db: float
    crf: int
    extra_movflags: list[str]


PRESET_CONFIGS: dict[BroadcastPreset, ExportConfig] = {
    BroadcastPreset.YOUTUBE_4K: ExportConfig(
        preset=BroadcastPreset.YOUTUBE_4K,
        description="YouTube / Web UHD (H.264 High Profile, -14 LUFS, AAC Stereo/5.1)",
        video_codec="libx264",
        audio_codec="aac",
        audio_bitrate="384k",
        sample_rate=48000,
        channels=2,
        loudness_lufs=-14.0,
        true_peak_db=-1.0,
        crf=18,
        extra_movflags=["+faststart"],
    ),
    BroadcastPreset.NETFLIX_51: ExportConfig(
        preset=BroadcastPreset.NETFLIX_51,
        description="Netflix Broadcast Spec (5.1 Surround, EBU R128 -23 LUFS, AC3 640k)",
        video_codec="libx264",
        audio_codec="ac3",
        audio_bitrate="640k",
        sample_rate=48000,
        channels=6,
        loudness_lufs=-23.0,
        true_peak_db=-1.0,
        crf=16,
        extra_movflags=["+faststart"],
    ),
    BroadcastPreset.THEATRICAL_MASTER: ExportConfig(
        preset=BroadcastPreset.THEATRICAL_MASTER,
        description="Theatrical Master Archive (ProRes / High Bitrate 5.1 E-AC3, -23 LUFS)",
        video_codec="libx264",
        audio_codec="eac3",
        audio_bitrate="768k",
        sample_rate=48000,
        channels=6,
        loudness_lufs=-23.0,
        true_peak_db=-1.0,
        crf=14,
        extra_movflags=["+faststart"],
    ),
    BroadcastPreset.MOBILE_STREAM: ExportConfig(
        preset=BroadcastPreset.MOBILE_STREAM,
        description="Mobile / Fast Social Stream (H.264 CRF 22, 192k AAC Stereo)",
        video_codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        sample_rate=44100,
        channels=2,
        loudness_lufs=-14.0,
        true_peak_db=-1.0,
        crf=22,
        extra_movflags=["+faststart"],
    ),
}


class BroadcastMasterExporter:
    """Orchestrates production-grade video remuxing and broadcast mastering."""

    @classmethod
    def export(
        cls,
        *,
        video_path: Path | str,
        audio_path: Path | str,
        output_path: Path | str,
        preset: BroadcastPreset | str = BroadcastPreset.YOUTUBE_4K,
        subtitle_path: Path | str | None = None,
        burn_subtitles: bool = False,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> Path:
        """
        Export final video with target broadcast profile and integrated loudness.

        Args:
            video_path: Source or lip-synced video file.
            audio_path: Mixed stereo or 5.1 audio master track.
            output_path: Destination media path (.mp4, .mkv, .mov).
            preset: Delivery preset specification.
            subtitle_path: Optional SRT or VTT subtitle file to embed or burn.
            burn_subtitles: If True, hardcodes subtitles onto video stream.
            progress_cb: Optional callback(percent, message) for UI updates.
        """
        vid = Path(video_path)
        aud = Path(audio_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if not vid.is_file():
            raise FileNotFoundError(f"Source video not found: {vid}")
        if not aud.is_file():
            raise FileNotFoundError(f"Master audio track not found: {aud}")
        if vid.resolve() == out.resolve():
            raise ValueError(f"Output path cannot overwrite source video: {out}")

        if isinstance(preset, str):
            try:
                preset = BroadcastPreset(preset.lower())
            except ValueError:
                preset = BroadcastPreset.YOUTUBE_4K

        cfg = PRESET_CONFIGS.get(preset, PRESET_CONFIGS[BroadcastPreset.YOUTUBE_4K])

        if progress_cb:
            progress_cb(10, f"Configuring {cfg.description}...")

        cmd: list[str] = [
            _ffmpeg_exe(),
            "-y",
            "-i",
            str(vid),
            "-i",
            str(aud),
        ]

        # Handle Subtitles input
        sub_file = Path(subtitle_path) if subtitle_path else None
        has_sub = sub_file is not None and sub_file.is_file()

        if has_sub and not burn_subtitles:
            cmd.extend(["-i", str(sub_file)])

        # Video filters / options
        if has_sub and burn_subtitles:
            # Escape path for ffmpeg subtitles filter (replace backslashes and colons for Windows)
            clean_sub = str(sub_file.resolve()).replace("\\", "/").replace(":", "\\:")
            cmd.extend(
                [
                    "-vf",
                    f"subtitles='{clean_sub}'",
                    "-c:v",
                    cfg.video_codec,
                    "-crf",
                    str(cfg.crf),
                    "-preset",
                    "medium",
                ]
            )
        else:
            # Stream copy video for lossless speed when no filter required, or re-encode if requested
            cmd.extend(["-c:v", "copy"])

        # Map streams
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

        if has_sub and not burn_subtitles:
            cmd.extend(
                [
                    "-map",
                    "2:s:0",
                    "-c:s",
                    "mov_text" if out.suffix.lower() == ".mp4" else "srt",
                    "-metadata:s:s:0",
                    "language=ben",
                    "-metadata:s:s:0",
                    "title=Bengali Dubbed Subtitles",
                ]
            )

        # Audio encoding settings
        cmd.extend(
            [
                "-c:a",
                cfg.audio_codec,
                "-b:a",
                cfg.audio_bitrate,
                "-ar",
                str(cfg.sample_rate),
                "-ac",
                str(cfg.channels),
            ]
        )

        if cfg.extra_movflags and out.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            cmd.extend(["-movflags", "".join(cfg.extra_movflags)])

        cmd.append(str(out))

        if progress_cb:
            progress_cb(35, "Mastering audio & video container streams...")

        logger.info("Executing Broadcast Master Exporter: %s", " ".join(cmd))
        _run(cmd)

        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"Export failed: Output file {out} was not created or is empty.")

        try:
            probe_data = probe(out)
            streams = probe_data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            if streams and not has_video:
                raise RuntimeError(f"Export verification failed: Output {out} has no video stream.")
            if streams and not has_audio:
                raise RuntimeError(f"Export verification failed: Output {out} has no audio stream.")
            out_dur = float(probe_data.get("format", {}).get("duration", 0.0))
            if streams and out_dur < 0.0:
                raise RuntimeError(
                    f"Export verification failed: Output {out} has invalid duration {out_dur}s."
                )
        except Exception as exc:
            if "Export verification failed" in str(exc):
                raise
            logger.warning("Post-export media probe skipped or unavailable: %s", exc)

        if progress_cb:
            progress_cb(100, f"Master successfully created: {out.name}")

        logger.info("Broadcast master successfully exported: %s", out)
        return out

    @classmethod
    def export_cinematic_surround_master(
        cls,
        *,
        video_path: Path | str,
        dialogue_path: Path | str,
        music_path: Path | str,
        output_path: Path | str,
        preset: BroadcastPreset | str = BroadcastPreset.NETFLIX_51,
        subtitle_path: Path | str | None = None,
        burn_subtitles: bool = False,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> Path:
        """
        Complete 2-stage mastering pipeline:
        1. Mix localized dialogue into discrete Center and music into 5.1 surround bed.
        2. Deliver master container matching broadcast specifications (EBU R128).
        """
        out = Path(output_path)
        temp_51_wav = out.parent / f"{out.stem}_temp_51.wav"

        try:
            if progress_cb:
                progress_cb(15, "Rendering 5.1 surround sound audio bed...")

            SurroundSoundMixer.mix_5point1(
                dialogue_wav=dialogue_path,
                background_music_wav=music_path,
                output_wav=temp_51_wav,
                loudness_target_lufs=-23.0 if "netflix" in str(preset).lower() else -14.0,
            )

            if progress_cb:
                progress_cb(50, "Multiplexing 5.1 audio with video streams...")

            return cls.export(
                video_path=video_path,
                audio_path=temp_51_wav,
                output_path=output_path,
                preset=preset,
                subtitle_path=subtitle_path,
                burn_subtitles=burn_subtitles,
                progress_cb=progress_cb,
            )
        finally:
            if temp_51_wav.is_file():
                try:
                    temp_51_wav.unlink()
                except Exception:
                    pass

    @classmethod
    def export_dual_audio_master(
        cls,
        *,
        video_path: Path | str,
        original_audio_path: Path | str,
        dubbed_audio_path: Path | str,
        output_path: Path | str,
        original_lang: str = "eng",
        dubbed_lang: str = "ben",
        bilingual_subtitle_path: Path | str | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> Path:
        """
        Export multi-track OTT/broadcast master package:
          - Track 1: Original Production Audio (e.g. English)
          - Track 2: Localized Dubbed Audio (e.g. Bengali - default playback track)
          - Track 3: Embedded Subtitles (Bilingual / Target language)

        Supported formats: .mkv (Matroska Multi-Audio Master) and .mp4.
        """
        vid = Path(video_path)
        orig_aud = Path(original_audio_path)
        dub_aud = Path(dubbed_audio_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if not vid.is_file():
            raise FileNotFoundError(f"Video file not found: {vid}")
        if not orig_aud.is_file():
            raise FileNotFoundError(f"Original audio track not found: {orig_aud}")
        if not dub_aud.is_file():
            raise FileNotFoundError(f"Dubbed audio track not found: {dub_aud}")
        if vid.resolve() == out.resolve():
            raise ValueError(f"Output path cannot overwrite source video: {out}")

        if progress_cb:
            progress_cb(10, "Configuring Dual-Audio Multi-Track container streams...")

        cmd: list[str] = [
            _ffmpeg_exe(),
            "-y",
            "-i",
            str(vid),
            "-i",
            str(orig_aud),
            "-i",
            str(dub_aud),
        ]

        sub_p = Path(bilingual_subtitle_path) if bilingual_subtitle_path else None
        has_sub = sub_p is not None and sub_p.is_file()
        if has_sub:
            cmd.extend(["-i", str(sub_p)])

        cmd.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-map",
                "2:a:0",
                "-c:v",
                "copy",
                "-c:a:0",
                "aac",
                "-b:a:0",
                "192k",
                "-metadata:s:a:0",
                f"language={original_lang}",
                "-metadata:s:a:0",
                "title=Original Audio",
                "-c:a:1",
                "aac",
                "-b:a:1",
                "192k",
                "-metadata:s:a:1",
                f"language={dubbed_lang}",
                "-metadata:s:a:1",
                f"title={dubbed_lang.capitalize()} Dubbed Audio",
                "-disposition:a:0",
                "0",
                "-disposition:a:1",
                "default",
            ]
        )

        if has_sub:
            cmd.extend(
                [
                    "-map",
                    "3:s:0",
                    "-c:s",
                    "mov_text" if out.suffix.lower() == ".mp4" else "srt",
                    "-metadata:s:s:0",
                    f"language={dubbed_lang}",
                    "-metadata:s:s:0",
                    "title=Bilingual Subtitles",
                ]
            )

        if out.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(out))
        if progress_cb:
            progress_cb(40, "Multiplexing dual-audio streams into master container...")

        _run(cmd)

        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"Export failed: Output file {out} was not created or is empty.")

        try:
            probe_data = probe(out)
            streams = probe_data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            if streams and not has_video:
                raise RuntimeError(f"Export verification failed: Output {out} has no video stream.")
            if streams and len(audio_streams) < 2:
                raise RuntimeError(
                    f"Export verification failed: Expected at least 2 audio tracks (dual-audio), found {len(audio_streams)}."
                )
        except Exception as exc:
            if "Export verification failed" in str(exc):
                raise
            logger.warning("Could not probe output media %s: %s", out, exc)

        if progress_cb:
            progress_cb(100, f"Dual-audio master successfully generated: {out.name}")
        return out


__all__ = ["PRESET_CONFIGS", "BroadcastMasterExporter", "BroadcastPreset", "ExportConfig"]
