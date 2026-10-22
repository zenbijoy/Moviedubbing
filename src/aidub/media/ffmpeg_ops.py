"""FFmpeg and FFprobe subprocess wrappers — robust media I/O for dubbing pipeline."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _ffmpeg_exe() -> str:
    """
    Return the path to a working ffmpeg binary.

    Resolution order:
      1. imageio-ffmpeg bundled binary (no PATH dependency, always works)
      2. System PATH ffmpeg (fallback for CI / server environments)

    Raises RuntimeError if neither is found.
    """
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(exe).is_file():
            return exe
    except Exception:
        pass
    # Fallback: system PATH
    sys_exe = shutil.which("ffmpeg")
    if sys_exe:
        return sys_exe
    raise RuntimeError(
        "ffmpeg not found. Install imageio-ffmpeg (uv add imageio-ffmpeg) "
        "or add ffmpeg to your system PATH (https://ffmpeg.org/download.html)."
    )


def _ffprobe_exe() -> str | None:
    """
    Return the path to a working ffprobe binary, or None if unavailable.

    imageio-ffmpeg only ships ffmpeg on Windows (not ffprobe), so this may
    return None. Callers must fall back to ffmpeg-based probing in that case.
    """
    # Check imageio-ffmpeg binary directory for a co-located ffprobe
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]

        ffmpeg_dir = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent
        for candidate in ffmpeg_dir.iterdir():
            if "ffprobe" in candidate.name.lower() and candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    # System PATH ffprobe
    return shutil.which("ffprobe")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute FFmpeg/FFprobe command with error handling."""
    logger.debug("Executing media command: %s", " ".join(cmd))
    p = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if p.returncode != 0:
        err = p.stderr[-2000:] if p.stderr else p.stdout[-2000:]
        raise RuntimeError(f"FFmpeg failed [exit {p.returncode}]: {' '.join(cmd)}\n{err}")
    return p


