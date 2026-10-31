"""
World-Class Pro Emotion Director & Engine for Cinematic Movie Dubbing.

Provides:
  - 3D Valence-Arousal-Dominance (PAD / VAD) psychological emotion vector space.
  - 12 Cinematic Hollywood Presets with 0% to 200% hyper-intensity scaling.
  - Multi-Keyframe Emotion Trajectory Envelope across dialogue duration.
  - Micro-Inflection synthesis parameters (tremble, breathiness, vocal fry, throat tension).
  - Original Actor Performance Emotion Extraction & Transfer.
  - Acoustic mapper translating PAD coordinates into engine-agnostic synthesis controls.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PADVector:
    """
    Continuous 3-dimensional psychological emotion vector:
      - Valence (-1.0 to 1.0): Negative/Agony vs Positive/Ecstasy
      - Arousal (0.0 to 1.0): Dormant/Sleepy vs Hyper-Excited/Explosive
      - Dominance (-1.0 to 1.0): Submissive/Terrified vs Authoritative/Commanding
    """

    valence: float = 0.0
    arousal: float = 0.35
    dominance: float = 0.0

    def clamped(self) -> PADVector:
        return PADVector(
            valence=float(np.clip(self.valence, -1.0, 1.0)),
            arousal=float(np.clip(self.arousal, 0.0, 1.0)),
            dominance=float(np.clip(self.dominance, -1.0, 1.0)),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PADVector:
        return cls(
            valence=float(data.get("valence", 0.0)),
            arousal=float(data.get("arousal", 0.35)),
            dominance=float(data.get("dominance", 0.0)),
        )


@dataclass
class MicroInflections:
    """Micro-inflection articulatory vocal dynamics."""

    tremble_pct: float = 0.0  # Vocal cord trembling (grief, terror) [0 - 100]
    breathiness_pct: float = 10.0  # Aspiration and intimate breath sound [0 - 100]
    vocal_fry_pct: float = 0.0  # Creaky low-register rumble [0 - 100]
    throat_tension_pct: float = 0.0  # Glottal constriction and strained neck muscles [0 - 100]

    def clamped(self) -> MicroInflections:
        return MicroInflections(
            tremble_pct=float(np.clip(self.tremble_pct, 0.0, 100.0)),
            breathiness_pct=float(np.clip(self.breathiness_pct, 0.0, 100.0)),
            vocal_fry_pct=float(np.clip(self.vocal_fry_pct, 0.0, 100.0)),
            throat_tension_pct=float(np.clip(self.throat_tension_pct, 0.0, 100.0)),
        )


@dataclass
class EmotionKeyframe:
    """Point in time along a dialogue cue with assigned emotion vector."""

    time_pct: float  # Normalized timestamp 0.0 (start) to 1.0 (end)
    pad: PADVector
    intensity: float = 1.0  # 0.0 to 2.0 (1.0 = standard, 2.0 = theatrical)


@dataclass
class EmotionTrajectory:
    """Dynamic emotion trajectory envelope over the course of a dialogue line."""

    keyframes: list[EmotionKeyframe] = field(default_factory=list)

    def evaluate_at(self, t: float) -> tuple[PADVector, float]:
        """Interpolate PAD vector and intensity at normalized time t in [0.0, 1.0]."""
        if not self.keyframes:
            return PADVector(), 1.0

        t = float(np.clip(t, 0.0, 1.0))
        sorted_kfs = sorted(self.keyframes, key=lambda k: k.time_pct)

        if t <= sorted_kfs[0].time_pct:
            return sorted_kfs[0].pad, sorted_kfs[0].intensity
        if t >= sorted_kfs[-1].time_pct:
            return sorted_kfs[-1].pad, sorted_kfs[-1].intensity

        # Find bounding keyframes
        for i in range(len(sorted_kfs) - 1):
            k1 = sorted_kfs[i]
            k2 = sorted_kfs[i + 1]
            if k1.time_pct <= t <= k2.time_pct:
                span = max(1e-4, k2.time_pct - k1.time_pct)
                weight = (t - k1.time_pct) / span
                # Smooth cosine interpolation
                w_smooth = (1.0 - math.cos(weight * math.pi)) * 0.5

                v = (1.0 - w_smooth) * k1.pad.valence + w_smooth * k2.pad.valence
                a = (1.0 - w_smooth) * k1.pad.arousal + w_smooth * k2.pad.arousal
                d = (1.0 - w_smooth) * k1.pad.dominance + w_smooth * k2.pad.dominance
                inten = (1.0 - w_smooth) * k1.intensity + w_smooth * k2.intensity
                return PADVector(v, a, d), inten

        return sorted_kfs[-1].pad, sorted_kfs[-1].intensity


# 12 Master Cinematic Film Presets
CINEMATIC_EMOTION_PRESETS: dict[str, tuple[PADVector, MicroInflections, str]] = {
    "Neutral": (
        PADVector(0.0, 0.35, 0.0),
        MicroInflections(tremble_pct=0, breathiness_pct=10, vocal_fry_pct=0, throat_tension_pct=0),
        "Natural conversational delivery with balanced composure.",
    ),
    "Heroic Defiance": (
        PADVector(0.55, 0.85, 0.90),
        MicroInflections(tremble_pct=5, breathiness_pct=5, vocal_fry_pct=15, throat_tension_pct=55),
        "Unshakeable determination, authoritative projection, chest resonance.",
    ),
    "Explosive Rage": (
        PADVector(-0.85, 0.98, 0.85),
        MicroInflections(tremble_pct=20, breathiness_pct=0, vocal_fry_pct=40, throat_tension_pct=90),
        "Thundering fury, glottal bite, clipped consonants, intense vocal drive.",
    ),
    "Broken Grief / Weeping": (
        PADVector(-0.90, 0.65, -0.75),
        MicroInflections(tremble_pct=85, breathiness_pct=65, vocal_fry_pct=25, throat_tension_pct=70),
        "Cracked pitch, stifled tears, heavy trembling vibrato and gasping pauses.",
    ),
    "Whispered Intimacy": (
        PADVector(0.35, 0.22, -0.25),
        MicroInflections(tremble_pct=0, breathiness_pct=90, vocal_fry_pct=10, throat_tension_pct=0),
        "Close-mic whispered cadence, deep breath warmth, conspiratorial tone.",
    ),
    "Terrified Panic": (
        PADVector(-0.95, 0.92, -0.90),
        MicroInflections(tremble_pct=90, breathiness_pct=75, vocal_fry_pct=0, throat_tension_pct=85),
        "High erratic pitch, rapid breath intake, helplessness, trembling fear.",
    ),
    "Sarcastic Mockery": (
        PADVector(0.20, 0.50, 0.60),
        MicroInflections(tremble_pct=0, breathiness_pct=15, vocal_fry_pct=50, throat_tension_pct=20),
        "Drawling cadence, exaggerated melodic pitch rise, condescending smirk.",
    ),
    "Romantic Warmth": (
        PADVector(0.85, 0.40, 0.25),
        MicroInflections(tremble_pct=0, breathiness_pct=40, vocal_fry_pct=10, throat_tension_pct=0),
        "Silky velvet timbre, gentle melodic fall, tender smile articulation.",
    ),
    "Sinister / Cold Threat": (
        PADVector(-0.60, 0.35, 0.85),
        MicroInflections(tremble_pct=0, breathiness_pct=10, vocal_fry_pct=60, throat_tension_pct=60),
        "Controlled icy monotone, low pitch, chilling precision without raising voice.",
    ),
    "Breathless Exhaustion": (
        PADVector(-0.25, 0.75, -0.40),
        MicroInflections(tremble_pct=45, breathiness_pct=95, vocal_fry_pct=20, throat_tension_pct=40),
        "Gasping between syllables, uneven rhythm, physical struggle for air.",
    ),
    "Joyful Laughter": (
        PADVector(0.95, 0.80, 0.50),
        MicroInflections(tremble_pct=15, breathiness_pct=30, vocal_fry_pct=0, throat_tension_pct=10),
        "Bouncy rhythmic cadence, bright upper harmonics, bubbling amusement.",
    ),
    "Desperate Pleading": (
        PADVector(-0.75, 0.78, -0.65),
        MicroInflections(tremble_pct=60, breathiness_pct=50, vocal_fry_pct=20, throat_tension_pct=75),
        "Strained upward inflection, urgent pleading pressure, cracking timbre.",
    ),
}


class ProEmotionDirectorEngine:
    """Engine orchestrating emotional performance generation, mapping, and actor extraction."""

    @classmethod
    def get_preset_names(cls) -> list[str]:
        return list(CINEMATIC_EMOTION_PRESETS.keys())

    @classmethod
    def get_preset(cls, name: str) -> tuple[PADVector, MicroInflections, str]:
        return CINEMATIC_EMOTION_PRESETS.get(name, CINEMATIC_EMOTION_PRESETS["Neutral"])

    @staticmethod
    def map_pad_to_performance(
        pad: PADVector,
        intensity: float = 1.0,
        micro: MicroInflections | None = None,
    ) -> dict[str, Any]:
        """
        Translates a 3D PAD emotion vector and micro-inflections into standardized
        synthesis parameters supported by neural voice engines:
          - pitch_shift_semitones
          - rate_multiplier
          - energy_scale
          - style_prompt
        """
        pad = pad.clamped()
        inten = max(0.0, min(2.0, intensity))
        m = (micro or MicroInflections()).clamped()

        # 1. Pitch shift (-6 to +6 semitones)
        # High arousal + high valence = bright high pitch; high dominance = deeper pitch
        pitch_delta = (
            (pad.arousal * 3.5)
            + (pad.valence * 1.5)
            - (pad.dominance * 2.2)
        ) * inten
        pitch_semitones = round(float(np.clip(pitch_delta, -6.0, 6.0)), 2)

        # 2. Speaking rate multiplier (0.75x to 1.35x)
        # High arousal + high tension speeds up; low arousal or sorrow slows down
        rate_delta = 1.0 + ((pad.arousal - 0.4) * 0.40) + (m.throat_tension_pct * 0.001)
        if pad.valence < -0.4 and pad.arousal < 0.5:
            rate_delta -= 0.15  # Sorrowful slow delivery
        rate = round(float(np.clip(rate_delta, 0.75, 1.35)), 2)

        # 3. Energy scale (0.6x to 1.6x)
        energy_val = 1.0 + ((pad.arousal * 0.5) + (pad.dominance * 0.2)) * inten
        energy = round(float(np.clip(energy_val, 0.6, 1.6)), 2)

        # 4. Generate expressive style prompt for neural LLM / TTS models
        descriptors = []
        if pad.arousal > 0.75 and pad.valence < -0.4:
            descriptors.append("furious and commanding")
        elif pad.arousal > 0.75 and pad.valence > 0.4:
            descriptors.append("exuberant and joyful")
        elif pad.arousal < 0.35 and pad.valence < -0.4:
            descriptors.append("mournful and sorrowful")
        elif pad.arousal < 0.35 and pad.dominance > 0.5:
            descriptors.append("calm, icy and menacing")
        elif m.breathiness_pct > 60:
            descriptors.append("soft whispered and breathless")

        if m.tremble_pct > 40:
            descriptors.append("with trembling vocal inflection")
        if m.vocal_fry_pct > 35:
            descriptors.append("with gravelly vocal fry")
        if m.throat_tension_pct > 50:
            descriptors.append("with tight throat tension")

        style_prompt = ", ".join(descriptors) if descriptors else "natural, authentic dialogue"

        return {
            "pad": pad.to_dict(),
            "intensity": round(inten, 2),
            "pitch_shift_semitones": pitch_semitones,
            "rate_multiplier": rate,
            "energy_scale": energy,
            "micro_inflections": {
                "tremble_pct": m.tremble_pct,
                "breathiness_pct": m.breathiness_pct,
                "vocal_fry_pct": m.vocal_fry_pct,
                "throat_tension_pct": m.throat_tension_pct,
            },
            "style_prompt": style_prompt,
        }

    @classmethod
    def blend_presets(cls, name_a: str, name_b: str, ratio: float) -> tuple[PADVector, MicroInflections, str]:
        """Linearly blend two cinematic presets. ratio 0.0 = A, 1.0 = B."""
        ratio = float(np.clip(ratio, 0.0, 1.0))
        pad_a, micro_a, _ = cls.get_preset(name_a)
        pad_b, micro_b, _ = cls.get_preset(name_b)
        blended_pad = PADVector(
            valence=pad_a.valence * (1.0 - ratio) + pad_b.valence * ratio,
            arousal=pad_a.arousal * (1.0 - ratio) + pad_b.arousal * ratio,
            dominance=pad_a.dominance * (1.0 - ratio) + pad_b.dominance * ratio,
        )
        blended_micro = MicroInflections(
            tremble_pct=micro_a.tremble_pct * (1.0 - ratio) + micro_b.tremble_pct * ratio,
            breathiness_pct=micro_a.breathiness_pct * (1.0 - ratio) + micro_b.breathiness_pct * ratio,
            vocal_fry_pct=micro_a.vocal_fry_pct * (1.0 - ratio) + micro_b.vocal_fry_pct * ratio,
            throat_tension_pct=micro_a.throat_tension_pct * (1.0 - ratio) + micro_b.throat_tension_pct * ratio,
        )
        return blended_pad.clamped(), blended_micro.clamped(), f"Blend({name_a}+{name_b}@{ratio:.2f})"

    @staticmethod
    def to_ssml(text: str, pad: PADVector, micro: MicroInflections | None = None, intensity: float = 1.0) -> str:
        """Render a SSML document from text + emotion PAD/micro-inflections."""
        perf = ProEmotionDirectorEngine.map_pad_to_performance(pad, intensity, micro)
        rate_pct = int(round((perf["rate_multiplier"] - 1.0) * 100))
        pitch_semi = perf["pitch_shift_semitones"]
        volume_db = round((perf["energy_scale"] - 1.0) * 6.0, 1)
        rate_str = f"{rate_pct:+d}%"
        pitch_str = f"{pitch_semi:+.2f}st"
        volume_str = f"{volume_db:+.1f}dB"
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            f'<speak version="1.1" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<prosody rate="{rate_str}" pitch="{pitch_str}" volume="{volume_str}">'
            f"{safe}"
            f"</prosody>"
            f"</speak>"
        )


    def extract_emotion_from_audio(wav_path: Path | str) -> tuple[PADVector, MicroInflections, str]:
        """
        Analyze the original movie actor's vocal performance track to automatically
        extract psychological emotion (Valence, Arousal, Dominance) and articulatory
        micro-inflections.
        """
        p = Path(wav_path)
        if not p.is_file():
            return PADVector(0.0, 0.4, 0.0), MicroInflections(), "Default (audio unavailable)"

        try:
            from aidub.media.pro_audio_editor import AudioClipData

            clip = AudioClipData.from_file(p)
            samples = clip.samples
            sr = clip.sample_rate

            if samples.size < sr * 0.2:  # Less than 200ms
                return PADVector(0.0, 0.4, 0.0), MicroInflections(), "Neutral (short cue)"

            # 1. Arousal estimation from RMS energy dynamics and crest factor
            rms = float(np.sqrt(np.mean(samples**2)))
            peak = float(np.max(np.abs(samples)))
            crest = peak / max(1e-4, rms)
            dynamic_range_db = 20.0 * math.log10(max(1e-4, peak / max(1e-4, rms)))

            arousal = float(np.clip(0.2 + (dynamic_range_db / 25.0) * 0.6, 0.1, 0.95))

            # 2. Dominance & Tension from spectral brightness (spectral centroid)
            fft_mag = np.abs(np.fft.rfft(samples[: min(samples.size, sr * 2)]))
            freqs = np.fft.rfftfreq(min(samples.size, sr * 2), 1.0 / sr)
            centroid = float(np.sum(freqs * fft_mag) / max(1e-6, np.sum(fft_mag)))

            # Higher centroid indicates vocal strain, loud projection or tension
            tension_pct = float(np.clip((centroid - 1200.0) / 2500.0 * 100.0, 0.0, 90.0))
            dominance = float(np.clip((centroid - 1500.0) / 2000.0, -0.8, 0.8))

            # 3. Valence estimation: pitch contour slope and variance
            # High energy variance with low spectral harmonicity correlates with distress/anger
            harm_ratio = float(np.max(fft_mag) / max(1e-4, np.mean(fft_mag)))
            valence = 0.2 if harm_ratio > 8.0 else -0.5

            pad = PADVector(valence=round(valence, 2), arousal=round(arousal, 2), dominance=round(dominance, 2))
            micro = MicroInflections(
                tremble_pct=round(max(0.0, (1.0 - harm_ratio / 15.0) * 40.0), 1),
                breathiness_pct=round(max(5.0, (centroid / 4000.0) * 35.0), 1),
                vocal_fry_pct=round(20.0 if centroid < 1400.0 else 5.0, 1),
                throat_tension_pct=round(tension_pct, 1),
            )

            explanation = (
                f"Extracted from actor performance: Arousal {arousal:.2f}, "
                f"Centroid {int(centroid)} Hz, Dominance {dominance:+.2f}."
            )
            return pad, micro, explanation
        except Exception as exc:
            logger.warning("Emotion extraction from audio failed: %s", exc)
            return PADVector(0.0, 0.4, 0.0), MicroInflections(), f"Fallback: {exc}"


__all__ = [
    "CINEMATIC_EMOTION_PRESETS",
    "EmotionKeyframe",
    "EmotionTrajectory",
    "MicroInflections",
    "PADVector",
    "ProEmotionDirectorEngine",
]
