"""Typed FFprobe wrapper with bounded resource use."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .runtime import MediaRuntime


class MediaProbeError(RuntimeError):
    def __init__(self, code: str, message: str, *, stderr: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.stderr = stderr[-8_192:]


@dataclass(frozen=True, slots=True)
class VideoStreamInfo:
    index: int
    codec: str
    width: int
    height: int
    average_frame_rate: Fraction | None
    real_frame_rate: Fraction | None
    time_base: Fraction | None
    pixel_format: str | None
    color_range: str | None
    color_space: str | None
    color_transfer: str | None
    color_primaries: str | None
    sample_aspect_ratio: str | None
    field_order: str | None
    rotation_degrees: int | None
    start_ticks: int | None
    duration_ticks: int | None

    @property
    def likely_variable_frame_rate(self) -> bool:
        if self.average_frame_rate is None or self.real_frame_rate is None:
            return False
        return self.average_frame_rate != self.real_frame_rate


@dataclass(frozen=True, slots=True)
class AudioStreamInfo:
    index: int
    codec: str
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    language: str | None
    time_base: Fraction | None
    start_ticks: int | None
    duration_ticks: int | None


@dataclass(frozen=True, slots=True)
class SubtitleStreamInfo:
    index: int
    codec: str
    language: str | None
    title: str | None
    time_base: Fraction | None
    forced: bool
    hearing_impaired: bool


@dataclass(frozen=True, slots=True)
class ContainerInfo:
    path: Path
    format_names: tuple[str, ...]
    duration_seconds: float | None
    bit_rate: int | None
    size_bytes: int
    video_streams: tuple[VideoStreamInfo, ...]
    audio_streams: tuple[AudioStreamInfo, ...]
    subtitle_streams: tuple[SubtitleStreamInfo, ...]
    chapters: int


def _fraction(value: Any) -> Fraction | None:
    if value in (None, "", "0/0", "N/A"):
        return None
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return result if result.denominator else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


class MediaProbe:
    def __init__(
        self,
        runtime: MediaRuntime | None = None,
        *,
        timeout_seconds: float = 30.0,
        maximum_output_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if maximum_output_bytes < 1024:
            raise ValueError("maximum_output_bytes is too small")
        self.runtime = runtime or MediaRuntime()
        self.timeout_seconds = timeout_seconds
        self.maximum_output_bytes = maximum_output_bytes

    def probe(self, source: Path | str) -> ContainerInfo:
        source_path = Path(source).expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise MediaProbeError("media.not_file", f"source is not a file: {source_path}")
        try:
            runtime = self.runtime.inspect()
        except (FileNotFoundError, RuntimeError) as exc:
            raise MediaProbeError(
                "media.ffprobe_unavailable",
                "FFprobe is required to inspect real media metadata",
            ) from exc

        command = [
            str(runtime.ffprobe),
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            str(source_path),
        ]
        try:
            # The executable is resolved to an existing local file and arguments
            # are passed as a sequence; no shell parsing is involved.
            process = subprocess.run(  # noqa: S603
                command,
                check=False,
                capture_output=True,
                timeout=self.timeout_seconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaProbeError(
                "media.probe_timeout",
                f"media probe exceeded {self.timeout_seconds:g} seconds",
            ) from exc
        if len(process.stdout) > self.maximum_output_bytes:
            raise MediaProbeError(
                "media.probe_output_too_large",
                "media metadata exceeded the configured safe limit",
            )
        stderr = process.stderr.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise MediaProbeError(
                "media.probe_failed",
                f"ffprobe failed with exit code {process.returncode}",
                stderr=stderr,
            )
        try:
            payload = json.loads(process.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MediaProbeError(
                "media.probe_invalid_json",
                "ffprobe returned invalid metadata",
                stderr=stderr,
            ) from exc
        return self._parse(source_path, payload)

    @staticmethod
    def _parse(source_path: Path, payload: dict[str, Any]) -> ContainerInfo:
        videos: list[VideoStreamInfo] = []
        audios: list[AudioStreamInfo] = []
        subtitles: list[SubtitleStreamInfo] = []
        for stream in payload.get("streams", []):
            kind = stream.get("codec_type")
            tags = stream.get("tags") or {}
            if kind == "video":
                side_data = stream.get("side_data_list") or []
                rotation = next(
                    (
                        _optional_int(item.get("rotation"))
                        for item in side_data
                        if item.get("rotation") is not None
                    ),
                    None,
                )
                videos.append(
                    VideoStreamInfo(
                        index=int(stream["index"]),
                        codec=str(stream.get("codec_name") or "unknown"),
                        width=int(stream.get("width") or 0),
                        height=int(stream.get("height") or 0),
                        average_frame_rate=_fraction(stream.get("avg_frame_rate")),
                        real_frame_rate=_fraction(stream.get("r_frame_rate")),
                        time_base=_fraction(stream.get("time_base")),
                        pixel_format=stream.get("pix_fmt"),
                        color_range=stream.get("color_range"),
                        color_space=stream.get("color_space"),
                        color_transfer=stream.get("color_transfer"),
                        color_primaries=stream.get("color_primaries"),
                        sample_aspect_ratio=stream.get("sample_aspect_ratio"),
                        field_order=stream.get("field_order"),
                        rotation_degrees=rotation,
                        start_ticks=_optional_int(stream.get("start_pts")),
                        duration_ticks=_optional_int(stream.get("duration_ts")),
                    )
                )
            elif kind == "audio":
                audios.append(
                    AudioStreamInfo(
                        index=int(stream["index"]),
                        codec=str(stream.get("codec_name") or "unknown"),
                        sample_rate=_optional_int(stream.get("sample_rate")),
                        channels=_optional_int(stream.get("channels")),
                        channel_layout=stream.get("channel_layout"),
                        language=tags.get("language"),
                        time_base=_fraction(stream.get("time_base")),
                        start_ticks=_optional_int(stream.get("start_pts")),
                        duration_ticks=_optional_int(stream.get("duration_ts")),
                    )
                )
            elif kind == "subtitle":
                subtitles.append(
                    SubtitleStreamInfo(
                        index=int(stream["index"]),
                        codec=str(stream.get("codec_name") or "unknown"),
                        language=tags.get("language"),
                        title=tags.get("title"),
                        time_base=_fraction(stream.get("time_base")),
                        forced=bool((stream.get("disposition") or {}).get("forced", 0)),
                        hearing_impaired=bool(
                            (stream.get("disposition") or {}).get("hearing_impaired", 0)
                        ),
                    )
                )
        container = payload.get("format") or {}
        return ContainerInfo(
            path=source_path,
            format_names=tuple(
                part for part in str(container.get("format_name") or "").split(",") if part
            ),
            duration_seconds=_optional_float(container.get("duration")),
            bit_rate=_optional_int(container.get("bit_rate")),
            size_bytes=source_path.stat().st_size,
            video_streams=tuple(videos),
            audio_streams=tuple(audios),
            subtitle_streams=tuple(subtitles),
            chapters=len(payload.get("chapters") or []),
        )
