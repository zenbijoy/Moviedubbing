"""
Non-Destructive Audio DSP Chain Application Service.

Applies sequential vocal mastering effects:
  - Parametric 4-band broadcast EQ
  - Dynamic de-essing
  - Dialogue leveler & true-peak limiter
  - Room acoustics & reverb matching
  - Pitch shifting & WSOLA time stretching
  - Peak normalization and S-curve anti-click fades
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

from aidub.domain.audio_edit import (
    DspEffectNode,
    DspEffectType,
    EffectRack,
    FadeSpec,
    FadeType,
)
from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine

logger = logging.getLogger(__name__)


class DspChain:
    """Non-destructive DSP processing chain for dialogue audio."""

    def __init__(self, engine: ProAudioDspEngine | None = None) -> None:
        self.engine: ProAudioDspEngine = engine or ProAudioDspEngine()

    def process_clip(self, clip: AudioClipData, rack: EffectRack) -> AudioClipData:
        """Applies all active effects in the rack sequentially to the in-memory clip."""
        active_effects = rack.get_active_effects()
        if not active_effects:
            return clip

        current = clip
        for node in active_effects:
            try:
                current = self._apply_single_effect(current, node)
            except Exception as ex:
                logger.error(
                    "DspChain error applying effect %s (params=%s): %s",
                    node.effect_type.value,
                    node.parameters,
                    ex,
                )
        return current

    def _apply_single_effect(
        self, clip: AudioClipData, node: DspEffectNode
    ) -> AudioClipData:
        params = node.parameters

        if node.effect_type == DspEffectType.PARAMETRIC_EQ:
            return self.engine.apply_parametric_eq(
                clip,
                low_shelf_gain_db=float(params.get("low_shelf_gain_db", 0.0)),
                low_mid_gain_db=float(params.get("low_mid_gain_db", 0.0)),
                high_mid_gain_db=float(params.get("high_mid_gain_db", 0.0)),
                high_shelf_gain_db=float(params.get("high_shelf_gain_db", 0.0)),
            )

        elif node.effect_type == DspEffectType.DE_ESSER:
            freq = float(params.get("frequency_hz", params.get("freq_hz", 6500.0)))
            thresh = float(params.get("threshold_db", -18.0))
            reduc = float(params.get("reduction_db", 6.0))
            samples = self.engine.apply_deesser(
                clip.samples,
                clip.sample_rate,
                threshold_db=thresh,
                reduction_db=reduc,
                freq_hz=freq,
            )
            return AudioClipData(samples=samples, sample_rate=clip.sample_rate)

        elif node.effect_type == DspEffectType.LEVELER_LIMITER:
            return self.engine.apply_leveler_and_limiter(
                clip,
                target_loudness_dbfs=float(params.get("target_loudness_dbfs", -16.0)),
                true_peak_limit_dbfs=float(params.get("true_peak_limit_dbfs", -1.0)),
            )

        elif node.effect_type == DspEffectType.REVERB_MATCH:
            return self.engine.apply_reverb_match(
                clip,
                room_size=float(params.get("room_size", 0.15)),
                wet_level=float(params.get("wet_level", 0.08)),
            )

        elif node.effect_type == DspEffectType.TIME_STRETCH:
            target_dur = float(params.get("target_duration_s", clip.duration_s))
            return self.engine.wsola_time_stretch(clip, target_duration_s=target_dur)

        elif node.effect_type == DspEffectType.PITCH_SHIFT:
            semitones = float(params.get("semitones", 0.0))
            return self.apply_pitch_shift(clip, semitones=semitones)

        return clip

    def apply_gain(self, clip: AudioClipData, gain_db: float) -> AudioClipData:
        """Applies linear gain factor calculated from decibels."""
        if math.isclose(gain_db, 0.0, abs_tol=1e-3):
            return clip
        factor = float(10.0 ** (gain_db / 20.0))
        processed = np.clip(clip.samples * factor, -1.0, 1.0)
        return AudioClipData(samples=processed, sample_rate=clip.sample_rate)

    def normalize_peak(
        self, clip: AudioClipData, target_peak_dbfs: float = -1.0
    ) -> AudioClipData:
        """Normalizes audio clip to target peak dBFS."""
        if clip.samples.size == 0:
            return clip
        peak = float(np.max(np.abs(clip.samples)))
        if peak < 1e-6:
            return clip
        target_linear = float(10.0 ** (target_peak_dbfs / 20.0))
        scale = target_linear / peak
        processed = np.clip(clip.samples * scale, -1.0, 1.0)
        return AudioClipData(samples=processed, sample_rate=clip.sample_rate)

    def apply_pitch_shift(
        self, clip: AudioClipData, semitones: float
    ) -> AudioClipData:
        """Resamples audio to shift pitch by specified semitones preserving length."""
        if math.isclose(semitones, 0.0, abs_tol=1e-3) or clip.samples.size == 0:
            return clip
        ratio = 2.0 ** (semitones / 12.0)
        orig_len = clip.samples.size
        # Resample
        new_len = max(1, int(orig_len / ratio))
        indices = np.linspace(0, orig_len - 1, new_len)
        shifted = np.interp(indices, np.arange(orig_len), clip.samples).astype(np.float32)
        # WSOLA stretch back to original duration
        temp_clip = AudioClipData(samples=shifted, sample_rate=clip.sample_rate)
        return self.engine.wsola_time_stretch(temp_clip, target_duration_s=clip.duration_s)

    def process_file(
        self, input_wav: Path | str, output_wav: Path | str, rack: EffectRack
    ) -> Path:
        """Reads a WAV file, applies the effect rack, and writes the output WAV."""
        in_path = Path(input_wav)
        out_path = Path(output_wav)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        clip = self.engine.load_wav(in_path)
        processed = self.process_clip(clip, rack)
        self.engine.save_wav(processed, out_path)
        return out_path


__all__ = [
    "DspChain",
]
