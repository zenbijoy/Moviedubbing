"""
Broadcast sidechain ducking engine: reduces background music/ambience when dialogue is present.
Provides smooth attack, hold time, and release gain ramps to prevent clicking or pumping.
"""
from __future__ import annotations

import math
import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class SidechainDucker:
    """
    Studio-grade sidechain ducker for dialogue-over-music mixing.
    Ducks background music smoothly with anti-pumping hold hysteresis and click-free attack/release.
    """

    def __init__(
        self,
        threshold_dbfs: float = -30.0,
        duck_db: float = -12.0,
        attack_ms: float = 15.0,
        release_ms: float = 120.0,
        hold_ms: float = 80.0,
    ) -> None:
        self.threshold_dbfs = threshold_dbfs
        self.duck_db = min(0.0, duck_db)
        self.attack_ms = max(1.0, attack_ms)
        self.release_ms = max(10.0, release_ms)
        self.hold_ms = max(0.0, hold_ms)

    def process(self, music: AudioClipData, dialogue: AudioClipData) -> AudioClipData:
        if music.samples.size == 0:
            return music
        if dialogue.samples.size == 0:
            return music.clone()

        sr = music.sample_rate
        n = min(music.samples.size, dialogue.samples.size)

        hop = max(16, int(sr * 0.005))  # 5ms RMS analysis window
        n_blocks = max(1, n // hop)

        thr_linear = 10.0 ** (self.threshold_dbfs / 20.0)
        duck_linear = 10.0 ** (self.duck_db / 20.0)

        # 1. Detect dialogue voice activity with hold timer
        hold_blocks = int((self.hold_ms / 1000.0) * (sr / hop))
        active_blocks = np.zeros(n_blocks, dtype=bool)

        hold_counter = 0
        for b in range(n_blocks):
            s_idx = b * hop
            e_idx = min(n, (b + 1) * hop)
            chunk = dialogue.samples[s_idx:e_idx]
            rms = float(np.sqrt(np.mean(chunk**2))) if chunk.size > 0 else 0.0

            if rms >= thr_linear:
                active_blocks[b] = True
                hold_counter = hold_blocks
            elif hold_counter > 0:
                active_blocks[b] = True
                hold_counter -= 1
            else:
                active_blocks[b] = False

        # 2. Continuous sample-by-sample exponential smoothing filter
        alpha_att = math.exp(-1.0 / max(1.0, sr * (self.attack_ms / 1000.0)))
        alpha_rel = math.exp(-1.0 / max(1.0, sr * (self.release_ms / 1000.0)))

        full_gain = np.ones(music.samples.size, dtype=np.float32)
        cur_gain = 1.0

        for b in range(n_blocks):
            target = duck_linear if active_blocks[b] else 1.0
            s_idx = b * hop
            e_idx = min(n, (b + 1) * hop)
            for s in range(s_idx, e_idx):
                if target < cur_gain:  # Ducking down into dialogue (attack)
                    cur_gain = alpha_att * cur_gain + (1.0 - alpha_att) * target
                else:  # Recovering music level after speech (release)
                    cur_gain = alpha_rel * cur_gain + (1.0 - alpha_rel) * target
                full_gain[s] = cur_gain

        # If music is longer than dialogue, smoothly release remaining music to unity
        if music.samples.size > n:
            for s in range(n, music.samples.size):
                cur_gain = alpha_rel * cur_gain + (1.0 - alpha_rel) * 1.0
                full_gain[s] = cur_gain

        out = (music.samples * full_gain).astype(np.float32)
        return AudioClipData(samples=out, sample_rate=sr)


__all__ = ["SidechainDucker"]
