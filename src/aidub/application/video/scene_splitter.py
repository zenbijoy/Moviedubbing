"""Split audio into scenes/segments based on silence threshold."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


@dataclass
class SceneSegment:
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class SceneSplitter:
    def __init__(self, silence_threshold_dbfs: float = -40.0, min_silence_s: float = 0.5, min_scene_s: float = 0.5) -> None:
        self.silence_threshold_dbfs = silence_threshold_dbfs
        self.min_silence_s = min_silence_s
        self.min_scene_s = min_scene_s

    def _threshold_linear(self) -> float:
        return 10.0 ** (self.silence_threshold_dbfs / 20.0)

    def split(self, clip: AudioClipData) -> list[SceneSegment]:
        if clip.samples.size == 0:
            return []
        thr = self._threshold_linear()
        sr = clip.sample_rate
        # frame-based
        frame = max(1, int(0.02 * sr))
        n_frames = clip.samples.size // frame
        is_silent = []
        for i in range(n_frames):
            chunk = clip.samples[i * frame:(i + 1) * frame]
            rms = float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0
            is_silent.append(rms < thr)
        # find silent runs
        segments = []
        scene_start = 0
        i = 0
        while i < n_frames:
            if is_silent[i]:
                # find run length
                j = i
                while j < n_frames and is_silent[j]:
                    j += 1
                run_s = (j - i) * frame / sr
                if run_s >= self.min_silence_s:
                    scene_end = i * frame / sr
                    if scene_end - scene_start >= self.min_scene_s:
                        segments.append(SceneSegment(scene_start, scene_end))
                    scene_start = j * frame / sr
                i = j
            else:
                i += 1
        # final scene
        end_s = clip.samples.size / sr
        if end_s - scene_start >= self.min_scene_s:
            segments.append(SceneSegment(scene_start, end_s))
        if not segments:
            segments.append(SceneSegment(0.0, end_s))
        return segments


__all__ = ["SceneSegment", "SceneSplitter"]
