"""System monitor screen: real-time laptop & GPU/VRAM performance."""
from __future__ import annotations

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox, QTableWidget,
        QTableWidgetItem, QHeaderView,
    )
    _QT = True
except ImportError:
    _QT = False
    QWidget = object  # type: ignore
    QDockWidget = object  # type: ignore

from aidub.application.system.system_monitor import SystemMonitor


if _QT:
    class SystemMonitorScreen(QWidget):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle("System Monitor & AI Accelerator")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            info_box = QGroupBox("System Info")
            info_lay = QVBoxLayout(info_box)
            self.platform_lbl = QLabel()
            self.proc_lbl = QLabel()
            info_lay.addWidget(self.platform_lbl)
            info_lay.addWidget(self.proc_lbl)
            layout.addWidget(info_box)

            # GPU & VRAM (AI Accelerator)
            gpu_box = QGroupBox("GPU & VRAM (AI Accelerator)")
            gpu_lay = QVBoxLayout(gpu_box)
            self.gpu_title_lbl = QLabel("GPU: Detecting...")
            self.gpu_util_lbl = QLabel("Compute: 0%")
            self.gpu_util_bar = QProgressBar()
            self.gpu_util_bar.setRange(0, 100)
            self.vram_lbl = QLabel("VRAM: 0 / 0 GB (0%)")
            self.vram_bar = QProgressBar()
            self.vram_bar.setRange(0, 100)
            self.gpu_temp_lbl = QLabel("Temp: N/A")

            gpu_lay.addWidget(self.gpu_title_lbl)
            gpu_lay.addWidget(self.gpu_util_lbl)
            gpu_lay.addWidget(self.gpu_util_bar)
            gpu_lay.addWidget(self.vram_lbl)
            gpu_lay.addWidget(self.vram_bar)
            gpu_lay.addWidget(self.gpu_temp_lbl)
            layout.addWidget(gpu_box)

            # CPU
            cpu_box = QGroupBox("CPU")
            cpu_lay = QVBoxLayout(cpu_box)
            self.cpu_bar = QProgressBar()
            self.cpu_lbl = QLabel()
            cpu_lay.addWidget(self.cpu_bar)
            cpu_lay.addWidget(self.cpu_lbl)
            layout.addWidget(cpu_box)

            # Memory
            mem_box = QGroupBox("RAM Memory")
            mem_lay = QVBoxLayout(mem_box)
            self.mem_bar = QProgressBar()
            self.mem_lbl = QLabel()
            mem_lay.addWidget(self.mem_bar)
            mem_lay.addWidget(self.mem_lbl)
            layout.addWidget(mem_box)

            # Disk
            disk_box = QGroupBox("Disk")
            disk_lay = QVBoxLayout(disk_box)
            self.disk_bar = QProgressBar()
            self.disk_lbl = QLabel()
            disk_lay.addWidget(self.disk_bar)
            disk_lay.addWidget(self.disk_lbl)
            layout.addWidget(disk_box)

            # Network / Battery
            nb_box = QGroupBox("Network / Battery")
            nb_lay = QVBoxLayout(nb_box)
            self.net_lbl = QLabel()
            self.bat_lbl = QLabel()
            nb_lay.addWidget(self.net_lbl)
            nb_lay.addWidget(self.bat_lbl)
            layout.addWidget(nb_box)

            # Top processes
            proc_box = QGroupBox("Top Processes (CPU)")
            proc_lay = QVBoxLayout(proc_box)
            self.proc_table = QTableWidget(0, 4)
            self.proc_table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Mem %"])
            self.proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            proc_lay.addWidget(self.proc_table)
            layout.addWidget(proc_box)

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(1000)
            self.refresh()

        def refresh(self) -> None:
            snap = SystemMonitor.snapshot()
            self.platform_lbl.setText(f"Platform: {snap['platform']} {snap['platform_release']}")
            self.proc_lbl.setText(f"Processes: {snap['process_count']}  CPU cores: {snap['cpu_count']}")

            # GPU Telemetry
            gpu = snap.get("gpu", {})
            if gpu.get("available"):
                self.gpu_title_lbl.setText(f"GPU: {gpu.get('gpu_name')} [{gpu.get('backend', '').upper()}]")
                util = int(gpu.get("gpu_utilization_percent", 0.0))
                self.gpu_util_bar.setValue(util)
                self.gpu_util_lbl.setText(f"Compute Load: {util}%")
                vram_pct = int(gpu.get("vram_percent", 0.0))
                self.vram_bar.setValue(vram_pct)
                self.vram_lbl.setText(
                    f"VRAM: {gpu.get('vram_used_gb', 0.0)} / {gpu.get('vram_total_gb', 0.0)} GB ({vram_pct}%)"
                )
                temp = gpu.get("temperature_c")
                if temp is not None:
                    self.gpu_temp_lbl.setText(f"Thermal: {temp}°C")
                else:
                    self.gpu_temp_lbl.setText("Thermal: Nominal")
            else:
                self.gpu_title_lbl.setText(f"GPU: {gpu.get('gpu_name', 'None')} (CPU-Only Mode)")
                self.gpu_util_bar.setValue(0)
                self.gpu_util_lbl.setText("Compute Load: N/A")
                self.vram_bar.setValue(0)
                self.vram_lbl.setText("VRAM: N/A")
                self.gpu_temp_lbl.setText("Thermal: N/A")

            self.cpu_bar.setValue(int(snap["cpu_percent"]))
            self.cpu_lbl.setText(f"CPU: {snap['cpu_percent']}%")
            self.mem_bar.setValue(int(snap["memory_percent"]))
            self.mem_lbl.setText(f"Memory: {snap['memory_used_gb']}/{snap['memory_total_gb']} GB ({snap['memory_percent']}%)")
            self.disk_bar.setValue(int(snap["disk_percent"]))
            self.disk_lbl.setText(f"Disk: {snap['disk_used_gb']}/{snap['disk_total_gb']} GB ({snap['disk_percent']}%)")
            self.net_lbl.setText(f"Network sent: {snap['net_sent_mb']} MB  recv: {snap['net_recv_mb']} MB")
            bat = snap["battery"]
            if bat:
                self.bat_lbl.setText(f"Battery: {bat['percent']}%  {'Charging' if bat['plugged'] else 'On battery'}")
            else:
                self.bat_lbl.setText("Battery: N/A (desktop/AC)")

            # top procs
            procs = SystemMonitor.top_processes(6)
            self.proc_table.setRowCount(len(procs))
            for i, p in enumerate(procs):
                self.proc_table.setItem(i, 0, QTableWidgetItem(str(p.get("pid"))))
                self.proc_table.setItem(i, 1, QTableWidgetItem(str(p.get("name"))))
                self.proc_table.setItem(i, 2, QTableWidgetItem(f"{p.get('cpu_percent') or 0:.1f}"))
                self.proc_table.setItem(i, 3, QTableWidgetItem(f"{p.get('memory_percent') or 0:.1f}"))

    class SystemMonitorDockWidget(QDockWidget):
        """Dockable timeline monitor panel for CPU, RAM, and GPU/VRAM hardware telemetry."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__("Hardware & GPU Accelerator Monitor", parent)
            self.monitor_screen = SystemMonitorScreen(self)
            self.setWidget(self.monitor_screen)
else:
    class SystemMonitorScreen:  # type: ignore
        """Headless stub when PySide6 is unavailable."""
        def __init__(self, *args, **kwargs) -> None:
            pass
        def refresh(self) -> None:
            pass

    class SystemMonitorDockWidget:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["SystemMonitorScreen", "SystemMonitorDockWidget"]
