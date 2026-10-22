"""Measured, local audio diagnostics for imported audio and video files.

The analyzer streams decoded mono PCM from FFmpeg, so feature-length media does
not have to be loaded into memory. Emotion classification is delegated to the
existing EmotionEngine; this module reports the measured signal evidence it uses.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path


class AudioAnalysisCancelled(RuntimeError):
    """Raised when an operator cancels a running audio analysis."""


@dataclass(frozen=True, slots=True)
class AudioAnalysisReport:
    """Measured audio features for the requested media interval."""

    file_name: str
    start_seconds: float
    analyzed_seconds: float
    source_sample_rate_hz: int | None
    source_channels: int | None
    analysis_sample_rate_hz: int
    peak_dbfs: float
    rms_dbfs: float
    near_full_scale_percent: float
    silence_percent: float
    active_audio_percent: float
    loudness_range_db: float | None
    pitch_median_hz: float | None
    pitch_p10_hz: float | None
    pitch_p90_hz: float | None
    pitch_voiced_sample_percent: float
    spectral_centroid_hz: float
    zero_crossing_rate: float
    measurement_note: str

    def to_dict(self) -> dict[str, str | int | float | None]:
        """Return a JSON-safe mapping suitable for display or an LLM prompt."""

        return asdict(self)


def _dbfs(value: float) -> float:
    return round(20.0 * math.log10(max(value, 1e-6)), 2)


def analyze_audio_file(
    media_path: Path | str,
    *,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
    progress_callback: Callable[[float, float], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> AudioAnalysisReport:
    """Measure real audio features by streaming the first audio stream via FFmpeg.

    ``duration_seconds=None`` analyzes from ``start_seconds`` through the end of
    the media. ``active_audio_percent`` uses a -40 dBFS RMS threshold; it is not
    an ASR or voice activity detector.
    """

    import numpy as np

    path = Path(media_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Audio analysis input does not exist: {path}")
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError("Analysis start time must be a finite non-negative number")
    if duration_seconds is not None and (
        not math.isfinite(duration_seconds) or duration_seconds <= 0
    ):
        raise ValueError("Analysis duration must be a finite positive number or None")

    from aidub.media.ffmpeg_ops import _ffmpeg_exe, probe

    metadata = probe(path)
    streams = [
        stream
        for stream in metadata.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if not streams:
        raise ValueError(f"No audio stream was found in {path.name}")
    source_stream = streams[0]
    try:
        media_duration = float(metadata.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        media_duration = 0.0
    if media_duration > 0 and start_seconds >= media_duration:
        raise ValueError("Analysis start time is at or beyond the end of the media")

    expected_duration = (
        max(0.0, media_duration - start_seconds)
        if duration_seconds is None and media_duration > 0
        else duration_seconds
    )
    if expected_duration is not None and media_duration > 0:
        expected_duration = min(expected_duration, media_duration - start_seconds)

    command = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
    ]
    if duration_seconds is not None:
        command.extend(["-t", f"{expected_duration:.3f}"])
    command.extend(
        ["-ac", "1", "-ar", "16000", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]
    )

    sample_rate = 16_000
    frame_size = 512
    silence_threshold = 10.0 ** (-55.0 / 20.0)
    activity_threshold = 10.0 ** (-40.0 / 20.0)
    clip_threshold = 10.0 ** (-0.01 / 20.0)
    window = np.hanning(frame_size).astype(np.float32)
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)

    total_samples = 0
    total_frames = 0
    sum_squares = 0.0
    peak = 0.0
    near_full_scale_samples = 0
    silent_frames = 0
    active_frames = 0
    crossing_count = 0
    crossing_intervals = 0
    spectral_centroid_sum = 0.0
    spectral_centroid_frames = 0
    frame_levels: list[np.ndarray] = []
    pitch_candidates: list[np.ndarray] = []
    pitch_sample_count = 0
    remainder = np.empty(0, dtype=np.float32)
    last_progress_second = -1

    def process_frames(frames: np.ndarray) -> None:
        nonlocal total_frames, sum_squares, peak, near_full_scale_samples
        nonlocal silent_frames, active_frames, crossing_count, crossing_intervals
        nonlocal spectral_centroid_sum, spectral_centroid_frames, pitch_sample_count

        if not len(frames):
            return
        frames = np.nan_to_num(frames, copy=True)
        frame_squares = np.mean(frames * frames, axis=1, dtype=np.float64)
        frame_rms = np.sqrt(frame_squares)
        frame_peaks = np.max(np.abs(frames), axis=1)
        sum_squares += float(np.sum(frames * frames, dtype=np.float64))
        peak = max(peak, float(np.max(frame_peaks)))
        near_full_scale_samples += int(np.count_nonzero(np.abs(frames) >= clip_threshold))
        silent_frames += int(np.count_nonzero(frame_rms < silence_threshold))
        active_frames += int(np.count_nonzero(frame_rms >= activity_threshold))
        total_frames += len(frames)
        frame_levels.append(frame_rms.astype(np.float32, copy=False))

        crossings = (frames[:, 1:] * frames[:, :-1]) < 0
        crossing_count += int(np.count_nonzero(crossings))
        crossing_intervals += int(crossings.size)

        spectrum = np.abs(np.fft.rfft(frames * window, axis=1))
        magnitude_sum = np.sum(spectrum, axis=1)
        centroids = np.divide(
            spectrum @ frequencies,
            magnitude_sum,
            out=np.zeros_like(magnitude_sum),
            where=magnitude_sum > 1e-9,
        )
        audible = frame_rms >= silence_threshold
        spectral_centroid_sum += float(np.sum(centroids[audible]))
        spectral_centroid_frames += int(np.count_nonzero(audible))

        # Sample pitch candidates at about 4 Hz to keep feature-film analysis fast.
        sampled = frames[::8]
        sampled_rms = frame_rms[::8]
        usable = sampled_rms >= max(silence_threshold, 0.004)
        sampled = sampled[usable]
        pitch_sample_count += len(sampled_rms)
        if len(sampled):
            centered = sampled - np.mean(sampled, axis=1, keepdims=True)
            pitch_spectrum = np.fft.rfft(centered * window, n=1024, axis=1)
            autocorrelation = np.fft.irfft(
                pitch_spectrum.real**2 + pitch_spectrum.imag**2, n=1024, axis=1
            )
            min_lag = int(sample_rate / 400.0)
            max_lag = int(sample_rate / 60.0)
            normalized = autocorrelation[:, min_lag : max_lag + 1] / np.maximum(
                autocorrelation[:, :1], 1e-9
            )
            best_indices = np.argmax(normalized, axis=1)
            periodicity = normalized[np.arange(len(normalized)), best_indices]
            lags = best_indices + min_lag
            edge_margin = max(2, int(normalized.shape[1] * 0.03))
            valid = (
                (periodicity >= 0.32)
                & (best_indices >= edge_margin)
                & (best_indices < normalized.shape[1] - edge_margin)
            )
            if np.any(valid):
                pitch_candidates.append(sample_rate / lags[valid].astype(np.float64))

    process: subprocess.Popen[bytes] | None = None
    with tempfile.TemporaryFile() as stderr_file:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file)
            assert process.stdout is not None
            bytes_per_chunk = 256 * 1024
            while True:
                if cancel_requested is not None and cancel_requested():
                    process.terminate()
                    process.wait(timeout=5)
                    raise AudioAnalysisCancelled("Audio analysis was cancelled")
                chunk = process.stdout.read(bytes_per_chunk)
                if not chunk:
                    break
                samples = np.frombuffer(chunk, dtype="<f4")
                if len(remainder):
                    samples = np.concatenate((remainder, samples))
                usable_count = len(samples) - (len(samples) % frame_size)
                if usable_count:
                    process_frames(samples[:usable_count].reshape(-1, frame_size))
                remainder = samples[usable_count:].copy()
                total_samples += len(chunk) // 4
                elapsed = total_samples / sample_rate
                current_second = int(elapsed)
                if progress_callback is not None and current_second != last_progress_second:
                    progress_callback(elapsed, expected_duration or 0.0)
                    last_progress_second = current_second

            if len(remainder) >= 64:
                padded = np.pad(remainder, (0, frame_size - len(remainder)))
                process_frames(padded.reshape(1, frame_size))
            exit_code = process.wait()
            stderr_file.seek(0)
            error_text = stderr_file.read().decode("utf-8", errors="replace")[-2_000:]
            if exit_code != 0:
                raise RuntimeError(error_text.strip() or "FFmpeg could not decode this audio stream")
        finally:
            if process is not None and process.stdout is not None:
                process.stdout.close()
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()

    if total_samples == 0 or total_frames == 0:
        raise ValueError(f"No decodable audio samples were found in {path.name}")

    levels = np.concatenate(frame_levels) if frame_levels else np.empty(0, dtype=np.float32)
    audible_levels = levels[levels >= silence_threshold]
    loudness_range = None
    if len(audible_levels) >= 2:
        audible_levels_db = 20.0 * np.log10(np.maximum(audible_levels, 1e-6))
        loudness_range = round(
            float(np.percentile(audible_levels_db, 95) - np.percentile(audible_levels_db, 10)),
            2,
        )
    pitches = np.concatenate(pitch_candidates) if pitch_candidates else np.empty(0)
    pitch_median = round(float(np.median(pitches)), 1) if len(pitches) else None
    pitch_p10 = round(float(np.percentile(pitches, 10)), 1) if len(pitches) else None
    pitch_p90 = round(float(np.percentile(pitches, 90)), 1) if len(pitches) else None
    rms = math.sqrt(sum_squares / max(total_samples, 1))
    rms_dbfs = _dbfs(rms)
    peak_dbfs = _dbfs(peak)
    actual_duration = total_samples / sample_rate
    voiced_percent = 100.0 * len(pitches) / max(pitch_sample_count, 1)
    return AudioAnalysisReport(
        file_name=path.name,
        start_seconds=round(start_seconds, 3),
        analyzed_seconds=round(actual_duration, 3),
        source_sample_rate_hz=(
            int(source_stream["sample_rate"])
            if source_stream.get("sample_rate") is not None
            else None
        ),
        source_channels=(
            int(source_stream["channels"]) if source_stream.get("channels") is not None else None
        ),
        analysis_sample_rate_hz=sample_rate,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        near_full_scale_percent=round(100.0 * near_full_scale_samples / max(total_samples, 1), 5),
        silence_percent=round(100.0 * silent_frames / max(total_frames, 1), 2),
        active_audio_percent=round(100.0 * active_frames / max(total_frames, 1), 2),
        loudness_range_db=loudness_range,
        pitch_median_hz=pitch_median,
        pitch_p10_hz=pitch_p10,
        pitch_p90_hz=pitch_p90,
        pitch_voiced_sample_percent=round(min(voiced_percent, 100.0), 2),
        spectral_centroid_hz=round(
            spectral_centroid_sum / max(spectral_centroid_frames, 1), 1
        ),
        zero_crossing_rate=round(crossing_count / max(crossing_intervals, 1), 5),
        measurement_note=(
            "Active-audio percentage uses a -40 dBFS RMS threshold; it is an energy proxy, not "
            "speech recognition or voice activity detection. Pitch is sampled at about 4 Hz. "
            "Pitch peaks near the estimator limits are discarded as unreliable. The first audio "
            "stream is downmixed to mono for analysis."
        ),
    )


__all__ = ["AudioAnalysisCancelled", "AudioAnalysisReport", "analyze_audio_file"]
