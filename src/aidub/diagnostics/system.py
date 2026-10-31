"""Local-only system readiness diagnostics for operators and support teams."""

from __future__ import annotations

import importlib.metadata
import platform
import shutil
import struct
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aidub import __version__
from aidub.i18n import CatalogRepository
from aidub.media import MediaRuntime, MediaRuntimeInfo


class RuntimeInspector(Protocol):
    """Small seam around the external media runtime readiness check."""

    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        """Resolve and execute the configured media runtime check."""


class CatalogInspector(Protocol):
    """Subset of the catalog repository used by diagnostics."""

    directory: Path

    def available_locales(self) -> tuple[str, ...]:
        """Return installed catalog locale identifiers."""


@dataclass(frozen=True, slots=True)
class PythonDiagnostic:
    version: str
    implementation: str
    supported: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "implementation": self.implementation,
            "supported": self.supported,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class PlatformDiagnostic:
    system: str
    release: str
    machine: str
    pointer_bits: int

    def as_dict(self) -> dict[str, object]:
        return {
            "machine": self.machine,
            "pointer_bits": self.pointer_bits,
            "release": self.release,
            "system": self.system,
        }


@dataclass(frozen=True, slots=True)
class PackageDiagnostic:
    name: str
    version: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class LocalizationDiagnostic:
    available: bool
    directory: str
    locales: tuple[str, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "directory": self.directory,
            "error": self.error,
            "locales": list(self.locales),
        }


@dataclass(frozen=True, slots=True)
class BinaryDiagnostic:
    available: bool
    path: str | None

    def as_dict(self) -> dict[str, object]:
        return {"available": self.available, "path": self.path}


@dataclass(frozen=True, slots=True)
class CudaDiagnostic:
    cuda_available: bool
    gpu_name: str
    vram_used_gb: float
    vram_total_gb: float
    torch_cuda: bool
    driver_version: str | None = None
    fix: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "cuda_available": self.cuda_available,
            "driver_version": self.driver_version,
            "fix": self.fix,
            "gpu_name": self.gpu_name,
            "torch_cuda": self.torch_cuda,
            "vram_total_gb": self.vram_total_gb,
            "vram_used_gb": self.vram_used_gb,
        }


@dataclass(frozen=True, slots=True)
class ModelsDiagnostic:
    installed_models: tuple[str, ...]
    count: int
    cache_path: str
    fix: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "cache_path": self.cache_path,
            "count": self.count,
            "fix": self.fix,
            "installed_models": list(self.installed_models),
        }


@dataclass(frozen=True, slots=True)
class CacheDiagnostic:
    path: str
    writable: bool
    free_gb: float
    fix: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "fix": self.fix,
            "free_gb": self.free_gb,
            "path": self.path,
            "writable": self.writable,
        }


