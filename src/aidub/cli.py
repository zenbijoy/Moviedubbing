"""Typed command-line boundary for operators, automation, and headless CI."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Protocol, TextIO, cast

from pydantic import ValidationError

from aidub import __version__
from aidub.application import OpenedProject, ProjectPackageError, ProjectPackageService
from aidub.pipeline.errors import PipelineError, exit_code_for_error
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


@dataclass(slots=True)
class CliDependencies:
    """Injectable application seams used by command handlers and tests."""

    diagnostics_collector: Callable[[], SystemDiagnosticReport] = collect_system_diagnostics
    dubbing_diagnostics_collector: Callable[[], DubbingDiagnosticReport] = (
        collect_dubbing_diagnostics
    )
    project_service: ProjectService = field(
        default_factory=lambda: ProjectPackageService(
            catalog=ProjectCatalog(default_catalog_path())
        )
    )
    media_probe: MediaProbeService = field(default_factory=MediaProbe)
    media_runtime: MediaRuntimeService = field(default_factory=MediaRuntime)
    derivative_service: DerivativeService = field(default_factory=_default_derivative_service)
    source_fingerprinter: Callable[[Path | str], SourceFingerprint] = full_fingerprint
    desktop_runner: DesktopRunner = _run_desktop


def _write_json(stream: TextIO, payload: object) -> None:
    json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
    stream.write("\n")


def _fraction_payload(value: Fraction | None) -> dict[str, int] | None:
    if value is None:
        return None
    return {"denominator": value.denominator, "numerator": value.numerator}


def _reconciliation_payload(report: ReconciliationReport) -> dict[str, object]:
    return {
        "clean": report.clean,
        "corrupt_objects": list(report.corrupt_objects),
        "errors": list(report.errors),
        "missing_objects": list(report.missing_objects),
        "orphan_objects": list(report.orphan_objects),
        "staged_removed": list(report.staged_removed),
        "staged_retained": list(report.staged_retained),
        "unsafe_entries": list(report.unsafe_entries),
        "valid_objects": list(report.valid_objects),
    }


def _opened_project_payload(opened: OpenedProject, *, operation: str) -> dict[str, object]:
    return {
        "artifact_reconciliation": _reconciliation_payload(opened.artifact_reconciliation),
        "migration": {
            "applied_versions": list(opened.migration.applied_versions),
            "backup_path": opened.migration.backup_path,
            "current_version": opened.migration.current_version,
            "previous_version": opened.migration.previous_version,
        },
        "operation": operation,
        "catalog_registered": opened.catalog_registered,
        "project": {
            "id": opened.project.project_id,
            "name": opened.project.name,
            "path": str(opened.paths.root),
            "source_language": opened.project.settings.source_language,
            "state": opened.project.state.value,
            "video_rate": {
                "denominator": opened.project.settings.video_rate.denominator,
                "numerator": opened.project.settings.video_rate.numerator,
            },
        },
        "recovered_job_ids": list(opened.recovered_job_ids),
        "warnings": list(opened.warnings),
    }


def _container_payload(info: ContainerInfo) -> dict[str, object]:
    return {
        "audio_streams": [
            {
                "channel_layout": stream.channel_layout,
                "channels": stream.channels,
                "codec": stream.codec,
                "duration_ticks": stream.duration_ticks,
                "index": stream.index,
                "language": stream.language,
                "sample_rate": stream.sample_rate,
                "start_ticks": stream.start_ticks,
                "time_base": _fraction_payload(stream.time_base),
            }
            for stream in info.audio_streams
        ],
        "bit_rate": info.bit_rate,
        "chapters": info.chapters,
        "duration_seconds": info.duration_seconds,
        "format_names": list(info.format_names),
        "path": str(info.path),
        "size_bytes": info.size_bytes,
        "subtitle_streams": [
            {
                "codec": stream.codec,
                "forced": stream.forced,
                "hearing_impaired": stream.hearing_impaired,
                "index": stream.index,
                "language": stream.language,
                "time_base": _fraction_payload(stream.time_base),
                "title": stream.title,
            }
            for stream in info.subtitle_streams
        ],
        "video_streams": [
            {
                "average_frame_rate": _fraction_payload(stream.average_frame_rate),
                "codec": stream.codec,
                "color_primaries": stream.color_primaries,
                "color_range": stream.color_range,
                "color_space": stream.color_space,
                "color_transfer": stream.color_transfer,
                "duration_ticks": stream.duration_ticks,
                "field_order": stream.field_order,
                "height": stream.height,
                "index": stream.index,
                "likely_variable_frame_rate": stream.likely_variable_frame_rate,
                "pixel_format": stream.pixel_format,
                "real_frame_rate": _fraction_payload(stream.real_frame_rate),
                "rotation_degrees": stream.rotation_degrees,
                "sample_aspect_ratio": stream.sample_aspect_ratio,
                "start_ticks": stream.start_ticks,
                "time_base": _fraction_payload(stream.time_base),
                "width": stream.width,
            }
            for stream in info.video_streams
        ],
    }


def _localization_values(values: Sequence[str], source_language: str) -> tuple[str, ...]:
    localizations = tuple(
        locale.strip() for value in values for locale in value.split(",") if locale.strip()
    )
    folded = [locale.casefold() for locale in localizations]
    if len(folded) != len(set(folded)):
        raise ValueError("localization language tags must be unique")
    if source_language.casefold() in folded:
        raise ValueError("a localization language must differ from the source language")
    return localizations


def _handle_doctor(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    if getattr(arguments, "dubbing", False):
        dub_report = dependencies.dubbing_diagnostics_collector()
        if arguments.output_json:
            payload = {
                "all_passed": dub_report.all_passed,
                "checks": [
                    {
                        "detail": c.detail,
                        "fix": c.fix,
                        "name": c.name,
                        "ok": c.ok,
                    }
                    for c in dub_report.checks
                ],
                "passed_count": dub_report.passed_count,
                "total_count": dub_report.total_count,
            }
            _write_json(stdout, payload)
        else:
            stdout.write(f"{dub_report.render()}\n")
        if arguments.require_runtime and not dub_report.all_passed:
            return EXIT_RUNTIME_UNAVAILABLE
        return EXIT_OK

    report = dependencies.diagnostics_collector()
    if arguments.output_json:
        _write_json(stdout, report.as_dict())
    else:
        stdout.write(f"{render_human_diagnostics(report)}\n")
    if arguments.require_runtime and not report.media_runtime.operational:
        return EXIT_RUNTIME_UNAVAILABLE
    return EXIT_OK


def _handle_project_create(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    localizations = _localization_values(arguments.localizations, arguments.source_language)
    settings = ProjectSettings(
        video_rate=RationalRate(
            numerator=arguments.frame_rate_numerator,
            denominator=arguments.frame_rate_denominator,
        ),
        source_language=arguments.source_language,
    )
    authorization = SourceAuthorization(
        acknowledged=True,
        acknowledged_by=arguments.operator,
        authority_basis=arguments.rights_basis,
        evidence_reference=arguments.evidence_reference,
    )
    opened = dependencies.project_service.create(
        arguments.path,
        name=arguments.name,
        settings=settings,
        source_authorization=authorization,
        localization_locales=localizations,
        actor_id=arguments.operator,
    )
    payload = _opened_project_payload(opened, operation="created")
    payload["localizations"] = list(localizations)
    if arguments.output_json:
        _write_json(stdout, payload)
    else:
        stdout.write(
            f"Created project {opened.project.name} ({opened.project.project_id})\n"
            f"Path: {opened.paths.root}\n"
            f"Localizations: {', '.join(localizations) or 'none'}\n"
        )
    return EXIT_OK


def _handle_project_validate(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    opened = dependencies.project_service.open(
        arguments.path,
        recover_interrupted=True,
        reconcile_artifacts=True,
    )
    payload = _opened_project_payload(opened, operation="validated")
    clean = opened.artifact_reconciliation.clean
    payload["valid"] = clean
    if arguments.output_json:
        _write_json(stdout, payload)
    else:
        state = "valid" if clean else "requires attention"
        stdout.write(
            f"Project {opened.project.name} is {state}.\n"
            f"Recovered jobs: {len(opened.recovered_job_ids)}\n"
            f"Missing artifacts: {len(opened.artifact_reconciliation.missing_objects)}\n"
            f"Corrupt artifacts: {len(opened.artifact_reconciliation.corrupt_objects)}\n"
            f"Unsafe entries: {len(opened.artifact_reconciliation.unsafe_entries)}\n"
        )
    return EXIT_OK if clean else EXIT_VALIDATION_FAILED


def _handle_media_probe(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    info = dependencies.media_probe.probe(arguments.source)
    if arguments.output_json:
        _write_json(stdout, _container_payload(info))
    else:
        duration = "unknown" if info.duration_seconds is None else f"{info.duration_seconds:.3f}s"
        stdout.write(
            f"Media: {info.path}\n"
            f"Formats: {', '.join(info.format_names) or 'unknown'}\n"
            f"Duration: {duration}\n"
            f"Streams: {len(info.video_streams)} video, {len(info.audio_streams)} audio, "
            f"{len(info.subtitle_streams)} subtitle\n"
        )
    return EXIT_OK


def _derivative_spec(arguments: argparse.Namespace) -> DerivativeSpec:
    if arguments.derivative_kind == "proxy":
        return ProxySpec(
            width=arguments.width,
            height=arguments.height,
            frame_rate=RationalRate(
                numerator=arguments.frame_rate_numerator,
                denominator=arguments.frame_rate_denominator,
            ),
            video_stream=arguments.video_stream,
            audio_stream=arguments.audio_stream,
        )
    if arguments.derivative_kind == "thumbnail":
        return ThumbnailSpec(
            position=RationalTime(
                ticks=arguments.position_ticks,
                rate=RationalRate(
                    numerator=arguments.position_rate_numerator,
                    denominator=arguments.position_rate_denominator,
                ),
            ),
            width=arguments.width,
            height=arguments.height,
            video_stream=arguments.video_stream,
        )
    return WaveformSpec(
        width=arguments.width,
        height=arguments.height,
        audio_stream=arguments.audio_stream,
        foreground_color=arguments.color,
    )


def _handle_media_derivative(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    runtime = dependencies.media_runtime.inspect()
    fingerprint = dependencies.source_fingerprinter(arguments.source)
    if fingerprint.full_sha256 is None:
        raise ValueError("derived media requires a complete source SHA-256 fingerprint")
    result = dependencies.derivative_service.generate(
        ffmpeg_executable=runtime.ffmpeg,
        ffmpeg_version=runtime.version,
        source=arguments.source,
        source_sha256=fingerprint.full_sha256,
        target=arguments.target,
        spec=_derivative_spec(arguments),
        timeout_seconds=arguments.timeout_seconds,
    )
    payload = {
        "byte_length": result.byte_length,
        "cache_key": result.cache_key,
        "kind": result.kind.value,
        "operation": "generated",
        "path": str(result.path),
        "sha256": result.sha256,
    }
    if arguments.output_json:
        _write_json(stdout, payload)
    else:
        stdout.write(f"Generated {result.kind.value}: {result.path}\nSHA-256: {result.sha256}\n")
    return EXIT_OK


def _handle_gui(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    _stdout: TextIO,
    _stderr: TextIO,
) -> int:
    qt_arguments = list(arguments.qt_arguments)
    if qt_arguments[:1] == ["--"]:
        qt_arguments = qt_arguments[1:]
    return dependencies.desktop_runner(qt_arguments, locale=arguments.locale)


def _handle_dub(
    arguments: argparse.Namespace,
    _dependencies: CliDependencies,
    stdout: TextIO,
    _stderr: TextIO,
) -> int:
    from dataclasses import asdict

    from aidub.pipeline.config import PipelineConfig
    from aidub.pipeline.engine import DubbingEngine

    if getattr(arguments, "overwrite", False) and arguments.output.is_file():
        arguments.output.unlink()

    fast = getattr(arguments, "fast", False)
    keep_music = False if fast else getattr(arguments, "keep_music", True)
    diarize = False if fast else getattr(arguments, "diarize", True)

    cfg = PipelineConfig(
        input=arguments.input,
        output=arguments.output,
        src_lang=arguments.source_lang,
        tgt_lang=arguments.target_lang,
        work_dir=arguments.work_dir,
        keep_music=keep_music,
        diarize=diarize,
        fast=fast,
        lipsync=getattr(arguments, "lipsync", False),
        lipsync_tier=getattr(arguments, "lipsync_tier", "preview_fast"),
        asr_model=arguments.asr_model,
        voice_name=arguments.voice_name,
        voice_engine=getattr(arguments, "voice_engine", "chatterbox"),
        overwrite=getattr(arguments, "overwrite", False),
    )

    engine = DubbingEngine(cfg)
    outputs = engine.run()

    if arguments.output_json:
        _write_json(stdout, asdict(outputs))
    else:
        stdout.write(f"Successfully generated dubbed video: {outputs.dubbed_video}\n")
        if outputs.lipsynced_video:
            stdout.write(f"Lip-synced video: {outputs.lipsynced_video}\n")
        stdout.write(f"Bilingual SRT: {outputs.bilingual_srt}\n")

    return EXIT_OK


def _handle_kaggle(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    del dependencies, stderr
    from aidub.cloud.kaggle_accelerator import (
        KaggleClient,
        KaggleNotebookBuilder,
    )

    if getattr(arguments, "check", False):
        client = KaggleClient()
        ok, msg = client.check_connection()
        stdout.write(f"Kaggle Connection: {'[OK]' if ok else '[FAILED]'} {msg}\n")
        return EXIT_OK if ok else EXIT_FAILURE

    out_nb = getattr(arguments, "export_notebook", None)
    if out_nb:
        dest = KaggleNotebookBuilder.export_to_file(
            out_nb,
            target_language=arguments.target_lang,
            voice_engine=arguments.voice_engine,
        )
        stdout.write(f"✓ Kaggle GPU dubbing notebook created: {dest}\n")
        return EXIT_OK

    stdout.write(
        "Kaggle Cloud Accelerator:\n"
        "  --check               Test Kaggle API credentials\n"
        "  --export-notebook <p> Generate GPU dubbing notebook (.ipynb)\n"
    )
    return EXIT_OK


CommandHandler = Callable[
    [argparse.Namespace, CliDependencies, TextIO, TextIO],
    int,
]


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI grammar without resolving optional dependencies."""

    parser = argparse.ArgumentParser(
        prog="aidub",
        description="AI Movie Dubbing Studio operator command line",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="inspect local runtime readiness")
    doctor.add_argument("--json", action="store_true", dest="output_json")
    doctor.add_argument(
        "--dubbing",
        action="store_true",
        help="inspect readiness of end-to-end dubbing pipeline dependencies",
    )
    doctor.add_argument(
        "--require-runtime",
        action="store_true",
        help="return exit code 3 when FFmpeg or ffprobe is not operational",
    )
    doctor.set_defaults(handler=_handle_doctor)

    project = commands.add_parser("project", help="create and validate project packages")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    create = project_commands.add_parser("create", help="create an atomic .aidub package")
    create.add_argument("path", type=Path, help="destination path; .aidub is added if omitted")
    create.add_argument("--name", required=True, help="project display name")
    create.add_argument("--source-language", required=True, help="BCP-47 source language")
    create.add_argument("--frame-rate-numerator", type=int, default=24_000)
    create.add_argument("--frame-rate-denominator", type=int, default=1_001)
    create.add_argument("--operator", required=True, help="operator recording authorization")
    create.add_argument("--rights-basis", required=True, help="legal/licensing authority basis")
    create.add_argument("--evidence-reference", help="rights evidence identifier or URI")
    create.add_argument(
        "--localization",
        "--localizations",
        action="extend",
        nargs="+",
        default=[],
        dest="localizations",
        metavar="LOCALE",
        help="target BCP-47 locale(s); repeat or provide a comma-separated list",
    )
    create.add_argument("--json", action="store_true", dest="output_json")
    create.set_defaults(handler=_handle_project_create)

    validate = project_commands.add_parser(
        "validate",
        help="migrate, recover, and reconcile an existing package",
    )
    validate.add_argument("path", type=Path)
    validate.add_argument("--json", action="store_true", dest="output_json")
    validate.set_defaults(handler=_handle_project_validate)

    dub = commands.add_parser("dub", help="execute end-to-end AI movie dubbing engine")
    dub.add_argument("--input", "-i", type=Path, required=True, help="input media file path")
    dub.add_argument(
        "--output", "-o", type=Path, required=True, help="output dubbed video MP4 path"
    )
    dub.add_argument(
        "--target-lang", "-t", default="bn", help="target language code (default: bn for Bengali)"
    )
    dub.add_argument(
        "--source-lang", "-s", default="auto", help="source language code (default: auto)"
    )
    dub.add_argument("--work-dir", type=Path, help="temporary work directory for checkpoints")
    dub.add_argument(
        "--asr-model", default="large-v3", help="Faster-Whisper model size (default: large-v3)"
    )
    dub.add_argument("--voice-name", help="optional Edge TTS voice name")
    dub.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help="fast quality profile: skip diarization and music separation",
    )
    dub.add_argument(
        "--no-music",
        action="store_false",
        dest="keep_music",
        help="disable background music track retention",
    )
    dub.add_argument(
        "--no-diarization",
        action="store_false",
        dest="diarize",
        default=True,
        help="disable PyAnnote speaker diarization; one configured target voice will be used",
    )
    dub.add_argument(
        "--lipsync",
        action="store_true",
        default=False,
        help="enable AI lip-sync synthesis for face-matching dialogue animation",
    )
    dub.add_argument(
        "--lipsync-tier",
        choices=["preview_fast", "cinema_quality"],
        default="preview_fast",
        help="lip-sync rendering tier: preview_fast (MuseTalk) or cinema_quality (LatentSync)",
    )
    dub.add_argument(
        "--overwrite",
        "--force",
        action="store_true",
        dest="overwrite",
        help="overwrite existing output file if present",
    )
    dub.add_argument(
        "--voice-engine",
        choices=["chatterbox", "edge_tts", "elevenlabs", "rvc"],
        default="chatterbox",
        help="AI voice synthesis engine: chatterbox (default), edge_tts, elevenlabs, or rvc",
    )
    dub.add_argument("--json", action="store_true", dest="output_json")
    dub.set_defaults(handler=_handle_dub)

    media = commands.add_parser("media", help="inspect local media")
    media_commands = media.add_subparsers(dest="media_command", required=True)
    probe = media_commands.add_parser("probe", help="run bounded FFprobe inspection")
    probe.add_argument("source", type=Path)
    probe.add_argument("--json", action="store_true", dest="output_json")
    probe.set_defaults(handler=_handle_media_probe)

    def add_derivative_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("source", type=Path)
        command.add_argument("target", type=Path)
        command.add_argument("--width", type=int, default=1280)
        command.add_argument("--height", type=int, default=720)
        command.add_argument("--video-stream", type=int, default=0)
        command.add_argument("--audio-stream", type=int, default=0)
        command.add_argument("--timeout-seconds", type=float, default=3_600.0)
        command.add_argument("--json", action="store_true", dest="output_json")

    proxy = media_commands.add_parser("proxy", help="generate a deterministic proxy derivative")
    add_derivative_arguments(proxy)
    proxy.add_argument("--frame-rate-numerator", type=int, default=24_000)
    proxy.add_argument("--frame-rate-denominator", type=int, default=1_001)
    proxy.set_defaults(handler=_handle_media_derivative, derivative_kind="proxy")

    thumbnail = media_commands.add_parser(
        "thumbnail", help="generate a deterministic thumbnail derivative"
    )
    add_derivative_arguments(thumbnail)
    thumbnail.add_argument("--position-ticks", type=int, required=True)
    thumbnail.add_argument("--position-rate-numerator", type=int, default=24_000)
    thumbnail.add_argument("--position-rate-denominator", type=int, default=1_001)
    thumbnail.set_defaults(handler=_handle_media_derivative, derivative_kind="thumbnail")

    waveform = media_commands.add_parser("waveform", help="generate a waveform derivative")
    add_derivative_arguments(waveform)
    waveform.add_argument("--color", default="#4A90E2")
    waveform.set_defaults(handler=_handle_media_derivative, derivative_kind="waveform")

    gui = commands.add_parser("gui", help="launch the optional PySide6 desktop shell")
    gui.add_argument("--locale", help="requested UI locale")
    gui.add_argument(
        "qt_arguments",
        nargs=argparse.REMAINDER,
        help="arguments passed to Qt after an optional -- separator",
    )
    gui.set_defaults(handler=_handle_gui)

    kaggle = commands.add_parser("kaggle", help="Kaggle free Cloud GPU accelerator tools")
    kaggle.add_argument("--export-notebook", type=Path, help="export a ready-to-run Kaggle GPU dubbing notebook (.ipynb)")
    kaggle.add_argument("--check", action="store_true", help="verify Kaggle API credentials and connectivity")
    kaggle.add_argument("--target-lang", default="bn", help="target language for dubbing notebook (default: bn)")
    kaggle.add_argument("--voice-engine", default="chatterbox", help="voice engine for notebook (default: chatterbox)")
    kaggle.set_defaults(handler=_handle_kaggle)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    dependencies: CliDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse and execute one command, returning a process-compatible exit code."""

    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    arguments = build_parser().parse_args(argv)
    handler = cast("CommandHandler", arguments.handler)
    try:
        return handler(arguments, dependencies or CliDependencies(), output, errors)
    except KeyboardInterrupt:
        errors.write("error: operation cancelled by operator\n")
        return 130
    except PipelineError as error:
        errors.write(f"error: {error.message}\n")
        return exit_code_for_error(error)
    except (MediaProbeError, ProjectPackageError, ValidationError, OSError, ValueError) as error:
        errors.write(f"error: {error}\n")
        return EXIT_FAILURE
    except Exception as error:
        errors.write(f"error: {error}\n")
        return EXIT_FAILURE


__all__ = [
    "EXIT_FAILURE",
    "EXIT_OK",
    "EXIT_RUNTIME_UNAVAILABLE",
    "EXIT_USAGE",
    "EXIT_VALIDATION_FAILED",
    "CliDependencies",
    "build_parser",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
