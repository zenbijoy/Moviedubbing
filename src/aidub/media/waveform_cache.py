"""Multi-resolution real PCM audio waveform peak generator and cache.

Extracts real audio samples from WAV/MP3/M4A/FLAC/OGG files using soundfile,
computes min/max peak envelopes via chunked block processing to conserve RAM,
caches binary peak data to disk, and provides fast sub-millisecond queries
for timeline rendering at any zoom level.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Default peaks resolution: 100 peak points per second of audio
DEFAULT_PEAKS_PER_SECOND = 100


class WaveformCache:
    """Manages generation, disk caching, and slice queries of real audio peaks."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        if cache_dir is None:
            self._cache_dir = Path.home() / ".cache" / "aidub" / "peaks"
        else:
            self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, tuple[float, np.ndarray]] = {}  # key -> (duration, peaks_array)

    def _cache_key(self, audio_path: Path) -> str:
        stat = audio_path.stat()
        raw = f"{audio_path.resolve()}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_audio_peaks(
        self,
        audio_path: Path | str,
        peaks_per_second: int = DEFAULT_PEAKS_PER_SECOND,
    ) -> tuple[float, np.ndarray]:
        """Load or compute (min, max) peak array for an audio file.

        Returns:
            (duration_seconds, peaks_array) where peaks_array has shape (N, 2),
            dtype float32, and values in [-1.0, 1.0].
        """
        p = Path(audio_path)
        if not p.is_file():
            return 0.0, np.zeros((0, 2), dtype=np.float32)

        cache_key = self._cache_key(p)
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        disk_file = self._cache_dir / f"{cache_key}_{peaks_per_second}.npy"
        meta_file = self._cache_dir / f"{cache_key}_{peaks_per_second}.meta"

        if disk_file.is_file() and meta_file.is_file():
            try:
                duration = float(meta_file.read_text(encoding="utf-8").strip())
                peaks = np.load(str(disk_file))
                self._memory_cache[cache_key] = (duration, peaks)
                return duration, peaks
            except Exception as exc:
                logger.debug("Failed reading cached waveform peaks: %s", exc)

        # Compute peaks via chunked streaming
        duration, peaks = self._compute_peaks_streaming(p, peaks_per_second)
        try:
            np.save(str(disk_file), peaks)
            meta_file.write_text(str(duration), encoding="utf-8")
        except Exception as exc:
            logger.debug("Could not write waveform cache to disk: %s", exc)

        self._memory_cache[cache_key] = (duration, peaks)
        return duration, peaks

    def _compute_peaks_streaming(
        self,
        audio_path: Path,
        peaks_per_second: int,
    ) -> tuple[float, np.ndarray]:
        """Stream audio in 64k sample blocks, computing min and max per block."""
        try:
            with sf.SoundFile(str(audio_path)) as f:
                sr = f.samplerate
                channels = f.channels
                frames = f.frames
                if sr <= 0 or frames <= 0:
                    return 0.0, np.zeros((0, 2), dtype=np.float32)

                duration = frames / float(sr)
                samples_per_peak = max(1, int(sr / peaks_per_second))
                total_peaks = int(np.ceil(frames / samples_per_peak))

                peaks = np.zeros((total_peaks, 2), dtype=np.float32)
                peak_idx = 0

                # Buffer for leftover samples between chunks
                chunk_size = 65536
                leftover = np.zeros((0,), dtype=np.float32)

                while True:
                    data = f.read(chunk_size, dtype="float32")
                    if len(data) == 0:
                        break

                    # Downmix multichannel to mono by averaging
                    if channels > 1:
                        mono = np.mean(data, axis=1)
                    else:
                        mono = data

                    if len(leftover) > 0:
                        combined = np.concatenate([leftover, mono])
                    else:
                        combined = mono

                    n_full_blocks = len(combined) // samples_per_peak
                    if n_full_blocks > 0:
                        usable = combined[: n_full_blocks * samples_per_peak]
                        reshaped = usable.reshape(n_full_blocks, samples_per_peak)
                        block_mins = np.min(reshaped, axis=1)
                        block_maxs = np.max(reshaped, axis=1)

                        end_idx = min(total_peaks, peak_idx + n_full_blocks)
                        count = end_idx - peak_idx
                        peaks[peak_idx:end_idx, 0] = block_mins[:count]
                        peaks[peak_idx:end_idx, 1] = block_maxs[:count]
                        peak_idx += count

                        leftover = combined[n_full_blocks * samples_per_peak :]
                    else:
                        leftover = combined

                if len(leftover) > 0 and peak_idx < total_peaks:
                    peaks[peak_idx, 0] = np.min(leftover)
                    peaks[peak_idx, 1] = np.max(leftover)
                    peak_idx += 1

                # Normalize peak amplitudes to [-1.0, 1.0] if safe
                max_amp = float(np.max(np.abs(peaks[:peak_idx])))
                if max_amp > 1.01:
                    peaks[:peak_idx] /= max_amp

                return duration, peaks[:peak_idx]
        except Exception as exc:
            logger.warning("Error computing waveform peaks for %s: %s", audio_path, exc)
            return 0.0, np.zeros((0, 2), dtype=np.float32)

    def query_slice_peaks(
        self,
        audio_path: Path | str,
        start_sec: float,
        duration_sec: float,
        num_points: int,
        peaks_per_second: int = DEFAULT_PEAKS_PER_SECOND,
    ) -> list[tuple[float, float]]:
        """Query min/max amplitude peaks for a time window resampled to num_points.

        Returns list of (min_val, max_val) normalized in [-1.0, 1.0].
        """
        if num_points <= 0 or duration_sec <= 0.0:
            return [(0.0, 0.0)] * max(0, num_points)

        total_dur, peaks = self.get_audio_peaks(audio_path, peaks_per_second)
        if len(peaks) == 0 or total_dur <= 0.0:
            return [(0.0, 0.0)] * num_points

        end_sec = start_sec + duration_sec
        total_peaks = len(peaks)

        # Map start/end seconds to peak index range
        start_idx = int(np.clip(start_sec * peaks_per_second, 0, total_peaks))
        end_idx = int(np.clip(end_sec * peaks_per_second, 0, total_peaks))

        if start_idx >= end_idx or start_idx >= total_peaks:
            return [(0.0, 0.0)] * num_points

        sub_peaks = peaks[start_idx:end_idx]
        sub_len = len(sub_peaks)

        if sub_len == num_points:
            return [(float(mn), float(mx)) for mn, mx in sub_peaks]

        # Resample sub_peaks to exactly num_points
        indices = np.linspace(0, sub_len, num_points + 1, dtype=int)
        result: list[tuple[float, float]] = []
        for i in range(num_points):
            b_start = indices[i]
            b_end = max(b_start + 1, indices[i + 1])
            block = sub_peaks[b_start:b_end]
            if len(block) > 0:
                mn = float(np.min(block[:, 0]))
                mx = float(np.max(block[:, 1]))
            else:
                mn, mx = 0.0, 0.0
            result.append((mn, mx))

        return result


# Global singleton cache instance
_GLOBAL_WAVEFORM_CACHE: WaveformCache | None = None


def get_waveform_cache() -> WaveformCache:
    """Access global WaveformCache instance."""
    global _GLOBAL_WAVEFORM_CACHE
    if _GLOBAL_WAVEFORM_CACHE is None:
        _GLOBAL_WAVEFORM_CACHE = WaveformCache()
    return _GLOBAL_WAVEFORM_CACHE


__all__ = [
    "DEFAULT_PEAKS_PER_SECOND",
    "WaveformCache",
    "get_waveform_cache",
]

