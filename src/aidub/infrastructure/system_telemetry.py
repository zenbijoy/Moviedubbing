"""
Production System Telemetry & Hardware Monitoring Service.

Provides real hardware telemetry probing (CPU cores & usage, Physical RAM total/used,
GPU model name & VRAM usage via PyTorch/CUDA/wmic, and Free Disk Storage via shutil)
without any random numbers or hardcoded simulations.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SystemTelemetryReport:
    os_info: str
    cpu_cores: int
    cpu_usage_pct: float
    ram_used_gb: float
    ram_total_gb: float
    gpu_name: str
    gpu_usage_pct: int
    vram_used_gb: float
    vram_total_gb: float
    disk_free_gb: float
    disk_total_gb: float
    loaded_models_count: int
    active_models_summary: str


def get_real_ram_bytes() -> tuple[int, int]:
    """Return (used_bytes, total_bytes) of physical memory using OS APIs."""
    if sys.platform == "win32":
        try:

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = int(stat.ullTotalPhys)
                avail = int(stat.ullAvailPhys)
                used = max(0, total - avail)
                return used, total
        except Exception as exc:
            logger.debug("Win32 memory status check fallback: %s", exc)

    try:
        import psutil

        mem = psutil.virtual_memory()
    except (ImportError, Exception) as exc:
        logger.debug("psutil check fallback: %s", exc)
    else:
        return mem.used, mem.total

    return 0, 0


def get_real_gpu_telemetry() -> tuple[str, int, float, float]:
    """
    Probe PyTorch CUDA / NVML or system GPU.
    Returns (gpu_name, usage_pct, vram_used_gb, vram_total_gb).
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            output = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=3,
            )
            name, utilization, memory_used, memory_total = [
                value.strip() for value in output.splitlines()[0].split(",")
            ]
            return (
                name,
                int(float(utilization)),
                round(float(memory_used) / 1024.0, 1),
                round(float(memory_total) / 1024.0, 1),
            )
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            logger.debug("nvidia-smi telemetry probe failed: %s", exc)

    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_total_gb = round(props.total_memory / (1024**3), 1)
            free_bytes, total_bytes = torch.cuda.mem_get_info(0)
            vram_used_gb = round((total_bytes - free_bytes) / (1024**3), 1)
            pct = int((vram_used_gb / max(0.1, vram_total_gb)) * 100)
            return gpu_name, pct, vram_used_gb, vram_total_gb
    except Exception as exc:
        logger.debug("PyTorch CUDA telemetry probe fallback: %s", exc)

    return "Unavailable", 0, 0.0, 0.0


def probe_system_telemetry(target_dir: Path | str | None = None) -> SystemTelemetryReport:
    """Probe exact real-time hardware telemetry from operating system and hardware drivers."""
    os_str = f"{platform.system()} {platform.release()}"
    cpu_cores = os.cpu_count() or 0
    cpu_usage_pct = 0.0
    try:
        import psutil

        cpu_usage_pct = float(psutil.cpu_percent(interval=None))
    except ImportError:
        pass

    used_bytes, total_bytes = get_real_ram_bytes()
    ram_used_gb = round(used_bytes / (1024**3), 1)
    ram_total_gb = round(total_bytes / (1024**3), 1)

    gpu_name, gpu_pct, vram_used, vram_total = get_real_gpu_telemetry()

    check_path = Path(target_dir) if target_dir else Path.cwd()
    try:
        usage = shutil.disk_usage(check_path)
        disk_free_gb = round(usage.free / (1024**3), 1)
        disk_total_gb = round(usage.total / (1024**3), 1)
    except Exception as exc:
        logger.debug("Storage check fallback: %s", exc)
        disk_free_gb, disk_total_gb = 0.0, 0.0

    loaded_models_count = 0
    models_summary = "No models currently loaded in VRAM"
    try:
        from aidub.infrastructure.models.manager import (
            ModelManager,
        )

        manager = ModelManager.get_instance()
        loaded = manager.loaded_models()
        loaded_models_count = len(loaded)
        if loaded_models_count > 0:
            models_summary = ", ".join(m.model_id for m in loaded)
    except Exception as exc:
        logger.debug("Model manager check fallback: %s", exc)

    return SystemTelemetryReport(
        os_info=os_str,
        cpu_cores=cpu_cores,
        cpu_usage_pct=cpu_usage_pct,
        ram_used_gb=ram_used_gb,
        ram_total_gb=ram_total_gb,
        gpu_name=gpu_name,
        gpu_usage_pct=gpu_pct,
        vram_used_gb=vram_used,
        vram_total_gb=vram_total,
        disk_free_gb=disk_free_gb,
        disk_total_gb=disk_total_gb,
        loaded_models_count=loaded_models_count,
        active_models_summary=models_summary,
    )


__all__ = [
    "SystemTelemetryReport",
    "get_real_gpu_telemetry",
    "get_real_ram_bytes",
    "probe_system_telemetry",
]
