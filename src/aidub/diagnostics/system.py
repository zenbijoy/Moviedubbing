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
class MediaRuntimeDiagnostic:
    operational: bool
    ffmpeg: BinaryDiagnostic
    ffprobe: BinaryDiagnostic
    version: str | None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "error": self.error,
            "ffmpeg": self.ffmpeg.as_dict(),
            "ffprobe": self.ffprobe.as_dict(),
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

    def as_dict(self) -> dict[str, object]:
        """Return a stable, JSON-compatible operator contract."""

        return {
            "desktop": self.desktop.as_dict(),
            "localization": self.localization.as_dict(),
            "media_runtime": self.media_runtime.as_dict(),
            "package": self.package.as_dict(),
            "platform": self.platform.as_dict(),
            "python": self.python.as_dict(),
            "schema_version": self.schema_version,
        }


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
        return MediaRuntimeDiagnostic(
            operational=False,
            ffmpeg=_located_binary("ffmpeg", finder),
            ffprobe=_located_binary("ffprobe", finder),
            version=None,
            error=_safe_error(error),
        )
    return MediaRuntimeDiagnostic(
        operational=True,
        ffmpeg=BinaryDiagnostic(available=True, path=str(info.ffmpeg)),
        ffprobe=BinaryDiagnostic(available=True, path=str(info.ffprobe)),
        version=info.version,
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
    )


def render_human_diagnostics(report: SystemDiagnosticReport) -> str:
    """Render a compact human-readable report from the machine contract."""

    python_state = "supported" if report.python.supported else "unsupported"
    locale_text = ", ".join(report.localization.locales) or "none"
    desktop_state = "available" if report.desktop.available else "unavailable"
    runtime_state = "ready" if report.media_runtime.operational else "not ready"
    ffmpeg_path = report.media_runtime.ffmpeg.path or "not found"
    ffprobe_path = report.media_runtime.ffprobe.path or "not found"
    lines = [
        "AI Movie Dubbing Studio diagnostics",
        f"Package: {report.package.name} {report.package.version}",
        (f"Python: {report.python.implementation} {report.python.version} ({python_state})"),
        (
            f"Platform: {report.platform.system} {report.platform.release}; "
            f"{report.platform.machine}; {report.platform.pointer_bits}-bit"
        ),
        f"Locales: {locale_text} ({report.localization.directory})",
        f"FFmpeg: {ffmpeg_path}",
        f"ffprobe: {ffprobe_path}",
        f"Media runtime: {runtime_state}",
        (f"Desktop: PySide6 {report.desktop.version or 'unknown version'} ({desktop_state})"),
    ]
    if report.media_runtime.error:
        lines.append(f"Media detail: {report.media_runtime.error}")
    if report.localization.error:
        lines.append(f"Locale detail: {report.localization.error}")
    if report.desktop.error:
        lines.append(f"Desktop detail: {report.desktop.error}")
    return "\n".join(lines)


__all__ = [
    "BinaryDiagnostic",
    "CatalogInspector",
    "DesktopDiagnostic",
    "LocalizationDiagnostic",
    "MediaRuntimeDiagnostic",
    "PackageDiagnostic",
    "PlatformDiagnostic",
    "PythonDiagnostic",
    "RuntimeInspector",
    "SystemDiagnosticReport",
    "collect_system_diagnostics",
    "render_human_diagnostics",
]
