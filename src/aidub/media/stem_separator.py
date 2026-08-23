"""Demucs / UVR-MDX Stem Separation & Background Peak Normalization Guard."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from aidub.media.ffmpeg_ops import _run

logger = logging.getLogger(__name__)


def separate_stems(
    audio_path: Path | str,
    output_dir: Path | str,
    model_name: str = "UVR-MDX-NET-Inst_HQ_3.onnx",
) -> tuple[Path, Path]:
    """
    Separate audio track into clean vocals and background accompaniment.

    Returns:
        Tuple of (vocals_wav_path, accompaniment_wav_path).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_p = Path(audio_path)

    vocal_path = out_dir / "vocals.wav"
    music_path = out_dir / "music.wav"

    try:
        cmd = [
            "demucs", "--two-stems", "vocals",
            "-o", str(out_dir),
            str(audio_p),
        ]
        _run(cmd)
        
        # Locate generated outputs
        sep_dir = out_dir / "htdemucs" / audio_p.stem
        if (sep_dir / "vocals.wav").exists():
            import shutil
            shutil.copyfile(str(sep_dir / "vocals.wav"), str(vocal_path))
            shutil.copyfile(str(sep_dir / "no_vocals.wav"), str(music_path))
            return vocal_path, music_path
        raise RuntimeError("Demucs completed without producing the expected stems")
    except Exception as exc:
        logger.exception("Demucs source separation failed")
        raise RuntimeError(
            "Demucs source separation failed; install Demucs and its model weights"
        ) from exc


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
        import soundfile as sf  # type: ignore[import-not-found]

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
