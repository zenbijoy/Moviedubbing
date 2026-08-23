"""FFmpeg and FFprobe subprocess wrappers — robust media I/O for dubbing pipeline."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute FFmpeg/FFprobe command with error handling."""
    logger.debug("Executing media command: %s", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        err = p.stderr[-2000:] if p.stderr else p.stdout[-2000:]
        raise RuntimeError(f"FFmpeg failed [exit {p.returncode}]: {' '.join(cmd)}\n{err}")
    return p


def probe(path: Path | str) -> dict[str, Any]:
    """Run ffprobe on input media file and return streams and format metadata."""
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


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


def extract_audio(video_path: Path | str, wav_path: Path | str, sr: int = 44100, ac: int = 2) -> Path:
    """Extract full-quality audio track from video file."""
    wav_p = Path(wav_path)
    _run(["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", str(ac), "-ar", str(sr), str(wav_p)])
    return wav_p


def to_16k_mono(src_path: Path | str, dst_path: Path | str) -> Path:
    """Convert audio file to 16kHz mono WAV (standard for ASR & diarization)."""
    dst_p = Path(dst_path)
    _run(["ffmpeg", "-y", "-i", str(src_path), "-vn", "-ac", "1", "-ar", "16000", str(dst_p)])
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
    """
    dst_p = Path(dst_path)
    if abs(factor - 1.0) < 0.001:
        # Near 1.0 ratio, simple copy
        _run(["ffmpeg", "-y", "-i", str(src_path), str(dst_p)])
    else:
        chain = _atempo_chain(factor)
        _run(["ffmpeg", "-y", "-i", str(src_path), "-filter:a", chain, str(dst_p)])
    return dst_p


def mix(voice_path: Path | str, music_path: Path | str, out_path: Path | str, music_gain: float = 0.45) -> Path:
    """
    Mix dubbed vocal track over ducked background music track.
    
    music_gain default 0.45 (-7dB) ensures background music never drowns speech.
    """
    out_p = Path(out_path)
    fc = f"[1:a]volume={music_gain:.2f}[m];[0:a][m]amix=inputs=2:duration=longest:dropout_transition=0"
    _run([
        "ffmpeg", "-y",
        "-i", str(voice_path),
        "-i", str(music_path),
        "-filter_complex", fc,
        "-c:a", "aac", "-b:a", "192k",
        str(out_p),
    ])
    return out_p


def mux(video_path: Path | str, audio_path: Path | str, out_path: Path | str) -> Path:
    """
    Combine original video stream (stream copy) with new dubbed audio track.
    
    Does NOT use -shortest to prevent truncating video tail if dubbed audio is brief.
    """
    out_p = Path(out_path)
    _run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "copy",
        "-c:a", "aac",
        str(out_p),
    ])
    return out_p


def trim(src_path: Path | str, dst_path: Path | str, start_s: float, end_s: float, sr: int = 16000) -> Path:
    """Trim audio slice between start_s and end_s timestamps."""
    dst_p = Path(dst_path)
    _run([
        "ffmpeg", "-y",
        "-ss", f"{start_s:.3f}",
        "-to", f"{end_s:.3f}",
        "-i", str(src_path),
        "-ac", "1",
        "-ar", str(sr),
        str(dst_p),
    ])
    return dst_p


__all__ = [
    "duration",
    "extract_audio",
    "mix",
    "mux",
    "probe",
    "time_stretch",
    "to_16k_mono",
    "trim",
]
