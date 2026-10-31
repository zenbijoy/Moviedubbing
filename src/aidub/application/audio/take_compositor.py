"""
Take comping: assemble a seamless master vocal track from selected regions of multiple takes.
Supports sample-accurate equal-power crossfading across comp splice boundaries.
"""
from __future__ import annotations

import numpy as np

from aidub.domain.audio_edit import CompingRegion
from aidub.media.pro_audio_editor import AudioClipData


class TakeCompositor:
    """
    Assembles a final master dialogue track from comped regions across multiple takes.
    Eliminates boundary splice clicks with automatic micro-crossfades.
    """

    @staticmethod
    def total_duration(regions: list[CompingRegion]) -> float:
        return sum(max(0.0, r.end_s - r.start_s) for r in regions)

    @classmethod
    def build_master(
        cls,
        regions: list[CompingRegion],
        takes: dict[str, AudioClipData],
        sr: int = 48000,
        crossfade_ms: float = 0.0,
    ) -> AudioClipData:
        """
        Builds a composite master audio track from comped regions.
        `crossfade_ms`: micro-crossfade overlap in milliseconds between adjacent take splices.
        """
        chunks: list[np.ndarray] = []
        for r in regions:
            clip = takes.get(r.take_id)
            if clip is None:
                continue
            start = int(r.start_s * sr)
            end = int(r.end_s * sr)
            start = max(0, min(start, clip.samples.size))
            end = max(start, min(end, clip.samples.size))
            segment = clip.samples[start:end].copy()
            if abs(r.gain_db) > 0.01:
                gain = 10.0 ** (r.gain_db / 20.0)
                segment = segment * gain
            chunks.append(segment.astype(np.float32))

        if not chunks:
            return AudioClipData(samples=np.array([], dtype=np.float32), sample_rate=sr)

        if len(chunks) == 1 or crossfade_ms <= 0.0:
            master = np.concatenate(chunks).astype(np.float32)
            return AudioClipData(samples=master, sample_rate=sr)

        # Multi-chunk assembly with micro-crossfades
        fade_samples = max(2, int(sr * (crossfade_ms / 1000.0)))
        assembled = chunks[0]

        for next_chunk in chunks[1:]:
            cur_fade = min(fade_samples, assembled.size // 3, next_chunk.size // 3)
            if cur_fade > 1:
                t = np.linspace(0.0, np.pi * 0.5, cur_fade, dtype=np.float32)
                f_out = np.cos(t)
                f_in = np.sin(t)

                overlap = (assembled[-cur_fade:] * f_out) + (next_chunk[:cur_fade] * f_in)
                assembled = np.concatenate([assembled[:-cur_fade], overlap, next_chunk[cur_fade:]])
            else:
                assembled = np.concatenate([assembled, next_chunk])

        return AudioClipData(samples=assembled.astype(np.float32), sample_rate=sr)


__all__ = ["TakeCompositor"]
