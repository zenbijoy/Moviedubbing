"""
Voice Engine Registry, Hardware Resource Manager, and Lifecycle Controller.

Provides:
  - Central discovery and registration of all local and cloud speech backends.
  - Real-time hardware inspection (RAM, VRAM, CUDA device, and disk capacity).
  - Lazy instantiation and safe memory deallocation to prevent concurrent VRAM exhaustion.
  - Transparent engine capability querying and intelligent graceful fallback resolution.
"""

from __future__ import annotations

import gc
import logging
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aidub.adapters.voice.chatterbox_adapter import ChatterboxVoiceEngine
from aidub.adapters.voice.edge_tts_adapter import EdgeTTSVoiceEngine
from aidub.adapters.voice.elevenlabs_adapter import ElevenLabsVoiceEngine
from aidub.adapters.voice.gemini_tts_adapter import GeminiTTSVoiceEngine
from aidub.adapters.voice.open_models_adapter import (
    CosyVoiceEngine,
    F5TTSVoiceEngine,
    OpenVoiceEngine,
    Qwen3TTSVoiceEngine,
)
from aidub.adapters.voice_base import (
    EngineCapability,
    SyntheticVoiceEngine,
    VoiceEngine,
    VoiceEngineKind,
    VoiceEngineMetadata,
)

logger = logging.getLogger(__name__)


