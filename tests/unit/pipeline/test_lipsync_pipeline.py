"""Unit tests for Lip-Sync pipeline integration, CLI flags, safe execution, and diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidub.adapters.lipsync_base import (
    LipSyncOptions,
    LipSyncQualityTier,
    run_configured_lipsync,
)
from aidub.cli import build_parser
from aidub.diagnostics.dubbing import _check_lipsync, collect_dubbing_diagnostics
from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine
from aidub.pipeline.errors import ErrorKind, PipelineError


def test_cli_parses_lipsync_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "dub",
            "-i",
            "in.mp4",
            "-o",
            "out.mp4",
            "--lipsync",
            "--lipsync-tier",
            "cinema_quality",
        ]
    )
    assert args.lipsync is True
    assert args.lipsync_tier == "cinema_quality"

    args_default = parser.parse_args(["dub", "-i", "in.mp4", "-o", "out.mp4"])
    assert args_default.lipsync is False
    assert args_default.lipsync_tier == "preview_fast"


def test_pipeline_config_lipsync_defaults(tmp_path: Path) -> None:
    cfg = PipelineConfig(input=tmp_path / "in.mp4", output=tmp_path / "out.mp4")
    assert cfg.lipsync is False
    assert cfg.lipsync_tier == "preview_fast"


def test_run_configured_lipsync_supports_all_options_and_safe_fps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    audio = tmp_path / "target.wav"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"source data")
    audio.write_bytes(b"audio data")

    # Command template uses all placeholders without failing with KeyError
    cmd_template = (
        "python -c \"import sys, pathlib; pathlib.Path(sys.argv[1]).write_bytes(b'video')\" "
        "{output} {video} {audio} {fps} {device} {face_padding}"
    )
    monkeypatch.setenv("TEST_LIPSYNC_CMD", cmd_template)

    opts = LipSyncOptions(fps=30.0, device="cuda:0", face_padding=15)

    # Mock probe to return valid video stream with tricky/missing frame rates
    mock_probe = {
        "format": {"duration": "2.5"},
        "streams": [
            {
                "codec_type": "video",
                "avg_frame_rate": "0/0",  # Test division by zero safety
                "r_frame_rate": "30/1",
                "width": 1280,
                "height": 720,
            }
        ],
    }
    with patch("aidub.adapters.lipsync_base.probe", return_value=mock_probe):
        rendered_frames, duration_ms = run_configured_lipsync(
            "TEST_LIPSYNC_CMD",
            source_video_path=str(source),
            target_audio_path=str(audio),
            output_path=output,
            options=opts,
        )

    assert rendered_frames == round(2.5 * 30.0)
    assert duration_ms == 2500
    assert output.is_file()


def test_dubbing_engine_validates_lipsync_prerequisites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "in.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"fake video")

    # Mock diagnostics report so other components pass
    from aidub.diagnostics.dubbing import DubbingCheckResult, DubbingDiagnosticReport

    mock_report = DubbingDiagnosticReport(
        checks=[
            DubbingCheckResult(name="ffmpeg/ffprobe", ok=True, detail="ok"),
            DubbingCheckResult(name="faster-whisper", ok=True, detail="ok"),
            DubbingCheckResult(name="demucs", ok=True, detail="ok"),
            DubbingCheckResult(name="edge-tts reachability", ok=True, detail="ok"),
            DubbingCheckResult(name="llm provider", ok=True, detail="ok"),
        ]
    )
    monkeypatch.setattr(
        "aidub.diagnostics.dubbing.collect_dubbing_diagnostics", lambda: mock_report
    )
    monkeypatch.delenv("AIDUB_MUSETALK_COMMAND", raising=False)

    cfg = PipelineConfig(
        input=source,
        output=output,
        lipsync=True,
        lipsync_tier="preview_fast",
        work_dir=tmp_path / "work",
    )
    engine = DubbingEngine(cfg)

    with pytest.raises(PipelineError) as exc_info:
        engine.run()

    assert exc_info.value.code == "lipsync_not_configured"
    assert "AIDUB_MUSETALK_COMMAND is not configured" in str(exc_info.value)


def test_dubbing_engine_runs_lipsync_stage_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "in.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"fake video")

    from aidub.diagnostics.dubbing import DubbingCheckResult, DubbingDiagnosticReport

    mock_report = DubbingDiagnosticReport(
        checks=[
            DubbingCheckResult(name="ffmpeg/ffprobe", ok=True, detail="ok"),
            DubbingCheckResult(name="faster-whisper", ok=True, detail="ok"),
            DubbingCheckResult(name="demucs", ok=True, detail="ok"),
            DubbingCheckResult(name="edge-tts reachability", ok=True, detail="ok"),
            DubbingCheckResult(name="llm provider", ok=True, detail="ok"),
            DubbingCheckResult(name="lip-sync engine", ok=True, detail="ok"),
        ]
    )
    monkeypatch.setattr(
        "aidub.diagnostics.dubbing.collect_dubbing_diagnostics", lambda: mock_report
    )
    monkeypatch.setenv(
        "AIDUB_MUSETALK_COMMAND",
        'python -c "import sys, pathlib; pathlib.Path(sys.argv[1]).write_bytes(b\'video\')" {output}',
    )

    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    from aidub.pipeline.engine import PIPELINE_VERSION
    from aidub.pipeline.manifest import PipelineManifest

    manifest = PipelineManifest.load(work_dir)
    manifest.pipeline_version = PIPELINE_VERSION
    manifest.input_url = str(source.resolve())
    stat = source.stat()
    manifest.source_signature = f"{stat.st_size}:{stat.st_mtime_ns}"
    manifest.config_signature = json.dumps(
        {
            "asr_model": "large-v3",
            "diarize": False,
            "dub": True,
            "keep_music": False,
            "lipsync": True,
            "lipsync_tier": "preview_fast",
            "max_stretch": 2.0,
            "src_lang": "auto",
            "tgt_lang": "bn",
            "voice_name": None,
        },
        sort_keys=True,
    )
    manifest.mark_stage("extract_audio", True)
    manifest.mark_stage("separate_stems", True)
    manifest.mark_stage("diarize", True)
    manifest.mark_stage("asr", True)
    manifest.mark_stage("translate", True)
    manifest.mark_stage("tts", True)
    manifest.mark_stage("assemble", True)
    manifest.save()

    (work_dir / "origin_audio.wav").write_bytes(b"origin audio")
    (work_dir / "vocals.wav").write_bytes(b"vocals")
    (work_dir / "vocals16.wav").write_bytes(b"vocals16")
    (work_dir / "dubbed_vocals.wav").write_bytes(b"dubbed vocals")
    (work_dir / "asr_segments.json").write_text("[]", encoding="utf-8")

    cfg = PipelineConfig(
        input=source,
        output=output,
        lipsync=True,
        lipsync_tier="preview_fast",
        keep_music=False,
        diarize=False,
        dub=True,
        work_dir=work_dir,
    )

    mock_probe = {
        "format": {"duration": "1.0"},
        "streams": [
            {
                "codec_type": "video",
                "fps": 24.0,
                "avg_frame_rate": "24/1",
                "width": 1280,
                "height": 720,
            },
            {"codec_type": "audio", "sample_rate": 24000, "channels": 1},
        ],
    }

    with (
        patch("aidub.pipeline.engine.probe", return_value=mock_probe),
        patch("aidub.adapters.lipsync_base.probe", return_value=mock_probe),
        patch("aidub.pipeline.engine.extract_audio"),
        patch("aidub.pipeline.engine.to_16k_mono", return_value=work_dir / "vocals16.wav"),
        patch(
            "aidub.pipeline.engine.mux",
            side_effect=lambda v, a, o: Path(o).write_bytes(b"dubbed video"),
        ),
    ):
        engine = DubbingEngine(cfg)
        outputs = engine.run()

    assert engine.manifest.is_stage_completed("lipsync") is True
    assert outputs.lipsynced_video != ""
    assert Path(outputs.lipsynced_video).exists()
    assert output.is_file()


def test_temporal_compositor_composite_video_validates_files(tmp_path: Path) -> None:
    from aidub.ai.vision.temporal_compositor import TemporalLipSyncCompositor

    compositor = TemporalLipSyncCompositor()
    with pytest.raises(FileNotFoundError, match="Source video not found"):
        compositor.composite_video("missing_src.mp4", "missing_ls.mp4", tmp_path / "out.mp4")

    src = tmp_path / "src.mp4"
    src.write_bytes(b"video")
    with pytest.raises(FileNotFoundError, match="Lip-sync video not found"):
        compositor.composite_video(src, "missing_ls.mp4", tmp_path / "out.mp4")


def test_check_lipsync_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIDUB_MUSETALK_COMMAND", raising=False)
    monkeypatch.delenv("AIDUB_LATENTSYNC_COMMAND", raising=False)

    res = _check_lipsync()
    assert res.ok is False
    assert "NOT CONFIGURED" in res.detail

    monkeypatch.setenv(
        "AIDUB_MUSETALK_COMMAND",
        "python -m musetalk --video {video} --audio {audio} --output {output}",
    )
    res_preview = _check_lipsync()
    assert res_preview.ok is True
    assert "MuseTalk" in res_preview.detail

    monkeypatch.setenv(
        "AIDUB_LATENTSYNC_COMMAND",
        "python LatentSync/inference.py --video {video} --audio {audio} --output {output}",
    )
    res_both = _check_lipsync()
    assert res_both.ok is True
    assert "MuseTalk" in res_both.detail and "LatentSync" in res_both.detail
