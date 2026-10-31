"""
True spectral formant shifting independent of fundamental pitch (F0).
Extracts vocal tract spectral envelope via cepstral liftering and warps formant resonances.
"""
from __future__ import annotations

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class FormantShifter:
    """
    Vocal tract formant modification engine.
    Extracts the smooth vocal tract spectral envelope using cepstral analysis,
    scales only the formant peaks, and recombines with untouched harmonic pitch structure.
    """

    @classmethod
    def shift(
        cls,
        clip: AudioClipData,
        formant_ratio: float = 1.0,
        lifter_quefrency: int = 20,
    ) -> AudioClipData:
        """
        Shifts vocal tract formant frequencies by `formant_ratio`.
        formant_ratio > 1.0 shifts formants higher (smaller vocal tract, feminine/child timbre).
        formant_ratio < 1.0 shifts formants lower (larger vocal tract, deep/masculine timbre).
        Fundamental pitch (F0) is strictly preserved.
        """
        if clip.samples.size == 0 or abs(formant_ratio - 1.0) < 1e-6:
            return clip.clone()

        samples = clip.samples.astype(np.float64)
        n = samples.size
        sr = clip.sample_rate

        # Forward real FFT
        spectrum = np.fft.rfft(samples)
        mag = np.abs(spectrum)
        phase = np.angle(spectrum)
        eps = 1e-7

        # 1. Real Cepstrum analysis to extract vocal tract envelope
        log_mag = np.log(mag + eps)
        # Create symmetric full spectrum for clean FFT round-trip
        if log_mag.size > 2:
            full_log = np.concatenate([log_mag, log_mag[-2:0:-1]])
        else:
            full_log = log_mag

        cepstrum = np.real(np.fft.ifft(full_log))

        # Lifter: preserve lower quefrency coefficients representing the vocal tract
        q_cut = max(3, min(lifter_quefrency, cepstrum.size // 6))
        lifter = np.zeros(cepstrum.size, dtype=np.float64)
        lifter[:q_cut] = 1.0
        lifter[-q_cut:] = 1.0

        smooth_log = np.real(np.fft.fft(cepstrum * lifter))
        envelope = np.exp(smooth_log[: mag.size])

        # 2. Extract fine harmonic pitch structure
        harmonics = mag / np.maximum(eps, envelope)

        # 3. Warp the vocal tract envelope
        freqs = np.fft.rfftfreq(n, 1.0 / sr)
        warped_freqs = freqs / max(0.1, float(formant_ratio))

        # Interpolate warped envelope onto original frequency grid
        warped_envelope = np.interp(
            freqs,
            warped_freqs,
            envelope,
            left=float(envelope[0]),
            right=float(envelope[-1]),
        )

        # 4. Recombine warped envelope with untouched harmonic pitch lines
        new_mag = warped_envelope * harmonics

        # Preserve overall energy scaling
        orig_energy = float(np.sum(mag**2))
        new_energy = float(np.sum(new_mag**2))
        if new_energy > eps and orig_energy > eps:
            new_mag *= np.sqrt(orig_energy / new_energy)

        # 5. Inverse FFT with original phase
        new_spectrum = new_mag * np.exp(1j * phase)
        out = np.fft.irfft(new_spectrum, n=n).astype(np.float32)
        out = np.clip(out, -1.0, 1.0)

        return AudioClipData(samples=out, sample_rate=sr)


__all__ = ["FormantShifter"]
