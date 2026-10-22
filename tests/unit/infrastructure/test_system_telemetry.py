"""Unit tests for production system telemetry service."""

from __future__ import annotations

from aidub.infrastructure.system_telemetry import (
    SystemTelemetryReport,
    get_real_gpu_telemetry,
    get_real_ram_bytes,
    probe_system_telemetry,
)


def test_get_real_ram_bytes() -> None:
    used, total = get_real_ram_bytes()
    assert total > 0
    assert used >= 0
    assert used <= total


def test_get_real_gpu_telemetry() -> None:
    gpu_name, usage_pct, vram_used, vram_total = get_real_gpu_telemetry()
    assert isinstance(gpu_name, str)
    assert len(gpu_name) > 0
    assert 0 <= usage_pct <= 100
    assert vram_used >= 0.0
    assert vram_total >= 0.0


def test_probe_system_telemetry() -> None:
    report = probe_system_telemetry()
    assert isinstance(report, SystemTelemetryReport)
    assert report.cpu_cores >= 1
    assert report.ram_total_gb > 0.0
    assert report.disk_free_gb >= 0.0
    assert report.disk_total_gb > 0.0
    assert isinstance(report.os_info, str)
