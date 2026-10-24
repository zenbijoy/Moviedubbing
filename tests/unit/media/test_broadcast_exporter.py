"""Unit tests for Broadcast Master Delivery Exporter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from aidub.media.broadcast_exporter import (
    PRESET_CONFIGS,
    BroadcastMasterExporter,
    BroadcastPreset,
)


def test_preset_specifications():
    assert BroadcastPreset.YOUTUBE_4K in PRESET_CONFIGS
    assert BroadcastPreset.NETFLIX_51 in PRESET_CONFIGS

    netflix_cfg = PRESET_CONFIGS[BroadcastPreset.NETFLIX_51]
    assert netflix_cfg.channels == 6
    assert netflix_cfg.loudness_lufs == -23.0
    assert netflix_cfg.audio_codec == "ac3"

    yt_cfg = PRESET_CONFIGS[BroadcastPreset.YOUTUBE_4K]
    assert yt_cfg.channels == 2
    assert yt_cfg.loudness_lufs == -14.0
    assert yt_cfg.audio_codec == "aac"


def test_broadcast_export_invokes_ffmpeg(tmp_path: Path):
    vid = tmp_path / "video.mp4"
    vid.write_bytes(b"dummy video")
    aud = tmp_path / "audio.wav"
    aud.write_bytes(b"dummy audio")
    out = tmp_path / "master.mp4"

    recorded_cmds: list[list[str]] = []

    def fake_run(cmd: list[str]):
        recorded_cmds.append(cmd)
        out.write_bytes(b"dummy master mp4")
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("aidub.media.broadcast_exporter._run", side_effect=fake_run):
        res = BroadcastMasterExporter.export(
            video_path=vid,
            audio_path=aud,
            output_path=out,
            preset=BroadcastPreset.NETFLIX_51,
        )

    assert res == out
    assert len(recorded_cmds) == 1
    cmd = recorded_cmds[0]
    assert "-c:a" in cmd
    a_idx = cmd.index("-c:a")
    assert cmd[a_idx + 1] == "ac3"
    assert "+faststart" in cmd


def test_broadcast_export_with_burned_subtitles(tmp_path: Path):
    vid = tmp_path / "video.mp4"
    vid.write_bytes(b"dummy video")
    aud = tmp_path / "audio.wav"
    aud.write_bytes(b"dummy audio")
    sub = tmp_path / "subs.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello", encoding="utf-8")
    out = tmp_path / "master_subbed.mp4"

    recorded_cmds: list[list[str]] = []

    def fake_run(cmd: list[str]):
        recorded_cmds.append(cmd)
        out.write_bytes(b"dummy master")
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("aidub.media.broadcast_exporter._run", side_effect=fake_run):
        BroadcastMasterExporter.export(
            video_path=vid,
            audio_path=aud,
            output_path=out,
            preset=BroadcastPreset.YOUTUBE_4K,
            subtitle_path=sub,
            burn_subtitles=True,
        )

    assert len(recorded_cmds) == 1
    cmd = recorded_cmds[0]
    # In burn subtitles, -vf subtitles=... should be included
    assert "-vf" in cmd
    vf_idx = cmd.index("-vf")
    assert "subtitles=" in cmd[vf_idx + 1]
