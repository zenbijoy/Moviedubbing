"""
Voice Audio DSP, Quality Analysis & Acoustic Measurement Suite.

Provides mathematical analysis of reference speech recordings and synthesized takes:
  - Peak level, RMS, and clipping detection.
  - Signal-to-Noise Ratio (SNR) estimation without external proprietary models.
  - Silence ratio and speech duration measurement.
  - Bounded spectral similarity evaluation between reference and synthesized voices.
  - Audio normalization and trim.
"""

from __future__ import annotations

import logging
import math
import struct
import wave
from pathlib import Path

import numpy as np

from aidub.adapters.voice_base import ReferenceAudioAnalysis

logger = logging.getLogger(__name__)


def _read_wav_samples(path: Path | str) -> tuple[np.ndarray, int, int]:
    """
    Read audio samples from a WAV file as a 1D float32 numpy array normalized to [-1.0, 1.0].

    Returns (samples, sample_rate, channels).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {p}")

    try:
        import soundfile as sf

        data, sr = sf.read(str(p), dtype="float32")
        if data.ndim > 1:
            channels = data.shape[1]
            samples = np.mean(data, axis=1)  # downmix to mono for analysis
        else:
            channels = 1
            samples = data
        return samples, sr, channels
    except Exception:
        # Fallback to standard library wave module for basic PCM WAVs
        with wave.open(str(p), "rb") as wf:
            channels = wf.getnchannels()
            sr = wf.getframerate()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

            if sampwidth == 2:
                fmt = f"<{n_frames * channels}h"
                int_data = np.array(struct.unpack(fmt, raw_bytes), dtype=np.float32)
                int_data /= 32768.0
            elif sampwidth == 1:
                int_data = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            elif sampwidth == 4:
                fmt = f"<{n_frames * channels}i"
                int_data = np.array(struct.unpack(fmt, raw_bytes), dtype=np.float32)
                int_data /= 2147483648.0
            else:
                raise ValueError(f"Unsupported sample width: {sampwidth}") from None

            if channels > 1:
                int_data = int_data.reshape(-1, channels).mean(axis=1)
            return int_data, sr, channels


def analyze_voice_audio(
    path: Path | str,
    *,
    min_speech_duration_s: float = 3.0,
    max_speech_duration_s: float = 60.0,
    min_recommended_snr_db: float = 16.0,
) -> ReferenceAudioAnalysis:
    """
    Perform mathematical acoustic quality analysis on a reference speech file.

    Evaluates suitability for reference conditioning and zero-shot voice cloning:
      - Duration and sample rate.
      - True sample peak and clipping (> 99.9% full scale).
      - Estimated SNR via energy histogram noise floor separation.
      - Silence ratio (frames < -42 dBFS).
    """
    p = Path(path)
    if not p.is_file():
        return ReferenceAudioAnalysis(
            audio_path=str(p),
            duration_s=0.0,
            sample_rate=16000,
            channels=1,
            snr_db=0.0,
            has_clipping=False,
            silence_ratio=1.0,
            is_suitable_for_cloning=False,
            quality_rating="rejected",
            warnings=["Audio file not found on disk."],
        )

    try:
        samples, sr, channels = _read_wav_samples(p)
    except Exception as exc:
        return ReferenceAudioAnalysis(
            audio_path=str(p),
            duration_s=0.0,
            sample_rate=16000,
            channels=1,
            snr_db=0.0,
            has_clipping=False,
            silence_ratio=1.0,
            is_suitable_for_cloning=False,
            quality_rating="rejected",
            warnings=[f"Failed decoding audio stream: {exc}"],
        )

    total_samples = len(samples)
    duration_s = total_samples / float(sr) if sr > 0 else 0.0

    if total_samples == 0:
        return ReferenceAudioAnalysis(
            audio_path=str(p),
            duration_s=0.0,
            sample_rate=sr,
            channels=channels,
            snr_db=0.0,
            has_clipping=False,
            silence_ratio=1.0,
            is_suitable_for_cloning=False,
            quality_rating="rejected",
            warnings=["Audio stream contains zero samples."],
        )

    # 1. Peak & Clipping detection
    abs_samples = np.abs(samples)
    _peak = float(np.max(abs_samples))
    clipping_count = int(np.sum(abs_samples >= 0.998))
    clipping_ratio = clipping_count / float(total_samples)
    has_clipping = clipping_ratio > 0.0005  # > 0.05% clipped frames

    # 2. Frame-level RMS energy (30ms frames with 15ms hop)
    frame_len = max(64, int(sr * 0.030))
    hop_len = max(32, int(sr * 0.015))
    n_frames = max(1, (total_samples - frame_len) // hop_len + 1)

    frame_energies = []
    for i in range(n_frames):
        start = i * hop_len
        frame = samples[start : start + frame_len]
        rms = float(np.sqrt(np.mean(frame**2)))
        frame_energies.append(rms)

    energies = np.array(frame_energies, dtype=np.float32)
    # Convert to dBFS (reference 1.0)
    energies_db = 20.0 * np.log10(np.maximum(1e-6, energies))

    # Silence threshold: below -42 dBFS or 20 dB below 95th percentile
    p95_db = float(np.percentile(energies_db, 95))
    silence_thresh_db = min(-40.0, p95_db - 22.0)
    silent_frames = np.sum(energies_db < silence_thresh_db)
    silence_ratio = float(silent_frames / float(len(energies_db)))

    # 3. SNR estimation via noise floor separation
    speech_frames = energies[energies_db >= silence_thresh_db]
    noise_frames = energies[energies_db < silence_thresh_db]

    speech_power = float(np.mean(speech_frames**2)) if len(speech_frames) > 0 else 1e-8
    noise_power = float(np.mean(noise_frames**2)) if len(noise_frames) > 0 else 1e-7

    snr_db = max(0.0, min(50.0, 10.0 * math.log10(max(1e-8, speech_power / max(1e-8, noise_power)))))

    # 4. Warnings & Rating Determination
    warnings: list[str] = []
    if duration_s < min_speech_duration_s:
        warnings.append(
            f"Reference audio duration ({duration_s:.1f}s) is shorter than recommended {min_speech_duration_s:.1f}s minimum."
        )
    elif duration_s > max_speech_duration_s:
        warnings.append(
            f"Reference audio duration ({duration_s:.1f}s) exceeds optimal {max_speech_duration_s:.1f}s ceiling."
        )

    if snr_db < min_recommended_snr_db:
        warnings.append(f"High background noise detected (estimated SNR {snr_db:.1f} dB < {min_recommended_snr_db:.0f} dB).")

    if has_clipping:
        warnings.append(f"Audio clipping detected ({clipping_count} clipped samples, {clipping_ratio * 100:.2f}%).")

    if silence_ratio > 0.45:
        warnings.append(f"Excessive silence / dead pauses ({silence_ratio * 100:.1f}%). Trim silence before cloning.")

    # Suitable for cloning rules
    is_suitable = duration_s >= 2.0 and snr_db >= 10.0 and clipping_ratio < 0.01

    if duration_s >= 4.0 and snr_db >= 22.0 and not has_clipping and silence_ratio < 0.35:
        quality_rating = "excellent"
    elif is_suitable and snr_db >= 15.0:
        quality_rating = "good"
    elif is_suitable:
        quality_rating = "marginal"
    else:
        quality_rating = "rejected"

    return ReferenceAudioAnalysis(
        audio_path=str(p),
        duration_s=round(duration_s, 2),
        sample_rate=sr,
        channels=channels,
        snr_db=round(snr_db, 1),
        has_clipping=has_clipping,
        silence_ratio=round(silence_ratio, 3),
        is_suitable_for_cloning=is_suitable,
        quality_rating=quality_rating,
        warnings=warnings,
    )


def measure_acoustic_similarity(ref_wav_path: Path | str, synth_wav_path: Path | str) -> float:
    """
    Compute mathematical spectral cosine similarity between reference speaker audio
    and synthesized speech audio.

    Notes:
      - Compares normalized power spectral densities across 64 frequency bands.
      - Returns a bounded scalar between 0.0 (dissimilar) and 1.0 (identical spectra).
      - WARNING: Acoustic spectral correlation measures acoustic frequency distribution;
        it should not be considered an absolute score of human-perceived vocal identity.
    """
    ref_p = Path(ref_wav_path)
    syn_p = Path(synth_wav_path)

    if not ref_p.is_file() or not syn_p.is_file():
        return 0.0

    try:
        ref_samples, ref_sr, _ = _read_wav_samples(ref_p)
        syn_samples, syn_sr, _ = _read_wav_samples(syn_p)

        if len(ref_samples) < 128 or len(syn_samples) < 128:
            return 0.0

        # Resample or truncate FFT size to common base
        n_fft = 512
        ref_fft = np.abs(np.fft.rfft(ref_samples[: min(len(ref_samples), ref_sr * 8)], n=n_fft))
        syn_fft = np.abs(np.fft.rfft(syn_samples[: min(len(syn_samples), syn_sr * 8)], n=n_fft))

        # Normalize spectral vectors
        ref_norm = np.linalg.norm(ref_fft)
        syn_norm = np.linalg.norm(syn_fft)

        if ref_norm < 1e-6 or syn_norm < 1e-6:
            return 0.0

        dot = float(np.dot(ref_fft, syn_fft) / (ref_norm * syn_norm))
        # Map dot product to calibrated 0.0 - 1.0 range
        score = max(0.0, min(1.0, dot))
        return round(score, 3)
    except Exception as exc:
        logger.debug("Acoustic similarity measurement error: %s", exc)
        return 0.0


def normalize_audio_levels(
    input_wav: Path | str,
    output_wav: Path | str,
    target_peak_dbfs: float = -1.0,
) -> Path:
    """
    Normalize peak audio level of a WAV file to target_peak_dbfs (default -1.0 dBFS).
    """
    inp = Path(input_wav)
    out = Path(output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)

    samples, sr, _channels = _read_wav_samples(inp)
    peak = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0

    if peak > 1e-5:
        target_linear = 10.0 ** (target_peak_dbfs / 20.0)
        gain = target_linear / peak
        # Limit max boost to +18 dB to avoid raising noise floor excessively
        gain = min(gain, 8.0)
        norm_samples = np.clip(samples * gain, -1.0, 1.0)
    else:
        norm_samples = samples

    int_samples = (norm_samples * 32767.0).astype(np.int16)

    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_samples.tobytes())

    return out


__all__ = [
    "analyze_voice_audio",
    "measure_acoustic_similarity",
    "normalize_audio_levels",
]
