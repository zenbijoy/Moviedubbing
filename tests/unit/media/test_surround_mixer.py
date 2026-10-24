"""Unit tests for 5.1 Cinematic Surround Sound Remixer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from aidub.media.surround_mixer import SurroundSoundMixer


def test_surround_mixer_missing_dialogue_raises():
    with pytest.raises(FileNotFoundError):
        SurroundSoundMixer.mix_5point1("non_existent_dialogue.wav", "music.wav", "out.wav")


def test_surround_mixer_runs_ffmpeg_with_channel_mapping(tmp_path: Path):
    dia = tmp_path / "dia.wav"
    dia.write_bytes(b"RIFF dummy dialogue")
    bg = tmp_path / "bg.wav"
    bg.write_bytes(b"RIFF dummy music")
    out = tmp_path / "out_51.wav"

    recorded_cmds: list[list[str]] = []

    def fake_run(cmd: list[str]):
        recorded_cmds.append(cmd)
        out.write_bytes(b"RIFF dummy 5.1 output")
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("aidub.media.surround_mixer._run", side_effect=fake_run), \
         patch("aidub.media.surround_mixer.duration", return_value=12.5):
        result = SurroundSoundMixer.mix_5point1(
            dialogue_wav=dia,
            background_music_wav=bg,
            output_wav=out,
            loudness_target_lufs=-23.0,
        )

    assert result == out
    assert len(recorded_cmds) == 1
    cmd = recorded_cmds[0]
    # Verify 6-channel output and loudnorm filter
    assert "-ac" in cmd
    ac_idx = cmd.index("-ac")
    assert cmd[ac_idx + 1] == "6"
    assert any("pan=5.1" in arg for arg in cmd)
    assert any("loudnorm=I=-23.0" in arg for arg in cmd)


def test_real_5point1_mixing_mono_dialogue_stereo_music(tmp_path: Path):
    import math
    import struct
    import wave
    from aidub.media.ffmpeg_ops import probe

    # 1. Create real mono dialogue
    dia = tmp_path / "dia_mono.wav"
    with wave.open(str(dia), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        frames = bytearray()
        for i in range(44100):
            v = int(12000 * math.sin(2 * math.pi * 500 * (i / 44100)))
            frames.extend(struct.pack("<h", v))
        wf.writeframes(frames)

    # 2. Create real stereo music
    bg = tmp_path / "bg_stereo.wav"
    with wave.open(str(bg), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        frames = bytearray()
        for i in range(48000):
            v = int(6000 * math.sin(2 * math.pi * 220 * (i / 48000)))
            frames.extend(struct.pack("<hh", v, v))
        wf.writeframes(frames)

    out_51 = tmp_path / "out_51_real.wav"
    res = SurroundSoundMixer.mix_5point1(dia, bg, out_51)

    assert res.is_file()
    assert res.stat().st_size > 0
    info = probe(res)
    audio_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert audio_stream["channels"] == 6

