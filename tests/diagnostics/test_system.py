from importlib.metadata import PackageNotFoundError
from pathlib import Path

from aidub.diagnostics import collect_system_diagnostics, render_human_diagnostics
from aidub.media import MediaRuntimeInfo


class StubCatalog:
    directory = Path("C:/aidub/i18n")

    def available_locales(self) -> tuple[str, ...]:
        return ("en", "bn-BD", "hi-IN")


class ReadyRuntime:
    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        assert timeout_seconds == 5.0
        return MediaRuntimeInfo(
            ffmpeg=Path("C:/runtime/ffmpeg.exe"),
            ffprobe=Path("C:/runtime/ffprobe.exe"),
            version="7.1.1",
        )


class FailedRuntime:
    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        raise FileNotFoundError(f"ffprobe missing after {timeout_seconds:g}s")


def _missing_distribution(_name: str) -> str:
    raise PackageNotFoundError


def test_collects_stable_local_readiness_contract() -> None:
    report = collect_system_diagnostics(
        runtime=ReadyRuntime(),
        catalog_repository=StubCatalog(),
        binary_finder=lambda _name: None,
        desktop_available=False,
        package_version_resolver=_missing_distribution,
    )

    payload = report.as_dict()
    package = payload["package"]
    localization = payload["localization"]
    desktop = payload["desktop"]
    assert isinstance(package, dict)
    assert isinstance(localization, dict)
    assert isinstance(desktop, dict)
    assert payload["schema_version"] == 1
    assert package["name"] == "aidub-studio"
    assert localization["locales"] == ["en", "bn-BD", "hi-IN"]
    assert payload["media_runtime"] == {
        "error": None,
        "ffmpeg": {"available": True, "path": str(Path("C:/runtime/ffmpeg.exe"))},
        "ffprobe": {"available": True, "path": str(Path("C:/runtime/ffprobe.exe"))},
        "operational": True,
        "version": "7.1.1",
    }
    assert desktop["available"] is False


def test_failed_runtime_reports_each_discovered_binary_without_raising() -> None:
    binaries = {"ffmpeg": "C:/runtime/ffmpeg.exe"}
    report = collect_system_diagnostics(
        runtime=FailedRuntime(),
        catalog_repository=StubCatalog(),
        binary_finder=binaries.get,
        desktop_available=True,
        package_version_resolver=lambda _name: "6.9.1",
    )

    assert report.media_runtime.operational is False
    assert report.media_runtime.ffmpeg.available is True
    assert report.media_runtime.ffprobe.available is False
    assert report.media_runtime.error == "FileNotFoundError: ffprobe missing after 5s"
    assert report.desktop.version == "6.9.1"

    human = render_human_diagnostics(report)
    assert "Media runtime: not ready" in human
    assert "Locales: en, bn-BD, hi-IN" in human
    assert "Desktop: PySide6 6.9.1 (available)" in human
