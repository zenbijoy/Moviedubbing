"""
Autonomous First-Run Setup & Hardware Diagnostic Wizard.

Auto-detects CPU cores, system RAM, NVIDIA GPUs / CUDA VRAM, and FFmpeg capability,
benchmarks system speed, and assigns optimal execution tiers (`ULTRA_CUDA`, `MID_GPU`, `CPU_BASIC`).
"""

from __future__ import annotations

import logging
import os
import platform
import time
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel

logger = logging.getLogger(__name__)

# Optional PySide6 import guard for headless execution environments
try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QFormLayout,
        QGroupBox,
        QLabel,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc, assignment]


class HardwareTier(StrEnum):
    ULTRA_CUDA = "ultra_cuda"  # NVIDIA GPU with >= 12GB VRAM
    MID_GPU = "mid_gpu"  # GPU with 4GB - 12GB VRAM or Apple Silicon
    CPU_BASIC = "cpu_basic"  # CPU fallback mode


class SystemCapabilityReport(ContractModel):
    """Diagnostic system resource capability report."""

    os_name: str = Field(min_length=1)
    cpu_cores: int = Field(ge=1)
    ram_gb: float = Field(ge=0.0)
    gpu_name: str = Field(default="Unavailable")
    vram_gb: float = Field(ge=0.0)
    ffmpeg_available: bool = True
    assigned_tier: HardwareTier = HardwareTier.CPU_BASIC
    recommended_concurrency: int = Field(default=4, ge=1)


class HardwareDiagnosticWizardController:
    """
    Autonomous hardware detection and tuning wizard controller (headless safe).
    """

    def probe_system_hardware(self) -> SystemCapabilityReport:
        """
        Probe system hardware capabilities and auto-assign performance tier.
        """
        cpu_count = os.cpu_count() or 4
        os_str = f"{platform.system()} {platform.release()}"

        # Real memory & GPU hardware probing
        from aidub.infrastructure.system_telemetry import probe_system_telemetry

        report = probe_system_telemetry()
        ram_gb = report.ram_total_gb
        vram_gb = report.vram_total_gb
        gpu_name = report.gpu_name
        try:
            from aidub.media.ffmpeg_ops import _ffmpeg_exe

            _ffmpeg_exe()
            ffmpeg_ok = True
        except RuntimeError:
            ffmpeg_ok = False

        # Assign tier
        if vram_gb >= 12.0 and ffmpeg_ok:
            tier = HardwareTier.ULTRA_CUDA
            concurrency = min(8, cpu_count)
        elif vram_gb >= 4.0:
            tier = HardwareTier.MID_GPU
            concurrency = min(4, cpu_count)
        else:
            tier = HardwareTier.CPU_BASIC
            concurrency = 2

        logger.info(
            "hardware_wizard: detected %s, CPU: %d cores, RAM: %.1fGB, VRAM: %.1fGB -> Tier: %s",
            gpu_name,
            cpu_count,
            ram_gb,
            vram_gb,
            tier,
        )

        return SystemCapabilityReport(
            os_name=os_str,
            cpu_cores=cpu_count,
            ram_gb=ram_gb,
            gpu_name=gpu_name,
            vram_gb=vram_gb,
            ffmpeg_available=ffmpeg_ok,
            assigned_tier=tier,
            recommended_concurrency=concurrency,
        )

    def run_micro_benchmark(self) -> float:
        """
        Execute quick math micro-benchmark to evaluate CPU/GPU throughput (ms).
        """
        start = time.perf_counter()
        _ = [i * i for i in range(500000)]
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return round(elapsed_ms, 2)


if PYSIDE6_AVAILABLE:

    class FirstRunHardwareWizardWidget(QWidget):
        """PySide6 QWidget for First-Run Setup & Hardware Diagnostic Wizard."""

        diagnostic_completed = Signal(object)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.controller = HardwareDiagnosticWizardController()
            self._init_ui()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)

            group = QGroupBox("Autonomous First-Run Hardware Setup Wizard", self)
            form = QFormLayout(group)

            self.status_label = QLabel("Run diagnostics to detect available hardware.", group)
            form.addRow("System Status:", self.status_label)

            self.run_btn = QPushButton("Run Hardware Diagnostics", group)
            self.run_btn.clicked.connect(self._on_run_diagnostic)
            form.addRow("Diagnostic Action:", self.run_btn)

            self.progress_bar = QProgressBar(group)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            form.addRow("Progress:", self.progress_bar)

            layout.addWidget(group)

        def _on_run_diagnostic(self) -> None:
            self.progress_bar.setValue(50)
            report = self.controller.probe_system_hardware()
            self.progress_bar.setValue(100)
            self.status_label.setText(
                f"Assigned Tier: {report.assigned_tier.value.upper()} | {report.gpu_name} ({report.vram_gb:.1f}GB VRAM)"
            )
            self.diagnostic_completed.emit(report)


__all__ = [
    "FirstRunHardwareWizardWidget",
    "HardwareDiagnosticWizardController",
    "HardwareTier",
    "SystemCapabilityReport",
]
