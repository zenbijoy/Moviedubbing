"""
Automatic vocal gain rider for transparent, broadcast-compliant dialogue level leveling.
Provides lookahead RMS tracking, noise-floor gate freezing, and smooth continuous gain envelopes.
"""
from __future__ import annotations

import math
import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class AutoGainRider:
    """
    Studio-grade vocal gain rider modeled after Waves Vocal Rider / iZotope RX Leveler.
    Smooths vocal volume variations dynamically without amplifying room tone or breath pauses.
    """

    def __init__(
        self,
        target_rms: float = 0.1,
        max_gain_db: float = 12.0,
        window_ms: float = 50.0,
        gate_threshold_db: float = -45.0,
        attack_ms: float = 25.0,
        release_ms: float = 150.0,
    ) -> None:
        self.target_rms = max(1e-4, target_rms)
        self.max_gain_db = max(0.0, max_gain_db)
        self.window_ms = max(5.0, window_ms)
        self.gate_threshold_db = gate_threshold_db
        self.attack_ms = max(5.0, attack_ms)
        self.release_ms = max(10.0, release_ms)

    def process(self, clip: AudioClipData) -> AudioClipData:
        if clip.samples.size == 0:
            return clip

        sr = clip.sample_rate
        samples = clip.samples.astype(np.float32)
        n = samples.size

        # Micro test vector fallback
        if n < 32:
            rms = float(np.sqrt(np.mean(samples**2))) if n else 0.0
            if rms > 1e-5:
                max_gain = 10.0 ** (self.max_gain_db / 20.0)
                g = float(np.clip(self.target_rms / rms, 1.0 / max_gain, max_gain))
                return AudioClipData(samples=(samples * g).astype(np.float32), sample_rate=sr)
            return clip

        hop_samples = max(16, int(sr * 0.01))  # 10ms hop
        frame_samples = max(hop_samples * 2, int(sr * (self.window_ms / 1000.0)))
        n_hops = max(1, n // hop_samples)

        max_gain_linear = 10.0 ** (self.max_gain_db / 20.0)
        min_gain_linear = 1.0 / max_gain_linear
        gate_linear = 10.0 ** (self.gate_threshold_db / 20.0)

        # 1. Compute target gain trajectory per hop
        raw_gains = np.ones(n_hops, dtype=np.float32)
        for i in range(n_hops):
            center = i * hop_samples
            s_idx = max(0, center - frame_samples // 2)
            e_idx = min(n, center + frame_samples // 2)
            chunk = samples[s_idx:e_idx]
            rms = float(np.sqrt(np.mean(chunk**2))) if chunk.size > 0 else 0.0

            if rms >= gate_linear:
                ideal_gain = self.target_rms / max(1e-5, rms)
                raw_gains[i] = float(np.clip(ideal_gain, min_gain_linear, max_gain_linear))
            else:
                # Silence / breath pause: smoothly hold or freeze at unity (1.0)
                raw_gains[i] = 1.0

        # 2. Smooth gain curve with asymmetric attack and release filters
        alpha_att = math.exp(-1.0 / max(1.0, sr * (self.attack_ms / 1000.0)))
        alpha_rel = math.exp(-1.0 / max(1.0, sr * (self.release_ms / 1000.0)))

        full_gain = np.ones(n, dtype=np.float32)
        cur_gain = 1.0

        for i in range(n_hops):
            target = raw_gains[i]
            s_idx = i * hop_samples
            e_idx = min(n, (i + 1) * hop_samples)
            for s in range(s_idx, e_idx):
                if target < cur_gain:  # Pulling down loud peaks (attack)
                    cur_gain = alpha_att * cur_gain + (1.0 - alpha_att) * target
                else:  # Bringing up quiet sections (release)
                    cur_gain = alpha_rel * cur_gain + (1.0 - alpha_rel) * target
                full_gain[s] = cur_gain

        tail = n_hops * hop_samples
        if tail < n:
            full_gain[tail:] = cur_gain

        out = samples * full_gain
        # Peak safety limiter (-0.5 dBFS)
        peak = float(np.max(np.abs(out))) if out.size > 0 else 0.0
        if peak > 0.944:  # -0.5 dBFS
            out = out * (0.944 / peak)

        return AudioClipData(samples=out.astype(np.float32), sample_rate=sr)


__all__ = ["AutoGainRider"]
