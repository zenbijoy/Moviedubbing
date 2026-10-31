"""Media metadata probes must not decode an entire source movie."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aidub.media import ffmpeg_ops


def test_ffmpeg_header_probe_does_not_decode_media(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "feature.mp4"
    source.write_bytes(b"container header fixture")
    commands: list[list[str]] = []
    diagnostic = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'feature.mp4':
  Duration: 02:28:08.00, start: 0.000000, bitrate: 800 kb/s
    Stream #0:0(und): Video: hevc (Main), yuv420p, 850x480, 23.98 fps
    Stream #0:1(eng): Audio: aac (LC), 48000 Hz, stereo, fltp
"""

    monkeypatch.setattr(ffmpeg_ops, "_ffprobe_exe", lambda: None)
    monkeypatch.setattr(ffmpeg_ops, "_ffmpeg_exe", lambda: "ffmpeg")

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, "", diagnostic)

    monkeypatch.setattr(ffmpeg_ops.subprocess, "run", run)

    info = ffmpeg_ops.probe(source)

    assert float(info["format"]["duration"]) == 8_888.0
    assert [stream["codec_type"] for stream in info["streams"]] == ["video", "audio"]
    assert info["streams"][0]["width"] == 850
    assert info["streams"][0]["height"] == 480
    assert "-f" not in commands[0]
    assert "-i" in commands[0]
