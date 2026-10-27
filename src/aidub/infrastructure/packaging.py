"""
Windows Standalone Packaging & Distribution Infrastructure.

Provides assembly, resource bundling, launcher generation, and verification
for standalone 64-bit Windows distributions.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PackagingSpec:
    app_name: str = "MovieDubbingStudio"
    version: str = "0.1.0"
    source_dir: Path = Path("src/aidub")
    output_dir: Path = Path("dist/MovieDubbingStudio_win64")
    resources_dir: Path = Path("resources")
    include_ffmpeg: bool = True
    copy_ffmpeg_binaries: bool = True


class WindowsPackager:
    """
    Assembles standalone Windows distribution layout and verifies binary dependencies.
    """

    def __init__(self, spec: PackagingSpec | None = None) -> None:
        self.spec = spec or PackagingSpec()

    def assemble_distribution(self, output_dir: Path | None = None) -> Path:
        """
        Assemble standalone distribution directory structure.
        """
        out = output_dir or self.spec.output_dir
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)

        bin_dir = out / "bin"
        lib_dir = out / "lib"
        res_dir = out / "resources"
        models_dir = out / "models"
        docs_dir = out / "docs"

        for d in (bin_dir, lib_dir, res_dir, models_dir, docs_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Copy application source tree to lib/aidub
        target_aidub = lib_dir / "aidub"
        if target_aidub.exists():
            shutil.rmtree(target_aidub)

        if self.spec.source_dir.exists():
            shutil.copytree(self.spec.source_dir, target_aidub)
            logger.info("Copied application source tree to %s", target_aidub)

        # 2. Copy resources (i18n, themes, etc.)
        if self.spec.resources_dir.exists():
            for item in self.spec.resources_dir.iterdir():
                dest = res_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        # 3. Detect FFmpeg and configure bin/
        self._configure_bin_directory(bin_dir)

        # 4. Configure models documentation in models/
        self._configure_models_directory(models_dir)

        # 5. Create GUI launcher scripts
        self._create_launchers(out)

        # 6. Write manifest and licensing
        self._write_metadata(out)

        logger.info("packaging: assembled distribution at %s", out)
        return out

    def _configure_bin_directory(self, bin_dir: Path) -> None:
        """Detect host FFmpeg/FFprobe and create binaries or documentation."""
        # Resolve using the same logic as aidub.media.ffmpeg_ops
        try:
            from aidub.media.ffmpeg_ops import _ffmpeg_exe, _ffprobe_exe
            ffmpeg_path = _ffmpeg_exe()
            ffprobe_path = _ffprobe_exe()
        except Exception:
            ffmpeg_path = shutil.which("ffmpeg")
            ffprobe_path = shutil.which("ffprobe")

        if ffmpeg_path and self.spec.copy_ffmpeg_binaries:
            try:
                shutil.copy2(ffmpeg_path, bin_dir / "ffmpeg.exe")
                if ffprobe_path:
                    shutil.copy2(ffprobe_path, bin_dir / "ffprobe.exe")
                logger.info("Bundled FFmpeg binaries into bin/")
            except Exception as e:
                logger.warning("Could not copy FFmpeg binaries: %s", e)

        readme_ffmpeg = bin_dir / "README_FFMPEG.txt"
        detected_info = (
            f"Detected on host at: {ffmpeg_path}\n"
            if ffmpeg_path
            else "Not detected in system PATH.\n"
        )
        readme_ffmpeg.write_text(
            "Movie Dubbing Studio - External Multimedia Binary Requirements\n"
            "===============================================================\n\n"
            "FFmpeg and FFprobe are required for video and audio demuxing, remuxing,\n"
            "waveform generation, and final rendering.\n\n"
            f"Status: {detected_info}\n"
            "INSTRUCTIONS:\n"
            "1. You may place 'ffmpeg.exe' and 'ffprobe.exe' directly in this 'bin/' folder,\n"
            "   OR ensure FFmpeg is installed and added to your system PATH.\n"
            "2. Download official Windows builds from: https://www.gyan.dev/ffmpeg/builds/\n"
            "   or https://github.com/BtbN/FFmpeg-Builds/releases\n"
            "3. Licensing: FFmpeg is licensed under the LGPL v2.1+ (or GPL v2+ depending\n"
            "   on build configuration). It is an external tool invoked via subprocess\n"
            "   and is not statically linked with Movie Dubbing Studio.\n",
            encoding="utf-8",
        )

    def _configure_models_directory(self, models_dir: Path) -> None:
        """Document external AI model caches and licensing."""
        readme_models = models_dir / "README_MODELS.txt"
        readme_models.write_text(
            "Movie Dubbing Studio - AI Models & External Weights\n"
            "===================================================\n\n"
            "To keep distribution downloads lightweight and comply with model licenses,\n"
            "pre-trained AI models are downloaded on demand or user consent.\n\n"
            "SUPPORTED ENGINES & CACHE DIRECTORIES:\n"
            "1. ASR (Whisper): faster-whisper\n"
            "   - Models: tiny, base, small, medium, large-v3\n"
            "   - Cache location: %USERPROFILE%\\.cache\\huggingface\\hub or local directory\n"
            "   - License: MIT License (OpenAI)\n\n"
            "2. Source Separation: Demucs (htdemucs)\n"
            "   - Cache location: %USERPROFILE%\\.cache\\torch\\hub\\checkpoints\n"
            "   - License: MIT License (Meta Research)\n\n"
            "3. Speaker Diarization: PyAnnote Audio 3.1\n"
            "   - Gated model requiring HuggingFace access token (HF_TOKEN)\n"
            "   - License: MIT / CC-BY-NC-4.0\n\n"
            "4. Speech Synthesis (TTS): Edge-TTS & Local TTS\n"
            "   - Online cloud engine requires active internet; no local weights required.\n"
            "   - Local cached synthesized audio is stored in project-local or user cache.\n\n"
            "OFFLINE DEPLOYMENT:\n"
            "For air-gapped workstations, pre-download models and place them into the\n"
            "standard HuggingFace/Torch cache folders before running.\n",
            encoding="utf-8",
        )

    def _create_launchers(self, out: Path) -> None:
        """Create batch and PowerShell launchers."""
        # MovieDubbingStudio.bat (Desktop UI)
        launcher_bat = out / "MovieDubbingStudio.bat"
        launcher_bat.write_text(
            "@echo off\n"
            "setlocal\n"
            'set "APP_DIR=%~dp0"\n'
            'set "PATH=%APP_DIR%bin;%PATH%"\n'
            'set "PYTHONPATH=%APP_DIR%lib;%PYTHONPATH%"\n\n'
            "if defined PYTHON (\n"
            '    set "PY_EXE=%PYTHON%"\n'
            ') else if exist "%APP_DIR%bin\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%bin\\python.exe"\n'
            ') else if exist "%APP_DIR%..\\.venv\\Scripts\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%..\\.venv\\Scripts\\python.exe"\n'
            ') else if exist "%APP_DIR%..\\..\\.venv\\Scripts\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%..\\..\\.venv\\Scripts\\python.exe"\n'
            ") else (\n"
            '    set "PY_EXE=python"\n'
            ")\n\n"
            "echo Starting Movie Dubbing Studio AI Desktop...\n"
            '"%PY_EXE%" -m aidub.ui.application %*\n'
            "endlocal\n",
            encoding="utf-8",
        )

        # MovieDubbingStudio.ps1 (PowerShell Desktop UI)
        launcher_ps1 = out / "MovieDubbingStudio.ps1"
        launcher_ps1.write_text(
            "# Movie Dubbing Studio PowerShell Launcher\n"
            "$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            '$env:PATH = "$AppDir\\bin;" + $env:PATH\n'
            '$env:PYTHONPATH = "$AppDir\\lib;" + $env:PYTHONPATH\n\n'
            "$PyExe = if ($env:PYTHON) { $env:PYTHON }\n"
            'elseif (Test-Path "$AppDir\\bin\\python.exe") { "$AppDir\\bin\\python.exe" }\n'
            'elseif (Test-Path "$AppDir\\..\\.venv\\Scripts\\python.exe") { "$AppDir\\..\\.venv\\Scripts\\python.exe" }\n'
            'elseif (Test-Path "$AppDir\\..\\..\\.venv\\Scripts\\python.exe") { "$AppDir\\..\\..\\.venv\\Scripts\\python.exe" }\n'
            "else { 'python' }\n\n"
            'Write-Host "Starting Movie Dubbing Studio AI Desktop..." -ForegroundColor Cyan\n'
            "& $PyExe -m aidub.ui.application $args\n",
            encoding="utf-8",
        )

        # aidub.bat (CLI)
        launcher_cli = out / "aidub.bat"
        launcher_cli.write_text(
            "@echo off\n"
            "setlocal\n"
            'set "APP_DIR=%~dp0"\n'
            'set "PATH=%APP_DIR%bin;%PATH%"\n'
            'set "PYTHONPATH=%APP_DIR%lib;%PYTHONPATH%"\n\n'
            "if defined PYTHON (\n"
            '    set "PY_EXE=%PYTHON%"\n'
            ') else if exist "%APP_DIR%bin\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%bin\\python.exe"\n'
            ') else if exist "%APP_DIR%..\\.venv\\Scripts\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%..\\.venv\\Scripts\\python.exe"\n'
            ') else if exist "%APP_DIR%..\\..\\.venv\\Scripts\\python.exe" (\n'
            '    set "PY_EXE=%APP_DIR%..\\..\\.venv\\Scripts\\python.exe"\n'
            ") else (\n"
            '    set "PY_EXE=python"\n'
            ")\n\n"
            '"%PY_EXE%" -m aidub.cli %*\n'
            "endlocal\n",
            encoding="utf-8",
        )

    def _write_metadata(self, out: Path) -> None:
        """Write manifest.json and distribution notices."""
        manifest_data = {
            "app_name": self.spec.app_name,
            "version": self.spec.version,
            "platform": "windows",
            "arch": "x64",
            "build_timestamp": datetime.now(UTC).isoformat(),
            "python_version_target": ">=3.12,<3.14",
            "entrypoint_desktop": "aidub.ui.application:run_desktop",
            "entrypoint_cli": "aidub.cli:main",
        }
        manifest_file = out / "manifest.json"
        manifest_file.write_text(
            json.dumps(manifest_data, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def verify_distribution(cls, dist_path: Path) -> bool:
        """
        Verify distribution contains launchers, metadata, and required directory structures.
        """
        dist_path = Path(dist_path)
        required = [
            dist_path / "MovieDubbingStudio.bat",
            dist_path / "MovieDubbingStudio.ps1",
            dist_path / "aidub.bat",
            dist_path / "manifest.json",
            dist_path / "bin" / "README_FFMPEG.txt",
            dist_path / "models" / "README_MODELS.txt",
            dist_path / "lib" / "aidub",
        ]
        return all(p.exists() for p in required)


__all__ = [
    "PackagingSpec",
    "WindowsPackager",
]
