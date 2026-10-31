"""Unit tests for VoiceEngineBenchmarkRunner."""

from __future__ import annotations

from pathlib import Path

from aidub.adapters.voice_base import VoiceEngineKind
from aidub.application.voice.benchmark_runner import (
    VoiceEngineBenchmarkRunner,
)


def test_benchmark_runner_single_engine(tmp_path: Path) -> None:
    runner = VoiceEngineBenchmarkRunner()
    res = runner.benchmark_engine(
        engine_kind=VoiceEngineKind.SYNTHETIC,
        text="The quest stands upon the edge of a knife.",
        output_dir=tmp_path / "bench_out",
    )

    assert res.engine_kind == "synthetic"
    assert res.is_available is True
    assert res.audio_duration_ms > 0
    assert res.latency_ms >= 0
    assert res.real_time_factor >= 0.0


def test_benchmark_runner_full_suite(tmp_path: Path) -> None:
    runner = VoiceEngineBenchmarkRunner()
    # Test suite with synthetic and local candidates
    report = runner.run_suite(
        text="All that is gold does not glitter.",
        output_dir=tmp_path / "suite_out",
        engines=[VoiceEngineKind.SYNTHETIC, VoiceEngineKind.QWEN3_TTS],
    )

    assert len(report.results) == 2
    assert report.benchmark_id.startswith("bench_report_")
    assert report.results[0].engine_kind == "synthetic"
    assert report.results[0].is_available is True
