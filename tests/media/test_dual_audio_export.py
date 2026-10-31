"""Unit tests for Multi-Track Dual-Audio Broadcast Exporter."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from aidub.media.broadcast_exporter import BroadcastMasterExporter
from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, probe


def _create_test_clip(path: Path, duration_s: float = 1.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=320x240:d={duration_s}:r=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )
    return path


def _create_test_audio(path: Path, freq: float = 440.0, duration_s: float = 1.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        frames = bytearray()
        for i in range(int(duration_s * 44100)):
            v = int(10000 * math.sin(2 * math.pi * freq * (i / 44100)))
            frames.extend(struct.pack("<hh", v, v))
        wf.writeframes(frames)
    return path


def test_dual_audio_master_export(tmp_path: Path) -> None:
    vid = _create_test_clip(tmp_path / "video.mp4", duration_s=1.0)
    orig_audio = _create_test_audio(tmp_path / "orig_audio.wav", freq=300.0, duration_s=1.0)
    dub_audio = _create_test_audio(tmp_path / "dub_audio.wav", freq=600.0, duration_s=1.0)

    # Subtitle file
    sub_file = tmp_path / "subs.srt"
    sub_file.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello World\nহ্যালো বিশ্ব\n", encoding="utf-8"
    )

    out_mkv = tmp_path / "dual_master.mkv"

    exported = BroadcastMasterExporter.export_dual_audio_master(
        video_path=vid,
        original_audio_path=orig_audio,
        dubbed_audio_path=dub_audio,
        output_path=out_mkv,
        original_lang="eng",
        dubbed_lang="ben",
        bilingual_subtitle_path=sub_file,
    )

    assert exported.is_file()
    assert exported.stat().st_size > 0

    info = probe(exported)
    streams = info["streams"]

    # Verify video stream
    v_streams = [s for s in streams if s["codec_type"] == "video"]
    assert len(v_streams) == 1

    # Verify 2 audio streams (Track 1 = original, Track 2 = dubbed)
    a_streams = [s for s in streams if s["codec_type"] == "audio"]
    assert len(a_streams) == 2


def test_dual_audio_missing_file_raises_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BroadcastMasterExporter.export_dual_audio_master(
            video_path=tmp_path / "no_vid.mp4",
            original_audio_path=tmp_path / "no_orig.wav",
            dubbed_audio_path=tmp_path / "no_dub.wav",
            output_path=tmp_path / "out.mkv",
        )
