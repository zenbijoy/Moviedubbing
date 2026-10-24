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