def get_system_ram_gb() -> tuple[float, float]:
    """Return (total_ram_gb, available_ram_gb) using psutil or native OS APIs."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        return round(mem.total / (1024**3), 2), round(mem.available / (1024**3), 2)
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import ctypes

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
                return round(stat.ullTotalPhys / (1024**3), 2), round(
                    stat.ullAvailPhys / (1024**3), 2
                )
        except Exception:
            pass

    return 16.0, 8.0  # conservative fallback


def get_gpu_info() -> dict[str, Any]:
    """Inspect CUDA hardware availability, device name, and VRAM."""
    try:
        import torch

        if torch.cuda.is_available():
            dev_idx = 0
            dev_name = torch.cuda.get_device_name(dev_idx)
            total_vram = round(
                torch.cuda.get_device_properties(dev_idx).total_memory / (1024**3), 2
            )
            allocated = torch.cuda.memory_allocated(dev_idx)
            free_vram = round(
                (torch.cuda.get_device_properties(dev_idx).total_memory - allocated) / (1024**3), 2
            )
            return {
                "cuda_available": True,
                "device_name": dev_name,
                "vram_total_gb": total_vram,
                "vram_free_gb": free_vram,
            }
    except Exception:
        pass

    return {
        "cuda_available": False,
        "device_name": "CPU (No CUDA detected)",
        "vram_total_gb": 0.0,
        "vram_free_gb": 0.0,
    }


def get_disk_free_gb(path: Path | str | None = None) -> float:
    """Return free disk space in GB for the target drive."""
    target = Path(path or Path.home())
    try:
        _, _, free = shutil.disk_usage(target)
        return round(free / (1024**3), 2)
    except Exception:
        return 50.0


class VoiceEngineRegistry:
    """
    Central registry for speech generation engines with hardware checks and lazy loading.
    """

    _default_instance: VoiceEngineRegistry | None = None

    @classmethod
    def get_default(cls) -> VoiceEngineRegistry:
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def __init__(self) -> None:
        self._factories: dict[VoiceEngineKind, Callable[[], VoiceEngine]] = {}
        self._loaded_instances: dict[VoiceEngineKind, VoiceEngine] = {}
        self._register_default_engines()

    def _register_default_engines(self) -> None:
        self._factories[VoiceEngineKind.SYNTHETIC] = lambda: SyntheticVoiceEngine()
        self._factories[VoiceEngineKind.EDGE_TTS] = lambda: EdgeTTSVoiceEngine()
        self._factories[VoiceEngineKind.GEMINI_TTS] = lambda: GeminiTTSVoiceEngine()
        self._factories[VoiceEngineKind.ELEVENLABS] = lambda: ElevenLabsVoiceEngine()
        self._factories[VoiceEngineKind.CHATTERBOX] = lambda: ChatterboxVoiceEngine()
        self._factories[VoiceEngineKind.F5_TTS] = lambda: F5TTSVoiceEngine()
        self._factories[VoiceEngineKind.COSYVOICE] = lambda: CosyVoiceEngine()
        self._factories[VoiceEngineKind.OPENVOICE] = lambda: OpenVoiceEngine()
        self._factories[VoiceEngineKind.QWEN3_TTS] = lambda: Qwen3TTSVoiceEngine()

    def register_engine(
        self, kind: VoiceEngineKind, factory: Callable[[], VoiceEngine]
    ) -> None:
        """Register a custom or fine-tuned engine factory."""
        self._factories[kind] = factory
        if kind in self._loaded_instances:
            del self._loaded_instances[kind]

    def list_registered_engines(self) -> list[VoiceEngineKind]:
        return list(self._factories.keys())

    def get_disk_free_gb(self, path: Path | str | None = None) -> float:
        return get_disk_free_gb(path)

    def get_engine(self, kind: VoiceEngineKind | str) -> VoiceEngine:
        """
        Retrieve or lazily instantiate the requested voice engine.
        Enforces memory requirements check prior to instantiation.
        """
        if isinstance(kind, str):
            try:
                kind = VoiceEngineKind(kind)
            except ValueError:
                kind = VoiceEngineKind.SYNTHETIC

        if kind in self._loaded_instances:
            return self._loaded_instances[kind]

        if kind not in self._factories:
            raise KeyError(f"Voice engine '{kind}' is not registered.")

        # Instantiate engine
        engine = self._factories[kind]()
        meta = engine.metadata

        # Perform hardware memory check for local heavy models
        if meta.is_local and meta.min_vram_gb > 0.0:
            gpu = get_gpu_info()
            if not gpu["cuda_available"] and meta.min_vram_gb >= 4.0:
                logger.warning(
                    "Engine %s requires CUDA GPU with %.1f GB VRAM, but only CPU is detected.",
                    kind.value,
                    meta.min_vram_gb,
                )

        self._loaded_instances[kind] = engine
        return engine

    def unload_engine(self, kind: VoiceEngineKind) -> None:
        """Safely unload engine instance to release system RAM and GPU VRAM."""
        if kind in self._loaded_instances:
            del self._loaded_instances[kind]
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("Unloaded voice engine: %s", kind.value)

    def unload_all_engines(self) -> None:
        """Unload all active engine instances."""
        for kind in list(self._loaded_instances.keys()):
            self.unload_engine(kind)

    def get_all_metadata(self) -> list[VoiceEngineMetadata]:
        """Query metadata for all registered engines without full weight instantiation."""
        results: list[VoiceEngineMetadata] = []
        for kind, factory in self._factories.items():
            if kind in self._loaded_instances:
                results.append(self._loaded_instances[kind].metadata)
            else:
                try:
                    # Lightweight instantiation for metadata
                    instance = factory()
                    results.append(instance.metadata)
                except Exception as exc:
                    logger.debug("Failed extracting metadata for %s: %s", kind, exc)
        return results

    def inspect_hardware(self) -> dict[str, Any]:
        """Comprehensive system hardware and capacity report."""
        total_ram, avail_ram = get_system_ram_gb()
        gpu = get_gpu_info()
        disk_free = get_disk_free_gb()

        return {
            "ram_total_gb": total_ram,
            "ram_available_gb": avail_ram,
            "cuda_available": gpu["cuda_available"],
            "gpu_name": gpu["device_name"],
            "vram_total_gb": gpu["vram_total_gb"],
            "vram_free_gb": gpu["vram_free_gb"],
            "disk_free_gb": disk_free,
            "active_models_loaded": [k.value for k in self._loaded_instances],
        }

    def resolve_effective_engine(
        self,
        requested_kind: VoiceEngineKind,
        required_capabilities: set[EngineCapability] | None = None,
    ) -> tuple[VoiceEngine, list[str]]:
        """
        Resolve the best available ready engine based on user request, availability,
        and required feature capabilities. Returns (resolved_engine, warnings).
        """
        warnings: list[str] = []

        try:
            target_engine = self.get_engine(requested_kind)
            is_ready, reason = target_engine.is_available()
            if is_ready:
                # Check capability compatibility
                if required_capabilities:
                    missing = required_capabilities - target_engine.metadata.capabilities
                    if missing:
                        warnings.append(
                            f"Engine {requested_kind.value} does not natively support: "
                            f"{', '.join(c.value for c in missing)}"
                        )
                return target_engine, warnings
            warnings.append(f"Requested engine '{requested_kind.value}' not ready: {reason}")
        except Exception as exc:
            warnings.append(f"Failed initializing requested engine '{requested_kind.value}': {exc}")

        # Fallback Strategy:
        # 1. If reference cloning needed -> try ElevenLabs if configured, else Synthetic
        if required_capabilities and EngineCapability.REFERENCE_AUDIO_CLONING in required_capabilities:
            eleven = self.get_engine(VoiceEngineKind.ELEVENLABS)
            if eleven.is_available()[0]:
                warnings.append("Fell back to ElevenLabs for reference-audio cloning.")
                return eleven, warnings
            synth = self.get_engine(VoiceEngineKind.SYNTHETIC)
            warnings.append("Fell back to Synthetic engine for reference-audio testing.")
            return synth, warnings

        # 2. General TTS synthesis -> fallback to Edge-TTS or Synthetic
        edge = self.get_engine(VoiceEngineKind.EDGE_TTS)
        if edge.is_available()[0]:
            warnings.append("Fell back to Edge-TTS neural base engine.")
            return edge, warnings

        synth = self.get_engine(VoiceEngineKind.SYNTHETIC)
        warnings.append("Fell back to built-in Synthetic engine.")
        return synth, warnings


# Global singleton instance holder
_SINGLETON_HOLDER: dict[str, VoiceEngineRegistry] = {}


def get_voice_engine_registry() -> VoiceEngineRegistry:
    """Get the application-wide VoiceEngineRegistry singleton."""
    if "registry" not in _SINGLETON_HOLDER:
        _SINGLETON_HOLDER["registry"] = VoiceEngineRegistry()
    return _SINGLETON_HOLDER["registry"]


__all__ = [
    "VoiceEngineRegistry",
    "get_disk_free_gb",
    "get_gpu_info",
    "get_system_ram_gb",
    "get_voice_engine_registry",
]
