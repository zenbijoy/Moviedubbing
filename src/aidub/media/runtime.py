"""Discovery and validation of the external FFmpeg runtime."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MediaRuntimeInfo:
    ffmpeg: Path
    ffprobe: Path
    version: str


class MediaRuntime:
    def __init__(
        self,
        *,
        ffmpeg: Path | str | None = None,
        ffprobe: Path | str | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe

    @staticmethod
    def _resolve(binary: Path | str | None, default_name: str) -> Path:
        if binary is None:
            found = shutil.which(default_name)
            if not found:
                candidate = (
                    Path.home()
                    / ".local"
                    / "bin"
                    / (f"{default_name}.exe" if os.name == "nt" else default_name)
                )
                if candidate.is_file():
                    found = str(candidate)
            if not found and default_name == "ffmpeg":
                try:
                    import imageio_ffmpeg

                    found = imageio_ffmpeg.get_ffmpeg_exe()
                except Exception:
                    pass
            if not found:
                raise FileNotFoundError(
                    f"{default_name} was not found; install or configure a supported runtime"
                )
            path = Path(found)
        else:
            path = Path(binary).expanduser()
        path = path.resolve(strict=True)
        if not path.is_file():
            raise FileNotFoundError(f"media runtime is not a file: {path}")
        bin_dir = str(path.parent.resolve())
        current_path = os.environ.get("PATH", "")
        if bin_dir not in current_path.split(os.pathsep):
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{current_path}"
        return path

    def inspect(self, timeout_seconds: float = 5.0) -> MediaRuntimeInfo:
        ffmpeg = self._resolve(self._ffmpeg, "ffmpeg")
        ffprobe = self._resolve(self._ffprobe, "ffprobe")
        # The executable is resolved to an existing local file and arguments
        # are passed as a sequence; no shell parsing is involved.
        process = subprocess.run(
            [str(ffmpeg), "-version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg version check failed with code {process.returncode}")
        first_line = process.stdout.splitlines()[0] if process.stdout else ""
        match = re.search(r"\bversion\s+([^\s]+)", first_line)
        version = match.group(1) if match else "unknown"
        return MediaRuntimeInfo(ffmpeg=ffmpeg, ffprobe=ffprobe, version=version)


def ensure_media_runtime_on_path() -> tuple[Path, Path]:
    """Discover FFmpeg/FFprobe and export their directory to os.environ['PATH']."""
    runtime = MediaRuntime()
    info = runtime.inspect()
    return info.ffmpeg, info.ffprobe
