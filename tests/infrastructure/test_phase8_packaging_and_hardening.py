"""
Unit tests for Phase 8 Windows Packaging, Autonomous Diagnostics & Production Hardening:
  - Task 8.1: Standalone Windows Packaging Assembly
  - Task 8.2: Autonomous First-Run Hardware Wizard
  - Task 8.3: Crash Recovery & Transaction Snapshot Engine
  - Task 8.4: Redacted Diagnostics Support Bundle Generator
  - Task 8.5: Autonomous Quality Benchmark Suite & Release Certification
"""

from __future__ import annotations

import zipfile

import pytest

from aidub.benchmarks.autonomous_harness import (
    AutonomousBenchmarkHarness,
    BenchmarkMeasurementsUnavailableError,
    BenchmarkMetricScore,
    MetricDirection,
)
from aidub.diagnostics.support_bundle import SupportBundleGenerator
from aidub.infrastructure.persistence.recovery import (
    CrashRecoveryEngine,
    RecoveryUnavailableError,
)
from aidub.packaging.build_windows import PackagingSpec, WindowsPackager
from aidub.ui.first_run_wizard import HardwareDiagnosticWizardController, HardwareTier


def test_windows_packager(tmp_path) -> None:
    out_dir = tmp_path / "MovieDubbingStudio_v1.0.0_win64"
    spec = PackagingSpec(output_dir=out_dir)
    packager = WindowsPackager(spec)

    dist_path = packager.assemble_distribution()
    assert dist_path.exists()
    assert (dist_path / "MovieDubbingStudio.bat").exists()
    assert (dist_path / "manifest.json").exists()

    assert packager.verify_distribution() is True


def test_hardware_diagnostic_wizard() -> None:
    ctrl = HardwareDiagnosticWizardController()
    report = ctrl.probe_system_hardware()

    assert report.cpu_cores >= 1
    assert report.ram_gb >= 0.0
    assert report.vram_gb >= 0.0
    assert report.assigned_tier in (
        HardwareTier.ULTRA_CUDA,
        HardwareTier.MID_GPU,
        HardwareTier.CPU_BASIC,
    )

    bench_ms = ctrl.run_micro_benchmark()
    assert bench_ms > 0.0


def test_crash_recovery_engine(tmp_path) -> None:
    engine = CrashRecoveryEngine(storage_dir=str(tmp_path))

    # Create snapshot
    snap1 = engine.create_snapshot("proj_001", "TRANSLATION", {"lines": "120"})
    assert snap1.snapshot_id is not None
    assert snap1.project_id == "proj_001"
    assert len(snap1.metadata_sha256) == 64

    snap2 = engine.create_snapshot("proj_001", "LIPSYNC", {"shots": "45"})

    # List snapshots
    snapshots = engine.list_snapshots("proj_001")
    assert len(snapshots) == 2

    # Metadata checkpoints can be inspected, but do not contain restorable project data.
    assert snapshots[0].snapshot_id == snap2.snapshot_id
    with pytest.raises(RecoveryUnavailableError, match="cannot restore project media"):
        engine.recover_latest_valid_snapshot("proj_001")

    # Tampered checkpoint metadata is detected and excluded from the valid list.
    checkpoint_path = next(tmp_path.glob(f"proj_001_{snap2.snapshot_id}.json"))
    checkpoint_path.write_text(
        checkpoint_path.read_text(encoding="utf-8").replace("LIPSYNC", "EDITING"),
        encoding="utf-8",
    )
    assert [item.snapshot_id for item in engine.list_snapshots("proj_001")] == [snap1.snapshot_id]


def test_support_bundle_secret_redaction(tmp_path) -> None:
    generator = SupportBundleGenerator()

    # Secret redaction check
    raw_log = "API_KEY=sk-proj-secretKey1234567890abcdef12345678 and bearer eyJhbGciOiJIUzI1NiJ9.sampleToken123456"
    clean_text, count = generator.redact_sensitive_text(raw_log)
    assert "sk-proj-secretKey" not in clean_text
    assert "REDACTED_SECRET" in clean_text
    assert count >= 1

    # Generate ZIP bundle
    dummy_log = tmp_path / "app.log"
    dummy_log.write_text("password=SuperSecretPassword123\nNormal log message", encoding="utf-8")

    res = generator.generate_support_bundle(
        output_directory=str(tmp_path / "bundle_out"),
        extra_log_files=[str(dummy_log)],
    )

    assert res.file_count >= 3
    assert res.redacted_tokens_count >= 1
    assert zipfile.is_zipfile(res.zip_path)


def test_autonomous_benchmark_harness() -> None:
    harness = AutonomousBenchmarkHarness()
    with pytest.raises(BenchmarkMeasurementsUnavailableError):
        harness.run_benchmark_suite("1.0.0", ["en-US", "bn-BD", "hi-IN"], measured_metrics={})

    measurements = {
        "asr_wer": BenchmarkMetricScore(
            metric_name="ASR Word Error Rate (WER)",
            score_value=0.04,
            target_threshold=0.10,
            direction=MetricDirection.LOWER_IS_BETTER,
        ),
        "translation_bleu": BenchmarkMetricScore(
            metric_name="Translation BLEU Score",
            score_value=38.5,
            target_threshold=30.0,
            direction=MetricDirection.HIGHER_IS_BETTER,
        ),
    }
    cert = harness.run_benchmark_suite(
        "1.0.0", ["en-US", "bn-BD", "hi-IN"], measured_metrics=measurements
    )

    assert cert.app_version == "1.0.0"
    assert cert.is_approved_for_release is True
    assert cert.overall_quality_score == 1.0
    assert "asr_wer" in cert.metric_details
    assert "translation_bleu" in cert.metric_details
