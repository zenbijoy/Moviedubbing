import json
from collections.abc import Sequence
from io import StringIO
from pathlib import Path

from aidub.application import ProjectPackageService
from aidub.cli import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_RUNTIME_UNAVAILABLE,
    CliDependencies,
    build_parser,
    main,
)
from aidub.diagnostics import (
    DubbingCheckResult,
    DubbingDiagnosticReport,
    SystemDiagnosticReport,
    collect_system_diagnostics,
)
from aidub.media import ContainerInfo, MediaRuntimeInfo


class StubCatalog:
    directory = Path("C:/aidub/i18n")

    def available_locales(self) -> tuple[str, ...]:
        return ("en", "bn-BD", "hi-IN")


class MissingRuntime:
    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        raise FileNotFoundError(f"runtime missing ({timeout_seconds:g}s)")


class StubProbe:
    def __init__(self, result: ContainerInfo) -> None:
        self.result = result
        self.sources: list[Path | str] = []

    def probe(self, source: Path | str) -> ContainerInfo:
        self.sources.append(source)
        return self.result


def _diagnostics_without_runtime() -> SystemDiagnosticReport:
    return collect_system_diagnostics(
        runtime=MissingRuntime(),
        catalog_repository=StubCatalog(),
        binary_finder=lambda _name: None,
        desktop_available=False,
        package_version_resolver=lambda _name: "6.9.1",
    )


def test_doctor_is_machine_readable_and_runtime_requirement_controls_exit() -> None:
    dependencies = CliDependencies(diagnostics_collector=_diagnostics_without_runtime)
    output = StringIO()
    errors = StringIO()

    result = main(
        ["doctor", "--json"],
        dependencies=dependencies,
        stdout=output,
        stderr=errors,
    )

    assert result == EXIT_OK
    assert json.loads(output.getvalue())["media_runtime"]["operational"] is False
    assert errors.getvalue() == ""

    required_output = StringIO()
    result = main(
        ["doctor", "--json", "--require-runtime"],
        dependencies=dependencies,
        stdout=required_output,
        stderr=StringIO(),
    )
    assert result == EXIT_RUNTIME_UNAVAILABLE


def test_doctor_dubbing_reports_readiness_and_supports_json() -> None:
    mock_report = DubbingDiagnosticReport(
        checks=[
            DubbingCheckResult(name="ffmpeg/ffprobe", ok=True, detail="ffmpeg v7.1"),
            DubbingCheckResult(name="faster-whisper", ok=True, detail="v1.2.1 installed"),
            DubbingCheckResult(
                name="pyannote token", ok=False, detail="token missing", fix="Set PYANNOTE_TOKEN"
            ),
            DubbingCheckResult(name="demucs", ok=True, detail="v4.1.0 installed"),
            DubbingCheckResult(name="edge-tts reachability", ok=True, detail="reachable"),
            DubbingCheckResult(name="llm provider", ok=True, detail="Gemini configured"),
        ]
    )
    dependencies = CliDependencies(dubbing_diagnostics_collector=lambda: mock_report)
    output = StringIO()

    result = main(
        ["doctor", "--dubbing", "--json"],
        dependencies=dependencies,
        stdout=output,
        stderr=StringIO(),
    )
    assert result == EXIT_OK
    data = json.loads(output.getvalue())
    assert data["all_passed"] is False
    assert data["passed_count"] == 5
    assert data["total_count"] == 6
    assert any(c["name"] == "pyannote token" and c["ok"] is False for c in data["checks"])

    human_output = StringIO()
    result = main(
        ["doctor", "--dubbing"], dependencies=dependencies, stdout=human_output, stderr=StringIO()
    )
    assert result == EXIT_OK
    assert "=== aidub dubbing pipeline readiness ===" in human_output.getvalue()
    assert "Set PYANNOTE_TOKEN" in human_output.getvalue()

    required_output = StringIO()
    result = main(
        ["doctor", "--dubbing", "--require-runtime"],
        dependencies=dependencies,
        stdout=required_output,
        stderr=StringIO(),
    )
    assert result == EXIT_RUNTIME_UNAVAILABLE


