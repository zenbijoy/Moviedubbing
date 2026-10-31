"""
Emotion Transfer and Original Actor Performance Extraction Service.

Extracts dynamic vocal energy, pitch inflection, and arousal from the
original actor's isolated vocal stem to drive synthetic performance.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from aidub.domain.emotion import EmotionSpec
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)


class EmotionTransferService:
    """Analyzes acoustic features of actor vocal stems and measures emotion match."""

    def extract_emotion_features(self, clip: AudioClipData) -> dict[str, float]:
        """Calculates acoustic features correlating with emotion dynamics."""
        if clip.samples.size == 0:
            return {"energy_mean": 0.0, "energy_std": 0.0, "zcr": 0.0, "estimated_arousal": 0.35}

        samples = clip.samples
        # Energy / RMS
        frame_len = max(64, int(clip.sample_rate * 0.030))
        n_frames = max(1, samples.size // frame_len)
        frames = samples[: n_frames * frame_len].reshape(n_frames, frame_len)

        rms_per_frame = np.sqrt(np.mean(frames**2, axis=1) + 1e-9)
        energy_mean = float(np.mean(rms_per_frame))
        energy_std = float(np.std(rms_per_frame))

        # Zero-crossing rate (indicates breathiness / high-frequency tension)
        zero_crossings = np.sum(np.diff(np.sign(samples)) != 0) / float(samples.size)

        # Estimated arousal based on energy variability and dynamic range
        dyn_range = float(np.max(rms_per_frame) - np.min(rms_per_frame))
        arousal = float(np.clip(0.20 + (dyn_range * 1.5) + (energy_std * 2.0), 0.05, 0.98))

        return {
            "energy_mean": round(energy_mean, 4),
            "energy_std": round(energy_std, 4),
            "zero_crossing_rate": round(float(zero_crossings), 4),
            "dynamic_range": round(dyn_range, 4),
            "estimated_arousal": round(arousal, 3),
        }

    def transfer_emotion_intent(
        self,
        source_clip: AudioClipData,
        base_category: str = "Dramatic",
    ) -> EmotionSpec:
        """Derives an EmotionSpec intent mapped from the source actor's performance."""
        feats = self.extract_emotion_features(source_clip)
        arousal = feats["estimated_arousal"]

        # Derive valence and dominance estimate
        valence = 0.0
        dominance = float(np.clip((arousal - 0.40) * 1.2, -0.8, 0.9))

        return EmotionSpec(
            primary_category=base_category,
            intensity=round(float(np.clip(arousal * 1.4, 0.5, 1.8)), 2),
            valence=round(valence, 2),
            arousal=arousal,
            dominance=round(dominance, 2),
            breathiness=round(float(np.clip(feats["zero_crossing_rate"] * 2.0, 0.0, 0.8)), 2),
        )

    def evaluate_emotion_match_score(
        self,
        source_clip: AudioClipData,
        dub_clip: AudioClipData,
    ) -> float:
        """
        Computes a compliance score (0.0 to 1.0) indicating how faithfully the
        dubbed take matches the source actor's dynamic energy and arousal trajectory.
        """
        src_feats = self.extract_emotion_features(source_clip)
        dub_feats = self.extract_emotion_features(dub_clip)

        # Compare arousal and energy std
        arousal_diff = abs(src_feats["estimated_arousal"] - dub_feats["estimated_arousal"])
        dyn_diff = abs(src_feats["dynamic_range"] - dub_feats["dynamic_range"])

        # Similarity penalty
        penalty = (arousal_diff * 0.6) + (dyn_diff * 0.4)
        score = float(np.clip(1.0 - penalty, 0.0, 1.0))
        return round(score, 3)


__all__ = [
    "EmotionTransferService",
]
