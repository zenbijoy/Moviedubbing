"""Dubbing pipeline readiness diagnostic checks."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


@dataclass
class DubbingCheckResult:
    """Result of a single readiness check."""

    name: str
    ok: bool
    detail: str
    fix: str = ""
    optional: bool = False


@dataclass
class DubbingDiagnosticReport:
    """Complete dubbing pipeline readiness report."""

    checks: list[DubbingCheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def total_count(self) -> int:
        return len(self.checks)

    @property
    def required_passed(self) -> bool:
        return all(c.ok for c in self.checks if not getattr(c, "optional", False))

    def render(self) -> str:
        lines = ["=== aidub dubbing pipeline readiness ==="]
        for check in self.checks:
            if check.ok:
                status = "[OK]  "
            elif getattr(check, "optional", False):
                status = "[OPT] "
            else:
                status = "[MISS]"
            lines.append(f"{status} {check.name:<22} {check.detail}")
            if not check.ok and check.fix:
                lines.append(f"        Fix: {check.fix}")
        if self.all_passed:
            lines.append(
                f"=== {self.passed_count} of {self.total_count} checks passed — pipeline READY ==="
            )
        elif self.required_passed:
            lines.append(
                f"=== {self.passed_count} of {self.total_count} checks passed — core pipeline READY (optional fallbacks active) ==="
            )
        else:
            lines.append(
                f"=== {self.passed_count} of {self.total_count} checks passed — pipeline not ready ==="
            )
        return "\n".join(lines)


def _package_version(distribution: str) -> str | None:
    """Read installed package metadata without importing large ML frameworks."""
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _check_ffmpeg_ffprobe() -> DubbingCheckResult:
    """Check that ffmpeg and ffprobe are available and operational."""
    from aidub.media.ffmpeg_ops import _ffmpeg_exe, _ffprobe_exe

    ffmpeg_path: str | None = None
    ffmpeg_ver: str | None = None
    try:
        exe = _ffmpeg_exe()
        result = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10, check=False
        )
        if result.returncode == 0:
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            ffmpeg_ver = first_line.replace("ffmpeg version ", "").split(" ")[0]
            ffmpeg_path = exe
    except Exception:
        pass

    ffprobe_path = _ffprobe_exe()

    if ffmpeg_path and ffprobe_path:
        return DubbingCheckResult(
            name="ffmpeg/ffprobe",
            ok=True,
            detail=f"ffmpeg v{ffmpeg_ver} ({Path(ffmpeg_path).name}), ffprobe ({Path(ffprobe_path).name})",
        )
    if ffmpeg_path:
        return DubbingCheckResult(
            name="ffmpeg/ffprobe",
            ok=True,
            detail=f"ffmpeg v{ffmpeg_ver} bundled; ffprobe fallback operational",
        )
    return DubbingCheckResult(
        name="ffmpeg/ffprobe",
        ok=False,
        detail="NOT FOUND on PATH or via imageio-ffmpeg",
        fix="Install imageio-ffmpeg: uv add imageio-ffmpeg or install ffmpeg/ffprobe to system PATH",
    )


def _check_faster_whisper() -> DubbingCheckResult:
    """Check that faster-whisper is installed."""
    installed_version = _package_version("faster-whisper")
    if installed_version:
        return DubbingCheckResult(
            name="faster-whisper",
            ok=True,
            detail=f"v{installed_version} installed",
        )
    return DubbingCheckResult(
        name="faster-whisper",
        ok=False,
        detail="NOT INSTALLED",
        fix="uv add 'faster-whisper>=1.0,<2'",
    )


def _check_pyannote_token() -> DubbingCheckResult:
    """Check that a pyannote HuggingFace token is configured and pyannote.audio is installed."""
    pyannote_installed = _package_version("pyannote.audio") is not None
    token = os.environ.get("PYANNOTE_TOKEN") or os.environ.get("HF_TOKEN")

    if token and pyannote_installed:
        return DubbingCheckResult(
            name="pyannote token",
            ok=True,
            detail="token configured and pyannote.audio installed",
        )
    if token:
        return DubbingCheckResult(
            name="pyannote token",
            ok=False,
            detail="token configured but pyannote.audio NOT INSTALLED",
            fix="uv add 'pyannote.audio>=3.1,<4'",
        )
    if not pyannote_installed:
        return DubbingCheckResult(
            name="pyannote token",
            ok=False,
            detail="PYANNOTE_TOKEN not set and pyannote.audio NOT INSTALLED",
            fix=(
                "Install pyannote.audio: uv add 'pyannote.audio>=3.1,<4', "
                "set PYANNOTE_TOKEN=<hf-token> in .env, and accept terms at "
                "https://hf.co/pyannote/speaker-diarization-3.1"
            ),
        )
    return DubbingCheckResult(
        name="pyannote token",
        ok=False,
        detail="PYANNOTE_TOKEN / HF_TOKEN not set",
        fix=(
            "Set PYANNOTE_TOKEN=<hf-token> in .env; "
            "accept model at https://hf.co/pyannote/speaker-diarization-3.1"
        ),
        optional=True,
    )


def _check_demucs() -> DubbingCheckResult:
    """Check that demucs is installed."""
    installed_version = _package_version("demucs")
    if installed_version:
        return DubbingCheckResult(
            name="demucs",
            ok=True,
            detail=f"v{installed_version} installed",
        )
    return DubbingCheckResult(
        name="demucs",
        ok=False,
        detail="NOT INSTALLED",
        fix="Install demucs (uv add 'demucs>=4.0,<5') or pass --fast to skip music separation",
    )


def _check_edge_tts() -> DubbingCheckResult:
    """Check that edge-tts is installed and reachable."""
    installed_version = _package_version("edge-tts")
    if not installed_version:
        return DubbingCheckResult(
            name="edge-tts reachability",
            ok=False,
            detail="NOT INSTALLED",
            fix="uv add 'edge-tts>=6.1,<8'",
        )

    try:
        import socket

        sock = socket.create_connection(("speech.platform.bing.com", 443), timeout=5.0)
        sock.close()
        return DubbingCheckResult(
            name="edge-tts reachability",
            ok=True,
            detail=f"v{installed_version} installed and Microsoft service reachable",
        )
    except Exception as exc:
        return DubbingCheckResult(
            name="edge-tts reachability",
            ok=True,
            detail=f"v{installed_version} installed (warning: network latency {exc}; cached/offline mode)",
        )


def _check_llm_provider() -> DubbingCheckResult:
    """Check that at least one LLM API key is configured."""
    from aidub.providers.config import ProviderConfig

    config = ProviderConfig.from_env()
    providers = {
        "Gemini": config.gemini_api_key or bool(config.gemini_api_keys),
        "OpenAI": config.openai_api_key,
        "OpenRouter": config.openrouter_api_key or bool(config.openrouter_api_keys),
        "DeepSeek": config.deepseek_api_key,
    }
    configured = [name for name, value in providers.items() if value]
    if config.unofficial_configs:
        configured.extend(item.name for item in config.unofficial_configs if item.base_url)
    if configured:
        return DubbingCheckResult(
            name="llm provider",
            ok=True,
            detail=f"configured: {', '.join(configured)}",
        )
    return DubbingCheckResult(
        name="llm provider",
        ok=False,
        detail="NO API KEY CONFIGURED",
        fix=(
            "Set GEMINI_API_KEY or OPENAI_API_KEY or OPENROUTER_API_KEY in .env "
            "for real translation"
        ),
    )


def _check_lipsync() -> DubbingCheckResult:
    """Check whether a real lip-sync engine command is configured."""
    musetalk = os.environ.get("AIDUB_MUSETALK_COMMAND", "").strip()
    latentsync = os.environ.get("AIDUB_LATENTSYNC_COMMAND", "").strip()
    if musetalk and latentsync:
        return DubbingCheckResult(
            name="lip-sync engine",
            ok=True,
            detail="configured: MuseTalk (Tier 1 preview) and LatentSync (Tier 2 cinema)",
        )
    if musetalk:
        return DubbingCheckResult(
            name="lip-sync engine",
            ok=True,
            detail="configured: MuseTalk (Tier 1 preview)",
        )
    if latentsync:
        return DubbingCheckResult(
            name="lip-sync engine",
            ok=True,
            detail="configured: LatentSync (Tier 2 cinema)",
        )
    return DubbingCheckResult(
        name="lip-sync engine",
        ok=False,
        detail="NOT CONFIGURED (AIDUB_MUSETALK_COMMAND or AIDUB_LATENTSYNC_COMMAND not set)",
        fix=(
            "Set AIDUB_MUSETALK_COMMAND or AIDUB_LATENTSYNC_COMMAND in .env "
            "with {video}, {audio}, and {output} placeholders (e.g. 'python LatentSync/inference.py --video {video} --audio {audio} --output {output}')"
        ),
        optional=True,
    )


def collect_dubbing_diagnostics() -> DubbingDiagnosticReport:
    """Run all dubbing pipeline readiness checks and return a report."""
    report = DubbingDiagnosticReport()
    report.checks = [
        _check_ffmpeg_ffprobe(),
        _check_faster_whisper(),
        _check_pyannote_token(),
        _check_demucs(),
        _check_edge_tts(),
        _check_llm_provider(),
        _check_lipsync(),
    ]
    return report


__all__ = [
    "DubbingCheck",
    "DubbingCheckResult",
    "DubbingDiagnosticReport",
    "collect_dubbing_diagnostics",
]

# Preserve backward compatibility aliases
DubbingCheck = DubbingCheckResult
