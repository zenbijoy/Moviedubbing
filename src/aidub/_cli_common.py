"""Common imports, constants, and protocols for the CLI modules."""

from __future__ import annotations


import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Protocol, TextIO, cast

from pydantic import ValidationError

from aidub import __version__
from aidub.application import OpenedProject, ProjectPackageError, ProjectPackageService
from aidub.diagnostics import (
    DubbingDiagnosticReport,
    SystemDiagnosticReport,
    collect_dubbing_diagnostics,
    collect_system_diagnostics,
    render_human_diagnostics,
)
from aidub.domain.project import ProjectSettings
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate, RationalTime
from aidub.infrastructure.artifacts import ReconciliationReport
from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path
from aidub.media import (
    ContainerInfo,
    DerivativeGenerator,
    DerivativeResult,
    FFprobeDerivativeValidator,
    MediaProbe,
    MediaProbeError,
    MediaRuntime,
    MediaRuntimeInfo,
    ProxySpec,
    SourceFingerprint,
    ThumbnailSpec,
    WaveformSpec,
    full_fingerprint,
)
from aidub.media.commands import DerivativeSpec
from aidub.pipeline.errors import PipelineError, exit_code_for_error

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_RUNTIME_UNAVAILABLE = 3
EXIT_VALIDATION_FAILED = 4


class ProjectService(Protocol):
    def create(
        self,
        destination: Path | str,
        *,
        name: str,
        settings: ProjectSettings,
        source_authorization: SourceAuthorization,
        localization_locales: Sequence[str] = (),
        actor_id: str | None = None,
    ) -> OpenedProject:
        """Create and publish one project package."""

    def open(
        self,
        package: Path | str,
        *,
        recover_interrupted: bool = True,
        reconcile_artifacts: bool = True,
    ) -> OpenedProject:
        """Open, recover, and validate one project package."""


class MediaProbeService(Protocol):
    def probe(self, source: Path | str) -> ContainerInfo:
        """Probe a local media file."""


class MediaRuntimeService(Protocol):
    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        """Return one verified local FFmpeg/ffprobe runtime."""


class DerivativeService(Protocol):
    def generate(
        self,
        *,
        ffmpeg_executable: Path | str,
        ffmpeg_version: str,
        source: Path | str,
        source_sha256: str,
        target: Path | str,
        spec: DerivativeSpec,
        timeout_seconds: float = 3_600.0,
    ) -> DerivativeResult:
        """Generate and atomically publish one derived-media output."""


class DesktopRunner(Protocol):
    def __call__(
        self,
        argv: Sequence[str] | None = None,
        *,
        locale: str | None = None,
    ) -> int:
        """Run the optional desktop application."""


def _run_desktop(
    argv: Sequence[str] | None = None,
    *,
    locale: str | None = None,
) -> int:
    from aidub.ui.application import run_desktop

    return run_desktop(argv, locale=locale)


def _default_derivative_service() -> DerivativeGenerator:
    return DerivativeGenerator(output_validator=FFprobeDerivativeValidator(MediaProbe()))


