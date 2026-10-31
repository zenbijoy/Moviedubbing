"""
Emotion Studio Editor Service.

Provides:
  - 12 Hollywood-grade cinematic presets with 0% to 200% intensity scaling.
  - 3D Continuous Valence-Arousal-Dominance (PAD) vectors.
  - Native SSML generation for Edge-TTS and Azure Neural synthesis.
  - Acoustic mapping for RVC pitch contour, formant adjustments, and micro-inflections.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from aidub.application.voice.pro_emotion_engine import (
    CINEMATIC_EMOTION_PRESETS,
    MicroInflections,
    PADVector,
)
from aidub.domain.emotion import (
    EmotionCurve,
    EmotionSpec,
    VocalizationMarker,
    VocalizationMarkerType,
)

logger = logging.getLogger(__name__)


class EmotionEditorService:
    """Manages directorial emotion tweaking, curve envelopes, and SSML generation."""

    def __init__(self) -> None:
        self.presets = CINEMATIC_EMOTION_PRESETS

    def list_preset_names(self) -> list[str]:
        return list(self.presets.keys())

    def apply_preset(self, preset_name: str, intensity: float = 1.0) -> EmotionSpec:
        """Constructs an EmotionSpec from a named preset and intensity factor."""
        if preset_name not in self.presets:
            preset_name = "Neutral"

        pad, inflect, _ = self.presets[preset_name]
        clamped_intensity = float(np.clip(intensity, 0.0, 2.0))

        return EmotionSpec(
            primary_category=preset_name,
            intensity=clamped_intensity,
            valence=float(pad.valence * clamped_intensity),
            arousal=float(pad.arousal * clamped_intensity),
            dominance=float(pad.dominance * clamped_intensity),
            breathiness=float(inflect.breathiness_pct / 100.0),
            tremble=float(inflect.tremble_pct / 100.0),
            throat_tension=float(inflect.throat_tension_pct / 100.0),
            vocal_fry=float(inflect.vocal_fry_pct / 100.0),
        )

    def calculate_acoustic_parameters(self, spec: EmotionSpec) -> dict[str, float]:
        """
        Translates psychological PAD coordinates into synthesis engine parameters:
          - pitch_scale: fundamental frequency multiplier (e.g. 0.85 to 1.35)
          - rate_scale: speaking tempo multiplier (e.g. 0.80 to 1.30)
          - volume_db: relative dynamic level in dB (-6.0 to +4.0)
          - formant_cents: vocal tract brightness (+/- 250 cents)
        """
        inten = spec.intensity
        # Arousal drives speaking rate and energy
        rate = 1.0 + ((spec.arousal - 0.35) * 0.40 * inten)
        # Dominance and valence drive pitch and chest resonance
        pitch = 1.0 + ((spec.dominance * 0.15 + (spec.arousal - 0.35) * 0.20) * inten)
        # Volume
        volume_db = float((spec.arousal - 0.35) * 6.0 * inten)
        # Formant shift
        formant_cents = float((spec.dominance * 120.0 + spec.valence * 60.0) * inten)

        return {
            "pitch_scale": round(float(np.clip(pitch, 0.75, 1.40)), 3),
            "rate_scale": round(float(np.clip(rate, 0.70, 1.40)), 3),
            "volume_db": round(float(np.clip(volume_db, -8.0, 6.0)), 2),
            "formant_cents": round(float(np.clip(formant_cents, -300.0, 300.0)), 1),
            "throat_tension": spec.throat_tension,
            "breathiness": spec.breathiness,
        }

    def generate_ssml(
        self,
        text: str,
        spec: EmotionSpec,
        voice_name: str = "bn-BD-PradeepNeural",
    ) -> str:
        """Generates W3C-compliant SSML with prosody and expressive markers."""
        params = self.calculate_acoustic_parameters(spec)

        # Convert pitch multiplier to percentage
        pitch_pct = int(round((params["pitch_scale"] - 1.0) * 100.0))
        pitch_str = f"{'+' if pitch_pct >= 0 else ''}{pitch_pct}%"

        # Convert rate multiplier to percentage
        rate_pct = int(round((params["rate_scale"] - 1.0) * 100.0))
        rate_str = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"

        volume_str = f"{params['volume_db']:+.1f}dB"

        # Build vocalization breaks
        ssml_body = text
        for marker in sorted(spec.markers, key=lambda m: m.timestamp_s, reverse=True):
            break_tag = f'<break time="{int(marker.duration_s * 1000)}ms"/>'
            ssml_body += f" {break_tag}"

        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="bn-BD">\n'
            f'  <voice name="{voice_name}">\n'
            f'    <prosody pitch="{pitch_str}" rate="{rate_str}" volume="{volume_str}">\n'
            f"      {ssml_body}\n"
            f"    </prosody>\n"
            f"  </voice>\n"
            f"</speak>"
        )

    def add_vocalization_marker(
        self,
        spec: EmotionSpec,
        marker_type: VocalizationMarkerType,
        timestamp_s: float,
        level_db: float = -6.0,
        duration_s: float = 0.25,
    ) -> VocalizationMarker:
        marker = VocalizationMarker(
            marker_type=marker_type,
            timestamp_s=timestamp_s,
            level_db=level_db,
            duration_s=duration_s,
        )
        spec.markers.append(marker)
        return marker


__all__ = [
    "EmotionEditorService",
]
