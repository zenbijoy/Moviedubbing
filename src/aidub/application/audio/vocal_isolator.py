"""Simple vocal isolation via center-channel extraction (stereo)."""
from __future__ import annotations

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class VocalIsolator:
    @staticmethod
    def isolate(stereo: np.ndarray) -> np.ndarray:
        # stereo shape (N,2); vocals often center -> L-R cancellation for accompaniment
        if stereo.ndim != 2 or stereo.shape[1] < 2:
            return stereo
        left = stereo[:, 0]
        right = stereo[:, 1]
        vocals = (left + right) / 2.0
        return vocals.astype(np.float32)

    @staticmethod
    def accompaniment(stereo: np.ndarray) -> np.ndarray:
        if stereo.ndim != 2 or stereo.shape[1] < 2:
            return stereo
        return ((stereo[:, 0] - stereo[:, 1]) / 2.0).astype(np.float32)


__all__ = ["VocalIsolator"]
