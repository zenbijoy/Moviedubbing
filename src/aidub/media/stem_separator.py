"""Demucs / UVR-MDX Stem Separation & Background Peak Normalization Guard."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import numpy as np

from aidub.media.ffmpeg_ops import _run

logger = logging.getLogger(__name__)


def separate_stems(
    audio_path: Path | str,
    output_dir: Path | str,
    model_name: str = "htdemucs",
) -> tuple[Path, Path]:
    """
    Separate audio track into clean vocals and background accompaniment.

    Fails explicitly when Demucs is unavailable or does not produce both stems.

    Returns:
        Tuple of (vocals_wav_path, accompaniment_wav_path).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_p = Path(audio_path)

    vocal_path = out_dir / "vocals.wav"
    music_path = out_dir / "music.wav"

    # ------------------------------------------------------------------
    # Try real Demucs separation first
    # ------------------------------------------------------------------
    if not _try_import_demucs():
        raise RuntimeError(
            "Demucs is required for dialogue/music separation. Install "
            "'demucs>=4.0,<5' in the active studio environment."
        )

    demucs_exe = shutil.which("demucs")
    command = [demucs_exe] if demucs_exe else [sys.executable, "-m", "demucs"]
    command.extend(["--two-stems", "vocals", "-n", model_name, "-o", str(out_dir), str(audio_p)])
    try:
        _run(command)
    except RuntimeError as exc:
        raise RuntimeError(f"Demucs stem separation failed: {exc}") from exc

    sep_dir = out_dir / model_name / audio_p.stem
    separated_vocals = sep_dir / "vocals.wav"
    separated_music = sep_dir / "no_vocals.wav"
    if not separated_vocals.is_file() or not separated_music.is_file():
        raise RuntimeError(
            f"Demucs completed without both expected stems in {sep_dir}; "
            "the source audio has not been substituted."
        )

    shutil.copyfile(separated_vocals, vocal_path)
    shutil.copyfile(separated_music, music_path)
    logger.info("Stem separation complete: vocals=%s music=%s", vocal_path, music_path)
    return vocal_path, music_path


def _try_import_demucs() -> bool:
    """Return True if demucs is importable."""
    try:
        import demucs  # noqa: F401

        return True
    except ImportError:
        return False


def needs_background_normalization(
    background_audio_path: Path | str,
    threshold: float = 0.10,
    chunk_size: int = 1024,
    sample_rate: int = 44100,
) -> tuple[bool, float]:
    """
    Check if background accompaniment track requires volume normalization.

    Prevents amplifying residual voice bleed left over from Demucs stem separation.
    (Adopted from open-dubbing audio_processing.py)

    Args:
        background_audio_path: Path to background accompaniment track.
        threshold: Amplitude threshold (0.10 default).
        chunk_size: Processing window chunk size.
        sample_rate: Audio sampling rate.

    Returns:
        Tuple of (needs_normalization_bool, max_peak_amplitude).
    """
    try:
        import soundfile as sf

        data, _ = sf.read(str(background_audio_path), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)

        max_amp = float(np.abs(data).max())
        needs = max_amp > threshold
        logger.debug("needs_background_normalization: max_amp=%.3f needs=%s", max_amp, needs)
        return needs, max_amp
    except Exception as exc:
        logger.error("Error evaluating background normalization: %s", exc)
        return True, 1.0


__all__ = ["needs_background_normalization", "separate_stems"]
