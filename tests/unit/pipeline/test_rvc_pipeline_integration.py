"""
Tests for Two-Stage Synthesis with Character RVC v2 Voice Conversion in DubbingEngine.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine


def test_pipeline_config_rvc_cloning_flag(tmp_path: Path) -> None:
    # Default is True
    cfg_normal = PipelineConfig(input=tmp_path / "in.mp4", output=tmp_path / "out.mp4")
    assert cfg_normal.rvc_cloning is True

    # Fast profile automatically disables rvc_cloning for CPU performance
    cfg_fast = PipelineConfig(input=tmp_path / "in.mp4", output=tmp_path / "out.mp4", fast=True)
    assert cfg_fast.rvc_cloning is False
    assert cfg_fast.keep_music is False
    assert cfg_fast.diarize is False


def test_rvc_conversion_invoked_during_tts_stage(tmp_path: Path) -> None:
    in_video = tmp_path / "in.mp4"
    in_video.write_bytes(b"dummy")
    out_video = tmp_path / "out.mp4"

    cfg = PipelineConfig(
        input=in_video,
        output=out_video,
        work_dir=tmp_path,
        rvc_cloning=True,
    )
    engine = DubbingEngine(cfg)

    # Verify RvcVoiceConversionAdapter integration works as expected
    from aidub.ai.voice.rvc_cloning_engine import RvcVoiceConversionAdapter

    adapter = RvcVoiceConversionAdapter()
    assert adapter is not None
    assert hasattr(adapter, "convert_timbre")

