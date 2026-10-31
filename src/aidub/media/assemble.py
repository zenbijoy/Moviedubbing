"""Audio Timeline Assembly & EBU R128 Loudness Normalization (from dub-studio)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration, time_stretch

logger = logging.getLogger(__name__)


def normalize_voice(
    samples: np.ndarray,
    sr: int,
    target_lufs: float = -14.0,
    target_rms_db: float = -14.0,
    max_gain_db: float = 18.0,
    peak_limit: float = 0.985,
) -> np.ndarray:
    """
    EBU R128 (or RMS fallback) integrated loudness normalization per phrase.

    Applies pure linear gain capped at +18dB to ensure crisp dialogue audibility,
    followed by peak limiting to 0.985 to prevent clipping distortion.

    Args:
        samples: Mono audio signal float32/float64 (-1.0 to +1.0).
        sr: Sample rate in Hz.
        target_lufs: Target loudness in LUFS (-16.0 default).
        target_rms_db: RMS fallback target when clip is too short for pyloudnorm.
        max_gain_db: Maximum allowed gain boost in dB (12.0dB max).
        peak_limit: Peak ceiling limit (0.985 max).

    Returns:
        Loudness-normalized float32 audio sample array.
    """
    if len(samples) == 0:
        return samples

    signal = samples.astype(np.float32)
    max_peak = np.abs(signal).max()
    if max_peak == 0:
        return signal

    clip_dur = len(signal) / sr
    gain_db = 0.0

    if clip_dur >= 0.400:
        try:
            import pyloudnorm as pyln

            meter = pyln.Meter(sr)
            loudness = meter.integrated_loudness(signal)
            if not np.isinf(loudness) and not np.isnan(loudness):
                gain_db = target_lufs - loudness
        except Exception:
            # Fallback to RMS
            rms = np.sqrt(np.mean(signal**2))
            if rms > 1e-7:
                rms_db = 20 * np.log10(rms)
                gain_db = target_rms_db - rms_db
    else:
        # Short clip RMS fallback
        rms = np.sqrt(np.mean(signal**2))
        if rms > 1e-7:
            rms_db = 20 * np.log10(rms)
            gain_db = target_rms_db - rms_db

    # Cap maximum gain boost
    gain_db = min(gain_db, max_gain_db)
    gain_linear = 10 ** (gain_db / 20.0)
    scaled = signal * gain_linear

    # Peak limiting
    peak = np.abs(scaled).max()
    if peak > peak_limit:
        scaled = scaled * (peak_limit / peak)

    return scaled.astype(np.float32)


def fit_to_slot(
    seg_wav: Path | str,
    target_dur: float,
    out_wav: Path | str,
    max_stretch: float = 2.0,
    sample_rate: int = 48_000,
) -> Path:
    """
    Fit synthesized audio segment into available slot time.

    Rule: ONLY speeds up audio (never slows down, as slowing is unnatural).
    Applies atempo if current duration > target_dur * 1.02, capped at max_stretch.

    Args:
        seg_wav: Input raw synthesized WAV file.
        target_dur: Available slot room in seconds.
        out_wav: Output fitted WAV path.
        max_stretch: Maximum allowed speed-up factor (2.0 default).
        sample_rate: Broadcast standard target sample rate (48000 Hz default).

    Returns:
        Path to fitted output WAV.
    """
    cur_dur = duration(seg_wav)
    out_p = Path(out_wav)

    if cur_dur <= target_dur * 1.02:
        # Decode/re-encode even when timing fits. Copying an MP3 into a .wav
        # filename corrupts the artifact and breaks the timeline assembler.
        out_p.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                _ffmpeg_exe(),
                "-y",
                "-i",
                str(seg_wav),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(out_p),
            ]
        )
        return out_p

    # Requires speed-up
    ratio = cur_dur / max(target_dur, 0.1)
    ratio_clamped = min(ratio, max_stretch)

    logger.debug(
        "fit_to_slot: speed up %s from %.2fs to %.2fs (ratio %.2fx)",
        Path(seg_wav).name,
        cur_dur,
        target_dur,
        ratio_clamped,
    )
    return time_stretch(seg_wav, out_p, ratio_clamped)


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr or len(data) == 0:
        return data
    try:
        import librosa

        return librosa.resample(data, orig_sr=orig_sr, target_sr=target_sr)
    except Exception:
        pass
    try:
        import torch
        import torchaudio.functional as F

        t = torch.from_numpy(data.astype(np.float32)).unsqueeze(0)
        res = F.resample(t, orig_freq=orig_sr, new_freq=target_sr).squeeze(0)
        return res.numpy().astype(np.float32)
    except Exception:
        pass
    try:
        from scipy import signal

        num = int(len(data) * target_sr / orig_sr)
        return signal.resample(data, num).astype(np.float32)
    except Exception:
        pass
    old_x = np.linspace(0, 1, len(data))
    new_len = int(len(data) * target_sr / orig_sr)
    new_x = np.linspace(0, 1, new_len)
    return np.interp(new_x, old_x, data).astype(np.float32)


def assemble_timeline(
    placed_segments: list[tuple[float | Any, Path | str]],
    total_duration_s: float,
    output_wav: Path | str,
    sample_rate: int = 48_000,
) -> Path:
    """
    Assemble placed dubbed segments into a single cohesive audio track at broadcast sample rate.

    Anchors each segment strictly to its target editorial cue timestamp (preventing
    cumulative timing drift across long-form films). Overlapping trails (e.g. reverb
    or breath) are cleanly blended without pushing subsequent character lines out of sync.
    Final audio is padded or conformed to match exact video duration.

    Args:
        placed_segments: List of tuples (start_position, segment_wav_path).
            start_position may be float seconds, RationalTime, or AudioSamplePosition.
        total_duration_s: Target total video duration in seconds.
        output_wav: Output WAV file path.
        sample_rate: Target output sample rate (48000 Hz broadcast standard default).

    Returns:
        Path to completed audio track.
    """
    import soundfile as sf
    from aidub.domain.time import AudioSamplePosition, RationalTime

    exact_len = int(round(total_duration_s * sample_rate))
    total_samples = max(exact_len, 0) + sample_rate
    timeline_buf = np.zeros(total_samples, dtype=np.float32)

    def _resolve_sample_index(pos: float | Any) -> int:
        if isinstance(pos, AudioSamplePosition):
            if pos.sample_rate == sample_rate:
                return pos.sample_index
            return int(round(pos.sample_index * sample_rate / pos.sample_rate))
        if isinstance(pos, RationalTime):
            return pos.to_audio_sample_position(sample_rate).sample_index
        return int(round(float(pos) * sample_rate))

    # Sort segments by their target start time
    sorted_segments = sorted(placed_segments, key=lambda x: _resolve_sample_index(x[0]))

    cursor_sample = 0

    for start_pos, seg_path in sorted_segments:
        target_start_sample = max(0, _resolve_sample_index(start_pos))
        data, sr = sf.read(str(seg_path), dtype="float32")

        if data.ndim > 1:
            data = data.mean(axis=1)

        if sr != sample_rate:
            data = _resample(data, orig_sr=sr, target_sr=sample_rate)

        # Normalize phrase loudness according to EBU R128 / broadcast standard
        norm_data = normalize_voice(data, sample_rate)
        seg_samples = len(norm_data)
        if seg_samples == 0:
            continue

        # In ADR-001 exact time model:
        # We anchor strictly to target_start_sample to prevent Cascading Drift Disaster.
        # If previous segment had a lingering tail, we log and blend rather than bumping.
        if target_start_sample < cursor_sample:
            overlap_ms = (cursor_sample - target_start_sample) * 1000.0 / sample_rate
            logger.debug(
                "Dialogue overlap of %.1f ms at sample %d. Anchoring to editorial timing to prevent drift.",
                overlap_ms,
                target_start_sample,
            )

        start_sample = target_start_sample
        end_sample = start_sample + seg_samples
        if end_sample > len(timeline_buf):
            timeline_buf = np.pad(timeline_buf, (0, end_sample - len(timeline_buf)))

        timeline_buf[start_sample:end_sample] += norm_data
        cursor_sample = max(cursor_sample, end_sample)

    out_p = Path(output_wav)
    final_buf = timeline_buf[:exact_len]
    if len(final_buf) < exact_len:
        final_buf = np.pad(final_buf, (0, exact_len - len(final_buf)))
    sf.write(str(out_p), final_buf, sample_rate)
    return out_p


__all__ = ["assemble_timeline", "fit_to_slot", "normalize_voice"]