def probe(path: Path | str) -> dict[str, Any]:
    """Read container metadata without decoding the media payload."""
    import re

    media_path = Path(path)
    if not media_path.is_file():
        raise FileNotFoundError(f"media file does not exist: {media_path}")

    ffprobe = _ffprobe_exe()
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-nostdin",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe could not read {media_path}: {result.stderr[-2_000:]}")
        return json.loads(result.stdout)

    # FFmpeg reports stream headers when opening an input. Decoding to a null
    # muxer here would make importing a feature film take as long as playing it.
    result = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(media_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    diagnostic = result.stderr
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", diagnostic)
    if duration_match is None:
        raise RuntimeError(
            f"FFmpeg could not read media metadata for {media_path}: {diagnostic[-2_000:]}"
        )
    hours, minutes, seconds = duration_match.groups()
    duration_s = int(hours) * 3_600 + int(minutes) * 60 + float(seconds)

    stream_pattern = re.compile(
        r"Stream #\d+:(\d+)(?:\[[^]]+\])?(?:\([^)]*\))?:\s*"
        r"(Video|Audio|Subtitle|Data|Attachment):\s*([^,\s]+)"
    )
    streams: list[dict[str, Any]] = []
    for line in diagnostic.splitlines():
        match = stream_pattern.search(line)
        if match is None:
            continue
        index, stream_type, codec_name = match.groups()
        stream: dict[str, Any] = {
            "index": int(index),
            "codec_type": stream_type.lower(),
            "codec_name": codec_name.lower(),
        }
        if stream_type.lower() == "video":
            dimensions = re.search(r"\b(\d{2,6})x(\d{2,6})\b", line)
            if dimensions:
                stream["width"], stream["height"] = map(int, dimensions.groups())
            fps_match = re.search(r"\b(\d+(?:\.\d+)?)\s*fps\b", line) or re.search(
                r"\b(\d+(?:\.\d+)?)\s*tbr\b", line
            )
            if fps_match:
                fps_num = float(fps_match.group(1))
                stream["fps"] = fps_num
                stream["avg_frame_rate"] = (
                    f"{int(fps_num)}/1" if fps_num.is_integer() else f"{fps_num}"
                )
        elif stream_type.lower() == "audio":
            sample_rate = re.search(r"\b(\d{4,6}) Hz\b", line)
            if sample_rate:
                stream["sample_rate"] = sample_rate.group(1)
            channel_layout = re.search(
                r"\b(mono|stereo|[2-9]\.\d(?:\([^)]*\))?|\d+ channels?)\b",
                line,
            )
            if channel_layout:
                layout = channel_layout.group(1).lower()
                if layout == "mono":
                    stream["channels"] = 1
                elif layout == "stereo":
                    stream["channels"] = 2
                elif layout.endswith(("channel", "channels")):
                    stream["channels"] = int(layout.split()[0])
                else:
                    layout_base = layout.split("(", maxsplit=1)[0]
                    whole, fraction = layout_base.split(".", maxsplit=1)
                    stream["channels"] = int(whole) + (1 if fraction == "1" else 0)
        streams.append(stream)

    if not streams:
        raise RuntimeError(f"FFmpeg found no media streams in {media_path}")

    format_match = re.search(r"Input #\d+,\s*([^,\s]+)", diagnostic)
    bitrate_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", diagnostic)
    return {
        "format": {
            "filename": str(media_path),
            "duration": str(duration_s),
            "size": str(media_path.stat().st_size),
            "bit_rate": str(int(bitrate_match.group(1)) * 1_000) if bitrate_match else "0",
            "format_name": format_match.group(1) if format_match else media_path.suffix.lstrip("."),
        },
        "streams": streams,
    }


def duration(path: Path | str) -> float:
    """Return the measured duration of an audio or video file."""
    try:
        meta = probe(path)
        return float(meta["format"]["duration"])
    except Exception:
        # Fallback for WAV files when ffprobe is not installed/on PATH
        try:
            import wave

            with wave.open(str(path), "rb") as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except Exception as wav_exc:
            raise RuntimeError(f"unable to measure media duration: {path}") from wav_exc


def extract_audio(
    video_path: Path | str, wav_path: Path | str, sr: int = 44100, ac: int = 2
) -> Path:
    """Extract full-quality audio track from video file."""
    wav_p = Path(wav_path)
    _run(
        [
            _ffmpeg_exe(),
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            str(ac),
            "-ar",
            str(sr),
            str(wav_p),
        ]
    )
    return wav_p


def to_16k_mono(src_path: Path | str, dst_path: Path | str) -> Path:
    """Convert audio file to 16kHz mono WAV (standard for ASR & diarization)."""
    dst_p = Path(dst_path)
    _run([_ffmpeg_exe(), "-y", "-i", str(src_path), "-vn", "-ac", "1", "-ar", "16000", str(dst_p)])
    return dst_p


def _atempo_chain(factor: float) -> str:
    """
    Build chained FFmpeg atempo audio filter for any factor.

    FFmpeg atempo accepts values between 0.5 and 2.0 per instance.
    For factors > 2.0 or < 0.5, multiple instances are chained together.
    """
    parts: list[str] = []
    f = factor
    while f > 2.0:
        parts.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        parts.append("atempo=0.5")
        f /= 0.5
    parts.append(f"atempo={f:.6f}")
    return ",".join(parts)


def time_stretch(src_path: Path | str, dst_path: Path | str, factor: float) -> Path:
    """
    Time-stretch audio file without altering pitch.

    factor > 1.0 speeds up (shortens duration).
    factor < 1.0 slows down (lengthens duration).
    Outputs 44.1kHz mono 16-bit PCM WAV.
    """
    dst_p = Path(dst_path)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if abs(factor - 1.0) < 0.001:
        # Near 1.0 ratio, reformat to standard 44.1kHz PCM
        _run(
            [
                _ffmpeg_exe(),
                "-y",
                "-i",
                str(src_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(dst_p),
            ]
        )
    else:
        chain = _atempo_chain(factor)
        _run(
            [
                _ffmpeg_exe(),
                "-y",
                "-i",
                str(src_path),
                "-filter:a",
                chain,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(dst_p),
            ]
        )
    return dst_p


def mix(
    voice_path: Path | str, music_path: Path | str, out_path: Path | str, music_gain: float = 0.30
) -> Path:
    """
    Mix dubbed vocal track over ducked background music track with professional loudness control.

    Ensures vocal priority (gain 1.4x), ducks music, avoids phase/clipping artifacts via alimiter,
    and encodes matching the destination file extension (.wav -> pcm_s16le, .mp3 -> mp3, .m4a -> aac).
    """
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_p.suffix.lower()

    fc = (
        "[0:a]aformat=channel_layouts=stereo,volume=1.4[v];"
        f"[1:a]aformat=channel_layouts=stereo,volume={music_gain:.2f}[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=0:weights=1 {music_gain:.2f}:normalize=0[mix];"
        "[mix]alimiter=limit=0.95:level=true[out]"
    )

    cmd = [
        _ffmpeg_exe(),
        "-y",
        "-i",
        str(voice_path),
        "-i",
        str(music_path),
        "-filter_complex",
        fc,
        "-map",
        "[out]",
    ]

    if suffix == ".wav":
        cmd.extend(["-c:a", "pcm_s16le", "-ar", "44100"])
    elif suffix == ".mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100"])

    cmd.append(str(out_p))
    _run(cmd)
    return out_p


def mux(video_path: Path | str, audio_path: Path | str, out_path: Path | str) -> Path:
    """
    Combine original video stream (stream copy) with new dubbed audio track.

    Uses -movflags +faststart for instant playback across all players and browsers,
    and encodes audio track with 192k 44.1kHz stereo AAC.
    """
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg_exe(),
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(out_p),
        ]
    )
    return out_p


def trim(
    src_path: Path | str, dst_path: Path | str, start_s: float, end_s: float, sr: int = 16000
) -> Path:
    """Trim audio slice between start_s and end_s timestamps."""
    dst_p = Path(dst_path)
    _run(
        [
            _ffmpeg_exe(),
            "-y",
            "-ss",
            f"{start_s:.3f}",
            "-to",
            f"{end_s:.3f}",
            "-i",
            str(src_path),
            "-ac",
            "1",
            "-ar",
            str(sr),
            str(dst_p),
        ]
    )
    return dst_p


__all__ = [
    "_ffmpeg_exe",
    "_ffprobe_exe",
    "duration",
    "extract_audio",
    "mix",
    "mux",
    "probe",
    "time_stretch",
    "to_16k_mono",
    "trim",
]
