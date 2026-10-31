"""
Studio Spectral De-Reverberation Engine for Movie Dialogue Dubbing.
Removes room reflections, flutter echo, and hall reverberation using STFT spectral decay estimation.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from aidub.media.pro_audio_editor import AudioClipData


class DeReverbEngine:
    """
    DSP de-reverberation engine modeled after iZotope RX De-Reverb / Cedar Studio.
    Estimates late reverberation power spectra and suppresses diffuse room reflections
    using multi-band spectral subtraction and Wiener filtering.
    """

    @classmethod
    def reduce(
        cls,
        clip: AudioClipData,
        amount: float = 0.5,
        decay_factor: float = 0.75,
        delay_frames: int = 4,
    ) -> AudioClipData:
        """
        Suppresses room reverberation tails while preserving direct vocal transients.
        `amount`: 0.0 (bypass) to 1.0 (aggressive de-reverb).
        """
        if clip.samples.size == 0 or amount <= 0.0:
            return clip.clone()

        amount = float(np.clip(amount, 0.0, 1.0))
        samples = clip.samples.astype(np.float32)
        sr = clip.sample_rate

        # Micro test vector fallback
        if samples.size < 64:
            # Gentle attenuation without zero-crossing distortion
            scaled = samples * (1.0 - (amount * 0.1))
            return AudioClipData(samples=scaled.astype(np.float32), sample_rate=sr)

        # STFT parameters
        nperseg = min(512, 1 << int(np.floor(np.log2(samples.size))))
        nperseg = max(64, nperseg)
        noverlap = nperseg * 3 // 4

        # Forward STFT
        f, t, Zxx = signal.stft(
            samples,
            fs=sr,
            window="hann",
            nperseg=nperseg,
            noverlap=noverlap,
            boundary="zeros",
        )

        mag = np.abs(Zxx)
        power = mag**2
        n_freqs, n_frames = mag.shape

        # Late reverberation power estimation via delayed recursive smoothing
        late_power = np.zeros_like(power)
        # Minimum gain floor to prevent musical noise artifacts
        gain_floor = max(0.12, 1.0 - (amount * 0.88))

        gamma = float(np.clip(decay_factor, 0.5, 0.95))
        d = max(1, min(delay_frames, n_frames // 4))

        for frame_idx in range(n_frames):
            if frame_idx >= d:
                delayed_pow = power[:, frame_idx - d]
                late_power[:, frame_idx] = (
                    gamma * late_power[:, frame_idx - 1] + (1.0 - gamma) * delayed_pow
                )
            else:
                late_power[:, frame_idx] = power[:, frame_idx] * 0.1

        # Wiener-like spectral suppression gain
        eps = 1e-8
        noise_ratio = late_power / (power + eps)
        gain_matrix = 1.0 - (amount * np.sqrt(np.clip(noise_ratio, 0.0, 1.0)))
        gain_matrix = np.clip(gain_matrix, gain_floor, 1.0)

        # Smooth spectral gain across adjacent frequency bins to prevent phase artifacts
        if n_freqs > 4:
            kernel = np.array([0.2, 0.6, 0.2], dtype=np.float32)
            gain_matrix = signal.convolve2d(gain_matrix, kernel[:, None], mode="same", boundary="symm")
            gain_matrix = np.clip(gain_matrix, gain_floor, 1.0)

        # Apply gain to complex STFT
        Zxx_clean = Zxx * gain_matrix

        # Inverse STFT
        _, clean_samples = signal.istft(
            Zxx_clean,
            fs=sr,
            window="hann",
            nperseg=nperseg,
            noverlap=noverlap,
            boundary="zeros",
        )

        # Match exact input duration
        if clean_samples.size > samples.size:
            clean_samples = clean_samples[: samples.size]
        elif clean_samples.size < samples.size:
            clean_samples = np.pad(clean_samples, (0, samples.size - clean_samples.size))

        clean_samples = np.clip(clean_samples, -1.0, 1.0).astype(np.float32)
        return AudioClipData(samples=clean_samples, sample_rate=sr)


__all__ = ["DeReverbEngine"]
