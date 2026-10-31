"""Unit tests for SystemMonitor GPU and VRAM hardware telemetry."""

from __future__ import annotations

from aidub.application.system.system_monitor import SystemMonitor


def test_system_monitor_gpu_snapshot_structure() -> None:
    gpu = SystemMonitor.gpu_snapshot()
    assert isinstance(gpu, dict)
    assert "available" in gpu
    assert "gpu_name" in gpu
    assert "vram_total_gb" in gpu
    assert "vram_used_gb" in gpu
    assert "vram_percent" in gpu
    assert "gpu_utilization_percent" in gpu
    assert "backend" in gpu

    assert isinstance(gpu["available"], bool)
    assert isinstance(gpu["gpu_name"], str)
    assert isinstance(gpu["vram_total_gb"], (int, float))
    assert isinstance(gpu["vram_used_gb"], (int, float))
    assert 0.0 <= gpu["vram_percent"] <= 100.0


def test_system_monitor_snapshot_contains_gpu() -> None:
    snap = SystemMonitor.snapshot()
    assert "cpu_percent" in snap
    assert "memory_total_gb" in snap
    assert "gpu" in snap
    assert isinstance(snap["gpu"], dict)
    assert "available" in snap["gpu"]
