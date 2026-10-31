"""System performance monitor backend."""
from __future__ import annotations

import platform
from typing import Any

import psutil


class SystemMonitor:
    @staticmethod
    def gpu_snapshot() -> dict[str, Any]:
        """Fetch GPU & VRAM telemetry via nvidia-smi, falling back to torch.cuda or CPU mode."""
        import subprocess

        # 1. Try nvidia-smi first (fastest, most accurate for hardware telemetry on Windows/Linux)
        try:
            res = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                if lines:
                    first = [p.strip() for p in lines[0].split(",")]
                    if len(first) >= 5:
                        name = first[0]
                        total_mib = float(first[1])
                        used_mib = float(first[2])
                        util_pct = float(first[3])
                        temp_c = float(first[4])
                        vram_total_gb = round(total_mib / 1024.0, 2)
                        vram_used_gb = round(used_mib / 1024.0, 2)
                        vram_pct = round((used_mib / total_mib * 100.0), 1) if total_mib > 0 else 0.0
                        return {
                            "available": True,
                            "gpu_name": name,
                            "gpu_count": len(lines),
                            "gpu_utilization_percent": util_pct,
                            "vram_total_gb": vram_total_gb,
                            "vram_used_gb": vram_used_gb,
                            "vram_percent": vram_pct,
                            "temperature_c": temp_c,
                            "backend": "nvidia-smi",
                        }
        except Exception:
            pass

        # 2. Try torch.cuda fallback
        try:
            import torch
            if torch.cuda.is_available():
                count = torch.cuda.device_count()
                name = torch.cuda.get_device_name(0)
                try:
                    free_b, total_b = torch.cuda.mem_get_info(0)
                    used_b = total_b - free_b
                    vram_total_gb = round(total_b / (1024**3), 2)
                    vram_used_gb = round(used_b / (1024**3), 2)
                    vram_pct = round((used_b / total_b * 100.0), 1) if total_b > 0 else 0.0
                except Exception:
                    allocated_b = torch.cuda.memory_allocated(0)
                    reserved_b = torch.cuda.memory_reserved(0)
                    vram_used_gb = round(allocated_b / (1024**3), 2)
                    vram_total_gb = round(reserved_b / (1024**3), 2) or vram_used_gb
                    vram_pct = round((allocated_b / max(reserved_b, 1) * 100.0), 1)

                return {
                    "available": True,
                    "gpu_name": name,
                    "gpu_count": count,
                    "gpu_utilization_percent": 0.0,
                    "vram_total_gb": vram_total_gb,
                    "vram_used_gb": vram_used_gb,
                    "vram_percent": vram_pct,
                    "temperature_c": None,
                    "backend": "torch.cuda",
                }
        except Exception:
            pass

        # 3. Fallback when no dedicated GPU is available
        return {
            "available": False,
            "gpu_name": "None (CPU Mode)",
            "gpu_count": 0,
            "gpu_utilization_percent": 0.0,
            "vram_total_gb": 0.0,
            "vram_used_gb": 0.0,
            "vram_percent": 0.0,
            "temperature_c": None,
            "backend": "none",
        }

    @staticmethod
    def snapshot() -> dict[str, Any]:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        battery = None
        try:
            b = psutil.sensors_battery()
            if b is not None:
                battery = {"percent": b.percent, "plugged": b.power_plugged, "secs_left": b.secsleft}
        except Exception:
            battery = None
        gpu = SystemMonitor.gpu_snapshot()
        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "net_sent_mb": round(net.bytes_sent / (1024**2), 2),
            "net_recv_mb": round(net.bytes_recv / (1024**2), 2),
            "battery": battery,
            "gpu": gpu,
            "process_count": len(psutil.pids()),
        }

    @staticmethod
    def top_processes(n: int = 5) -> list[dict[str, Any]]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
        return procs[:n]


__all__ = ["SystemMonitor"]
