"""Unit tests for DubbingEngineWorker thread and output management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aidub.ui.workers import DubbingEngineWorker


def test_dubbing_engine_worker_available_output_path(tmp_path: Path):
    in_video = tmp_path / "movie.mp4"
    in_video.touch()

    worker = DubbingEngineWorker(
        input_path=in_video,
        target_lang="bn",
        quality_profile="quality",
    )

    out_p = worker._available_output_path()
    assert out_p.parent == tmp_path
    assert "movie_dubbed_bn.mp4" in out_p.name

    # If base exists, it should append revision number
    out_p.touch()
    revised_p = worker._available_output_path()
    assert revised_p.name == "movie_dubbed_bn_02.mp4"


def test_dubbing_engine_worker_initialization_and_run(tmp_path: Path):
    in_video = tmp_path / "movie.mp4"
    in_video.touch()

    worker = DubbingEngineWorker(
        input_path=in_video,
        target_lang="bn",
        quality_profile="fast",
        voice_name="bn-BD-PradeepNeural",
        character_voices={"SPEAKER_00": "bn-BD-PradeepNeural"},
        lipsync=True,
    )

    completed_signals = []
    worker.dubbing_completed.connect(completed_signals.append)

    mock_outputs = MagicMock()
    mock_outputs.dubbed_video = tmp_path / "dubbed_final.mp4"
    mock_outputs.dubbed_audio = tmp_path / "dubbed.wav"
    mock_outputs.bilingual_srt = tmp_path / "sub.srt"
    mock_outputs.target_srt = tmp_path / "target.srt"
    mock_outputs.transcript_json = tmp_path / "trans.json"
    mock_outputs.lipsynced_video = ""

    with patch("aidub.pipeline.engine.DubbingEngine") as mock_engine_cls:
        mock_instance = MagicMock()
        mock_instance.run.return_value = mock_outputs
        mock_instance.work_dir = tmp_path / "work"
        mock_engine_cls.return_value = mock_instance

        # Run synchronously in test
        worker.run()

        assert len(completed_signals) == 1
        res = completed_signals[0]
        assert res["output_file"] == str(tmp_path / "dubbed_final.mp4")
        assert res["work_dir"] == str(tmp_path / "work")

        # Verify PipelineConfig was initialized with fast=True and lipsync=False (fast overrides lipsync)
        call_args = mock_engine_cls.call_args
        cfg = call_args[0][0]
        assert cfg.fast is True
        assert cfg.lipsync is False
        assert cfg.keep_music is False
        assert cfg.diarize is False
        assert cfg.character_voices == {"SPEAKER_00": "bn-BD-PradeepNeural"}
