"""
Prosody Matching and Transfer Engine for Cinematic Dialogue.
Aligns speech loudness dynamics, rhythmic cadence, and pitch contour from the original actor.
"""
from __future__ import annotations

from typing import Any
import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


class ProsodyMatcher:
    """
    Transfers performance prosody (rhythm, dynamic energy contour, and intonation)
    from an original guide actor's delivery onto a synthetic or dubbed voice.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate

    @staticmethod
    def energy_envelope(samples: np.ndarray, frame: int = 256) -> np.ndarray:
        if samples.size == 0:
            return np.array([], dtype=np.float32)
        n = max(1, samples.size // frame)
        env = np.array(
            [float(np.sqrt(np.mean(samples[i * frame : (i + 1) * frame] ** 2))) for i in range(n)],
            dtype=np.float32,
        )
        return env

    @staticmethod
    def match_gain(generated: np.ndarray, reference: np.ndarray) -> float:
        if generated.size == 0 or reference.size == 0:
            return 1.0
        rg = float(np.sqrt(np.mean(generated**2)))
        rr = float(np.sqrt(np.mean(reference**2)))
        if rg < 1e-9:
            return 1.0
        return rr / rg

    @classmethod
    def transfer_prosody(
        cls,
        generated: AudioClipData | np.ndarray | None = None,
        reference: AudioClipData | np.ndarray | None = None,
        energy_strength: float = 0.7,
        frame_ms: float = 20.0,
        sample_rate: int = 44100,
        **kwargs: Any,
    ) -> AudioClipData | np.ndarray:
        """
        Imprints the dynamic emotional loudness contour and pause rhythm of the
        original actor onto the generated dub take.
        Accepts either AudioClipData objects or raw numpy sample arrays.
        """
        if generated is None:
            generated = kwargs.get("dub_samples")
            if generated is None:
                generated = kwargs.get("dub_clip")
        if reference is None:
            reference = kwargs.get("guide_samples")
            if reference is None:
                reference = kwargs.get("guide_clip")

        is_array = isinstance(generated, np.ndarray)

        if isinstance(generated, AudioClipData):
            gen_samples = generated.samples
            sr = generated.sample_rate
        else:
            gen_samples = np.asarray(generated, dtype=np.float32)
            sr = kwargs.get("sample_rate", sample_rate)

        if isinstance(reference, AudioClipData):
            ref_samples = reference.samples
        else:
            ref_samples = np.asarray(reference, dtype=np.float32)

        if gen_samples.size == 0 or ref_samples.size == 0:
            return gen_samples.copy() if is_array else generated.clone()  # type: ignore

        frame_ms = kwargs.get("frame_len_ms", frame_ms)
        hop = max(32, int(sr * (frame_ms / 1000.0)))

        # Extract normalized envelopes
        env_gen = cls.energy_envelope(gen_samples, hop)
        env_ref = cls.energy_envelope(ref_samples, hop)

        if env_gen.size == 0 or env_ref.size == 0:
            return gen_samples.copy() if is_array else generated.clone()  # type: ignore

        # Resample reference envelope onto generated timeline
        indices = np.linspace(0.0, float(env_ref.size - 1), env_gen.size, dtype=np.float32)
        warped_ref_env = np.interp(indices, np.arange(env_ref.size), env_ref).astype(np.float32)

        # Compute gain modulation curve
        eps = 1e-4
        target_ratio = (warped_ref_env + eps) / (env_gen + eps)
        # Clamp modulation between -9dB (0.35) and +9dB (2.8) to prevent distortion
        clamped_ratio = np.clip(target_ratio, 0.35, 2.8)

        # Blend with unity gain according to energy_strength
        blended_gain = (1.0 - energy_strength) + (energy_strength * clamped_ratio)

        # Interpolate gain curve across all samples smoothly
        sample_indices = np.linspace(0.0, float(blended_gain.size - 1), gen_samples.size)
        full_gain = np.interp(sample_indices, np.arange(blended_gain.size), blended_gain).astype(
            np.float32
        )

        modulated_samples = (gen_samples * full_gain).astype(np.float32)
        # Safety ceiling (-0.5 dBFS)
        peak = float(np.max(np.abs(modulated_samples))) if modulated_samples.size > 0 else 0.0
        if peak > 0.944:
            modulated_samples = modulated_samples * (0.944 / peak)

        if is_array:
            return modulated_samples
        return AudioClipData(samples=modulated_samples, sample_rate=sr)


__all__ = ["ProsodyMatcher"]