@dataclass(frozen=True, slots=True)
class MediaRuntimeDiagnostic:
    operational: bool
    ffmpeg: BinaryDiagnostic
    ffprobe: BinaryDiagnostic
    version: str | None
    error: str | None = None
    ffmpeg_on_path: bool = False
    ffprobe_on_path: bool = False
    fix: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "error": self.error,
            "ffmpeg": self.ffmpeg.as_dict(),
            "ffmpeg_on_path": self.ffmpeg_on_path,
            "ffprobe": self.ffprobe.as_dict(),
            "ffprobe_on_path": self.ffprobe_on_path,
            "fix": self.fix,
            "operational": self.operational,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class DesktopDiagnostic:
    available: bool
    framework: str
    version: str | None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "error": self.error,
            "framework": self.framework,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class SystemDiagnosticReport:
    schema_version: int
    python: PythonDiagnostic
    platform: PlatformDiagnostic
    package: PackageDiagnostic
    localization: LocalizationDiagnostic
    media_runtime: MediaRuntimeDiagnostic
    desktop: DesktopDiagnostic
    cuda: CudaDiagnostic | None = None
    models: ModelsDiagnostic | None = None
    cache_dir: CacheDiagnostic | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a stable, JSON-compatible operator contract."""

        payload: dict[str, object] = {
            "desktop": self.desktop.as_dict(),
            "localization": self.localization.as_dict(),
            "media_runtime": self.media_runtime.as_dict(),
            "package": self.package.as_dict(),
            "platform": self.platform.as_dict(),
            "python": self.python.as_dict(),
            "schema_version": self.schema_version,
        }
        if self.cuda is not None:
            payload["cuda"] = self.cuda.as_dict()
        if self.models is not None:
            payload["models"] = self.models.as_dict()
        if self.cache_dir is not None:
            payload["cache_dir"] = self.cache_dir.as_dict()
        return payload


def _safe_error(error: BaseException) -> str:
    """Bound diagnostic failures so native-loader output cannot flood terminals."""

    message = " ".join(str(error).split())
    return f"{type(error).__name__}: {message}"[:1_000]


def _located_binary(
    name: str,
    finder: Callable[[str], str | None],
) -> BinaryDiagnostic:
    located = finder(name)
    if located is None:
        return BinaryDiagnostic(available=False, path=None)
    return BinaryDiagnostic(
        available=True,
        path=str(Path(located).expanduser().resolve(strict=False)),
    )


def _media_runtime_diagnostic(
    runtime: RuntimeInspector,
    finder: Callable[[str], str | None],
) -> MediaRuntimeDiagnostic:
    try:
        info = runtime.inspect(timeout_seconds=5.0)
    except Exception as error:
        ffmpeg_on_path = finder("ffmpeg") is not None
        ffprobe_on_path = finder("ffprobe") is not None
        return MediaRuntimeDiagnostic(
            operational=False,
            ffmpeg=_located_binary("ffmpeg", finder),
            ffprobe=_located_binary("ffprobe", finder),
            version=None,
            error=_safe_error(error),
            ffmpeg_on_path=ffmpeg_on_path,
            ffprobe_on_path=ffprobe_on_path,
            fix="Install FFmpeg and add ffmpeg/ffprobe to your system PATH",
        )
    ffmpeg_on_path = finder("ffmpeg") is not None
    ffprobe_on_path = finder("ffprobe") is not None
    fix = None
    if not (ffmpeg_on_path and ffprobe_on_path):
        fix = (
            f"FFmpeg is located at '{info.ffmpeg}' but is NOT in your system PATH. "
            f"Subprocesses (like Demucs) may fail. Add '{info.ffmpeg.parent}' to system PATH."
        )
    return MediaRuntimeDiagnostic(
        operational=True,
        ffmpeg=BinaryDiagnostic(available=True, path=str(info.ffmpeg)),
        ffprobe=BinaryDiagnostic(available=True, path=str(info.ffprobe)),
        version=info.version,
        ffmpeg_on_path=ffmpeg_on_path,
        ffprobe_on_path=ffprobe_on_path,
        fix=fix,
    )


def _cuda_diagnostic() -> CudaDiagnostic:
    """Probe real GPU / CUDA availability and VRAM via nvidia-smi and PyTorch."""
    import subprocess

    gpu_name = "None"
    vram_used_gb = 0.0
    vram_total_gb = 0.0
    driver_version = None
    cuda_detected = False

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            out = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.used,memory.total,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=3,
            )
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if lines:
                parts = [p.strip() for p in lines[0].split(",")]
                if len(parts) >= 3:
                    gpu_name = parts[0]
                    vram_used_gb = round(float(parts[1]) / 1024.0, 2)
                    vram_total_gb = round(float(parts[2]) / 1024.0, 2)
                    driver_version = parts[3] if len(parts) >= 4 else None
                    cuda_detected = True
        except Exception:
            pass

    torch_cuda = False
    try:
        import torch

        torch_cuda = bool(torch.cuda.is_available())
        if torch_cuda and not cuda_detected:
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_total_gb = round(props.total_memory / (1024**3), 2)
            free_bytes, total_bytes = torch.cuda.mem_get_info(0)
            vram_used_gb = round((total_bytes - free_bytes) / (1024**3), 2)
            cuda_detected = True
    except Exception:
        pass

    fix = None
    if cuda_detected and not torch_cuda:
        fix = (
            "NVIDIA GPU detected, but installed PyTorch is CPU-only. "
            "To enable GPU acceleration, install CUDA PyTorch: "
            "pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124"
        )
    elif not cuda_detected:
        fix = "No NVIDIA GPU detected; pipeline will run in CPU mode."

    return CudaDiagnostic(
        cuda_available=cuda_detected,
        gpu_name=gpu_name,
        vram_used_gb=vram_used_gb,
        vram_total_gb=vram_total_gb,
        torch_cuda=torch_cuda,
        driver_version=driver_version,
        fix=fix,
    )


def _models_diagnostic() -> ModelsDiagnostic:
    """Scan and list downloaded model artifacts in local caches."""
    cache_path = Path.home() / ".cache" / "huggingface" / "hub"
    installed: list[str] = []
    if cache_path.exists():
        for d in sorted(cache_path.iterdir()):
            if d.is_dir() and d.name.startswith("models--"):
                clean = d.name.replace("models--", "").replace("--", "/")
                installed.append(clean)

    fix = None
    if not installed:
        fix = "No AI models cached yet. Models will download automatically on first run."

    return ModelsDiagnostic(
        installed_models=tuple(installed),
        count=len(installed),
        cache_path=str(cache_path),
        fix=fix,
    )


def _cache_diagnostic() -> CacheDiagnostic:
    """Verify that local cache and scratch directories are writable with sufficient space."""
    cache_dir = Path.home() / ".cache" / "aidub"
    writable = False
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file = cache_dir / ".write_probe"
        test_file.write_text("ready", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        writable = True
    except Exception:
        pass

    try:
        usage = shutil.disk_usage(cache_dir)
        free_gb = round(usage.free / (1024**3), 2)
    except Exception:
        free_gb = 0.0

    fix = None
    if not writable:
        fix = f"Cache directory '{cache_dir}' is not writable. Check folder permissions."
    elif free_gb < 5.0:
        fix = f"Low disk space ({free_gb:.1f} GB free in '{cache_dir}'). Free at least 10 GB for video processing."

    return CacheDiagnostic(
        path=str(cache_dir),
        writable=writable,
        free_gb=free_gb,
        fix=fix,
    )


def _localization_diagnostic(repository: CatalogInspector) -> LocalizationDiagnostic:
    try:
        locales = repository.available_locales()
    except Exception as error:
        return LocalizationDiagnostic(
            available=False,
            directory=str(repository.directory),
            locales=(),
            error=_safe_error(error),
        )
    return LocalizationDiagnostic(
        available=bool(locales),
        directory=str(repository.directory),
        locales=locales,
    )


def _desktop_diagnostic(
    *,
    available: bool | None,
    version_resolver: Callable[[str], str],
) -> DesktopDiagnostic:
    if available is None:
        from aidub.ui.qt_support import (
            PYSIDE6_AVAILABLE,
            desktop_dependency_message,
        )

        available = PYSIDE6_AVAILABLE
        error = None if available else desktop_dependency_message()
    else:
        error = None if available else "PySide6 is unavailable"

    try:
        version = version_resolver("PySide6")
    except importlib.metadata.PackageNotFoundError:
        version = None
    except Exception as resolver_error:
        version = None
        if error is None:
            error = _safe_error(resolver_error)
    return DesktopDiagnostic(
        available=available,
        framework="PySide6",
        version=version,
        error=error,
    )


def collect_system_diagnostics(
    *,
    runtime: RuntimeInspector | None = None,
    catalog_repository: CatalogInspector | None = None,
    binary_finder: Callable[[str], str | None] = shutil.which,
    desktop_available: bool | None = None,
    package_version_resolver: Callable[[str], str] = importlib.metadata.version,
) -> SystemDiagnosticReport:
    """Inspect local dependencies without reading secrets or making network calls."""

    python_supported = (3, 12) <= sys.version_info[:2] < (3, 14)
    return SystemDiagnosticReport(
        schema_version=1,
        python=PythonDiagnostic(
            version=platform.python_version(),
            implementation=platform.python_implementation(),
            supported=python_supported,
        ),
        platform=PlatformDiagnostic(
            system=platform.system() or "unknown",
            release=platform.release() or "unknown",
            machine=platform.machine() or "unknown",
            pointer_bits=struct.calcsize("P") * 8,
        ),
        package=PackageDiagnostic(name="aidub-studio", version=__version__),
        localization=_localization_diagnostic(catalog_repository or CatalogRepository()),
        media_runtime=_media_runtime_diagnostic(runtime or MediaRuntime(), binary_finder),
        desktop=_desktop_diagnostic(
            available=desktop_available,
            version_resolver=package_version_resolver,
        ),
        cuda=_cuda_diagnostic(),
        models=_models_diagnostic(),
        cache_dir=_cache_diagnostic(),
    )


def render_human_diagnostics(report: SystemDiagnosticReport) -> str:
    """Render a comprehensive, human-readable report with actionable remediation guidance."""

    python_state = "supported" if report.python.supported else "unsupported"
    locale_text = ", ".join(report.localization.locales) or "none"
    desktop_state = "available" if report.desktop.available else "unavailable"
    runtime_state = "ready" if report.media_runtime.operational else "not ready"
    ffmpeg_path = report.media_runtime.ffmpeg.path or "not found"
    ffprobe_path = report.media_runtime.ffprobe.path or "not found"
    ffmpeg_path_tag = "on PATH" if report.media_runtime.ffmpeg_on_path else "NOT on PATH (fallback)"
    ffprobe_path_tag = "on PATH" if report.media_runtime.ffprobe_on_path else "NOT on PATH (fallback)"

    lines = [
        "=== AI Movie Dubbing Studio System Diagnostics ===",
        f"Package:         {report.package.name} {report.package.version}",
        f"Python:          {report.python.implementation} {report.python.version} ({python_state})",
        (
            f"Platform:        {report.platform.system} {report.platform.release}; "
            f"{report.platform.machine}; {report.platform.pointer_bits}-bit"
        ),
        f"FFmpeg:          {ffmpeg_path} [{ffmpeg_path_tag}]",
        f"ffprobe:         {ffprobe_path} [{ffprobe_path_tag}]",
        f"Media runtime:   {runtime_state}",
    ]
    if report.media_runtime.fix:
        lines.append(f"  Fix:           {report.media_runtime.fix}")
    if report.media_runtime.error:
        lines.append(f"  Media detail:  {report.media_runtime.error}")

    if report.cuda:
        if report.cuda.cuda_available:
            cuda_summary = f"{report.cuda.gpu_name} ({report.cuda.vram_used_gb:.1f} / {report.cuda.vram_total_gb:.1f} GB VRAM)"
            lines.append(f"GPU Hardware:    {cuda_summary} [Driver: {report.cuda.driver_version or 'unknown'}]")
        else:
            lines.append("GPU Hardware:    No NVIDIA GPU detected (CPU mode only)")
        lines.append(f"CUDA (PyTorch):  {'Available' if report.cuda.torch_cuda else 'Unavailable (CPU-only PyTorch build installed)'}")
        if report.cuda.fix:
            lines.append(f"  Fix:           {report.cuda.fix}")

    if report.cache_dir:
        writable_str = "writable" if report.cache_dir.writable else "NOT writable"
        lines.append(f"Cache Directory: {report.cache_dir.path} ({writable_str}, {report.cache_dir.free_gb:.1f} GB free)")
        if report.cache_dir.fix:
            lines.append(f"  Fix:           {report.cache_dir.fix}")

    if report.models:
        lines.append(f"Cached Models:   {report.models.count} installed in {report.models.cache_path}")
        for m in report.models.installed_models:
            lines.append(f"  • {m}")
        if report.models.fix:
            lines.append(f"  Fix:           {report.models.fix}")

    lines.append(f"Desktop GUI:     PySide6 {report.desktop.version or 'unknown version'} ({desktop_state})")
    lines.append(f"Locales:         {locale_text} ({report.localization.directory})")
    if report.localization.error:
        lines.append(f"  Locale detail: {report.localization.error}")
    if report.desktop.error:
        lines.append(f"  Desktop error: {report.desktop.error}")
    return "\n".join(lines)


__all__ = [
    "BinaryDiagnostic",
    "CacheDiagnostic",
    "CatalogInspector",
    "CudaDiagnostic",
    "DesktopDiagnostic",
    "LocalizationDiagnostic",
    "MediaRuntimeDiagnostic",
    "ModelsDiagnostic",
    "PackageDiagnostic",
    "PlatformDiagnostic",
    "PythonDiagnostic",
    "RuntimeInspector",
    "SystemDiagnosticReport",
    "collect_system_diagnostics",
    "render_human_diagnostics",
]

