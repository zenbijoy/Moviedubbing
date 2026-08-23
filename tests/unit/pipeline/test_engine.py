"""Unit tests for DubbingEngine, PipelineManifest, and UtteranceStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine, PipelineCancelled
from aidub.pipeline.errors import ErrorKind, PipelineError, exit_code_for_error
from aidub.pipeline.manifest import PipelineManifest, StageStatus
from aidub.pipeline.utterance_store import UtteranceStore


def test_pipeline_config_defaults(tmp_path: Path) -> None:
    cfg = PipelineConfig(input=tmp_path / "in.mp4", output=tmp_path / "out.mp4")
    assert cfg.tgt_lang == "bn"
    assert cfg.dub is True
    assert cfg.keep_music is True
    assert cfg.max_stretch == 2.0


def test_pipeline_manifest_save_and_load(tmp_path: Path) -> None:
    manifest = PipelineManifest.load(tmp_path, task_id="test_task_01")
    manifest.mark_stage("asr", True, duration_ms=120)
    manifest.save()

    loaded = PipelineManifest.load(tmp_path)
    assert loaded.task_id == "test_task_01"
    assert loaded.is_stage_completed("asr") is True
    assert loaded.stages["asr"].duration_ms == 120
    assert loaded.outputs.target_srt.endswith("target_language.srt")


def test_utterance_store_atomic_save_and_hash_diff(tmp_path: Path) -> None:
    store = UtteranceStore("bn", tmp_path)
    segs = [
        {"start": 1.0, "end": 3.0, "text": "Hello world", "tgt": "হ্যালো বিশ্ব", "speaker": 0},
        {"start": 3.5, "end": 6.0, "text": "Dubbing test", "tgt": "ডাবিং পরীক্ষা", "speaker": 0},
    ]

    saved_path = store.save_utterances(segs)
    assert saved_path.exists()

    loaded_segs, _ = store.load_utterances()
    assert len(loaded_segs) == 2
    assert loaded_segs[0]["_hash"] != ""

    # Test modification detection
    loaded_segs[0]["tgt"] = "সম্পূর্ণ নতুন অনুবাদ"
    modified = store.get_modified_utterances(loaded_segs)
    assert len(modified) == 1
    assert modified[0]["id"] == 1


def test_pipeline_error_handling() -> None:
    err_usage = PipelineError(ErrorKind.USAGE, "bad_arg", "Invalid CLI argument")
    assert exit_code_for_error(err_usage) == 1
    assert err_usage.retryable is False

    err_retry = PipelineError(ErrorKind.RETRYABLE, "rate_limit", "API Rate limit")
    assert exit_code_for_error(err_retry) == 2
    assert err_retry.retryable is True


def test_dubbing_engine_instantiation(tmp_path: Path) -> None:
    in_file = tmp_path / "sample.mp4"
    out_file = tmp_path / "dubbed.mp4"
    in_file.write_bytes(b"synthetic video data")

    cfg = PipelineConfig(input=in_file, output=out_file, work_dir=tmp_path / "work")
    engine = DubbingEngine(cfg)
    assert engine.work_dir.exists()
    assert engine.manifest.task_id != ""


def test_dubbing_engine_honors_cancellation_before_media_work(tmp_path: Path) -> None:
    in_file = tmp_path / "sample.mp4"
    in_file.write_bytes(b"synthetic video data")
    cfg = PipelineConfig(
        input=in_file,
        output=tmp_path / "dubbed.mp4",
        work_dir=tmp_path / "work",
    )
    engine = DubbingEngine(cfg, cancel_requested=lambda: True)

    with pytest.raises(PipelineCancelled, match="cancelled by operator"):
        engine.run()


def test_dubbing_engine_rejects_missing_source_before_probe(tmp_path: Path) -> None:
    cfg = PipelineConfig(
        input=tmp_path / "missing.mp4",
        output=tmp_path / "dubbed.mp4",
        work_dir=tmp_path / "work",
    )

    with pytest.raises(PipelineError) as exc_info:
        DubbingEngine(cfg).run()

    assert exc_info.value.code == "input_not_found"