def test_project_create_and_validate_are_end_to_end(tmp_path: Path) -> None:
    destination = tmp_path / "International Feature"
    dependencies = CliDependencies(project_service=ProjectPackageService())
    create_output = StringIO()

    result = main(
        [
            "project",
            "create",
            str(destination),
            "--name",
            "International Feature",
            "--source-language",
            "en-US",
            "--frame-rate-numerator",
            "24000",
            "--frame-rate-denominator",
            "1001",
            "--operator",
            "studio.operator",
            "--rights-basis",
            "Licensed master agreement MSA-2026-0042",
            "--evidence-reference",
            "rights://MSA-2026-0042",
            "--localizations",
            "bn-BD",
            "hi-IN",
            "--json",
        ],
        dependencies=dependencies,
        stdout=create_output,
        stderr=StringIO(),
    )

    assert result == EXIT_OK
    created = json.loads(create_output.getvalue())
    package = destination.with_suffix(".aidub")
    assert created["operation"] == "created"
    assert created["localizations"] == ["bn-BD", "hi-IN"]
    assert created["project"]["video_rate"] == {"denominator": 1001, "numerator": 24000}
    assert package.is_dir()
    assert (package / "localizations" / "bn-BD").is_dir()
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_authorization"]["acknowledged_by"] == "studio.operator"
    assert manifest["source_authorization"]["authority_basis"].startswith("Licensed")

    validate_output = StringIO()
    result = main(
        ["project", "validate", str(package), "--json"],
        dependencies=dependencies,
        stdout=validate_output,
        stderr=StringIO(),
    )
    validated = json.loads(validate_output.getvalue())
    assert result == EXIT_OK
    assert validated["operation"] == "validated"
    assert validated["valid"] is True
    assert validated["artifact_reconciliation"]["clean"] is True
    assert validated["recovered_job_ids"] == []


def test_project_create_rejects_source_as_localization(tmp_path: Path) -> None:
    errors = StringIO()
    result = main(
        [
            "project",
            "create",
            str(tmp_path / "invalid"),
            "--name",
            "Invalid",
            "--source-language",
            "en",
            "--operator",
            "operator",
            "--rights-basis",
            "licensed",
            "--localization",
            "EN",
        ],
        dependencies=CliDependencies(project_service=ProjectPackageService()),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == EXIT_FAILURE
    assert "must differ" in errors.getvalue()
    assert not (tmp_path / "invalid.aidub").exists()


def test_media_probe_and_gui_use_injected_boundaries(tmp_path: Path) -> None:
    media_path = tmp_path / "source.mkv"
    probe = StubProbe(
        ContainerInfo(
            path=media_path,
            format_names=("matroska", "webm"),
            duration_seconds=12.5,
            bit_rate=1_000_000,
            size_bytes=2_048,
            video_streams=(),
            audio_streams=(),
            subtitle_streams=(),
            chapters=2,
        )
    )
    desktop_calls: list[tuple[list[str], str | None]] = []

    def run_desktop(
        argv: Sequence[str] | None = None,
        *,
        locale: str | None = None,
    ) -> int:
        desktop_calls.append((list(argv or ()), locale))
        return 7

    dependencies = CliDependencies(media_probe=probe, desktop_runner=run_desktop)
    output = StringIO()
    result = main(
        ["media", "probe", str(media_path), "--json"],
        dependencies=dependencies,
        stdout=output,
        stderr=StringIO(),
    )
    payload = json.loads(output.getvalue())
    assert result == EXIT_OK
    assert payload["format_names"] == ["matroska", "webm"]
    assert payload["chapters"] == 2
    assert probe.sources == [media_path]

    result = main(
        ["gui", "--locale", "bn-BD", "--", "-platform", "offscreen"],
        dependencies=dependencies,
        stdout=StringIO(),
        stderr=StringIO(),
    )
    assert result == 7
    assert desktop_calls == [(["-platform", "offscreen"], "bn-BD")]


def test_dub_cli_exposes_real_pipeline_options(tmp_path: Path) -> None:
    arguments = build_parser().parse_args(
        [
            "dub",
            "--input",
            str(tmp_path / "source.mp4"),
            "--output",
            str(tmp_path / "dubbed.mp4"),
            "--source-lang",
            "en-US",
            "--target-lang",
            "bn",
            "--asr-model",
            "small",
            "--voice-name",
            "bn-BD-NabanitaNeural",
            "--no-music",
            "--no-diarization",
        ]
    )
    assert arguments.source_lang == "en-US"
    assert arguments.target_lang == "bn"
    assert arguments.asr_model == "small"
    assert arguments.voice_name == "bn-BD-NabanitaNeural"
    assert arguments.keep_music is False
    assert arguments.diarize is False
