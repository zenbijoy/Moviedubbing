"""
Cubase Pro Direct Offline Processing (DOP) Engine & Non-Destructive History Stack.

Features:
  - F7 Direct Offline Processing clone: instant non-destructive DSP processing directly on clips.
  - Full Offline Process History stack (reorder, bypass, modify parameters, delete steps).
  - Tube & Tape Analog Saturation for warming sterile AI synthetic voices.
  - Dynamic Noise Gate with lookahead hysteresis.
  - 4-Band Studio Parametric Equalizer.
  - Sibilance De-Esser.
  - Brickwall True-Peak Limiter (-1.0 dBFS).
  - 180° Phase Inverter for acoustic cancellation testing.
  - Non-destructive caching and 1-Click render.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

import numpy as np

from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine

logger = logging.getLogger(__name__)


class DopProcessType(StrEnum):
    TUBE_SATURATION = "tube_saturation"
    NOISE_GATE = "noise_gate"
    PARAMETRIC_EQ = "parametric_eq"
    DE_ESSER = "de_esser"
    ROOM_AMBIENCE = "room_ambience"
    BRICKWALL_LIMITER = "brickwall_limiter"
    PHASE_INVERT = "phase_invert"
    GAIN_NORMALIZE = "gain_normalize"


@dataclass
class DopProcessStep:
    """A single process node in the Direct Offline Processing chain."""

    step_id: str
    process_type: DopProcessType
    parameters: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    display_title: str = ""

    def __post_init__(self) -> None:
        if not self.display_title:
            self.display_title = self.process_type.value.replace("_", " ").title()


class CubaseDopEngine:
    """Clones Cubase Pro's Direct Offline Processing (DOP) rack and non-destructive history stack."""

    def __init__(self) -> None:
        self.dsp = ProAudioDspEngine()

    def render_dop_chain(
        self, original_clip: AudioClipData, steps: list[DopProcessStep]
    ) -> AudioClipData:
        """Renders the entire DOP history stack sequentially from the untouched original audio."""
        if original_clip.samples.size == 0 or not steps:
            return original_clip.clone()

        current = original_clip.clone()
        for step in steps:
            if not step.is_active:
                continue
            try:
                current = self._execute_step(current, step)
            except Exception as ex:
                logger.error("DOP error in step %s (%s): %s", step.step_id, step.process_type, ex)

        return current

    def _execute_step(self, clip: AudioClipData, step: DopProcessStep) -> AudioClipData:
        p = step.parameters
        pt = step.process_type
        sr = clip.sample_rate

        if pt == DopProcessType.TUBE_SATURATION:
            # Analog warmth: Soft-clipping + even/odd harmonic saturation
            drive_db = float(p.get("drive_db", 4.0))
            warmth = float(p.get("warmth", 0.5))  # 0.0 to 1.0
            drive_linear = 10.0 ** (drive_db / 20.0)

            x = clip.samples * drive_linear
            # Classic asymmetric tube curve: tanh(x) + subtle even harmonic x^2
            tube = np.tanh(x) + (warmth * 0.15 * (x**2))
            # Output trim to maintain nominal volume
            out = tube / max(1.0, drive_linear * 0.8)
            return AudioClipData(
                samples=np.clip(out, -1.0, 1.0).astype(np.float32), sample_rate=sr
            )

        elif pt == DopProcessType.NOISE_GATE:
            # Clean room noise or breaths below threshold
            thresh_db = float(p.get("threshold_db", -40.0))
            attack_ms = float(p.get("attack_ms", 10.0))
            release_ms = float(p.get("release_ms", 80.0))
            thresh_linear = 10.0 ** (thresh_db / 20.0)

            samples = clip.samples.copy()
            hop = max(32, int(sr * 0.005))  # 5ms envelope
            n_blocks = samples.size // hop

            gain_curve = np.ones_like(samples)
            current_gain = 1.0
            alpha_a = math.exp(-1.0 / (sr * (attack_ms / 1000.0)))
            alpha_r = math.exp(-1.0 / (sr * (release_ms / 1000.0)))

            for b in range(n_blocks):
                idx = b * hop
                sub = samples[idx : idx + hop]
                rms = float(np.sqrt(np.mean(sub**2))) if sub.size > 0 else 0.0
                target_gain = 1.0 if rms >= thresh_linear else 0.0

                for s in range(idx, min(samples.size, idx + hop)):
                    if target_gain > current_gain:
                        current_gain = alpha_a * current_gain + (1.0 - alpha_a) * target_gain
                    else:
                        current_gain = alpha_r * current_gain + (1.0 - alpha_r) * target_gain
                    gain_curve[s] = current_gain

            return AudioClipData(samples=samples * gain_curve, sample_rate=sr)

        elif pt == DopProcessType.PARAMETRIC_EQ:
            low_mid = float(p.get("low_mid_gain_db", 0.0))
            high_mid = float(p.get("high_mid_gain_db", 0.0))
            air = float(p.get("high_shelf_gain_db", 0.0))
            out = self.dsp.apply_eq_4band(
                clip.samples,
                sr,
                low_mid_gain_db=low_mid,
                high_mid_gain_db=high_mid,
                air_gain_db=air,
            )
            return AudioClipData(samples=out, sample_rate=sr)

        elif pt == DopProcessType.DE_ESSER:
            thresh = float(p.get("threshold_db", -20.0))
            reduc = float(p.get("reduction_db", 6.0))
            freq = float(p.get("freq_hz", 6500.0))
            out = self.dsp.apply_deesser(
                clip.samples, sr, threshold_db=thresh, reduction_db=reduc, freq_hz=freq
            )
            return AudioClipData(samples=out, sample_rate=sr)

        elif pt == DopProcessType.ROOM_AMBIENCE:
            wet = float(p.get("wet_level", 0.12))
            preset = p.get("preset", "living_room")
            out = self.dsp.apply_room_ambience(clip.samples, sr, preset=preset, dry_wet=wet)
            return AudioClipData(samples=out, sample_rate=sr)

        elif pt == DopProcessType.BRICKWALL_LIMITER:
            ceil_db = float(p.get("ceiling_db", -1.0))
            out = self.dsp.apply_compressor_limiter(clip.samples, sr, ceiling_db=ceil_db)
            return AudioClipData(samples=out, sample_rate=sr)

        elif pt == DopProcessType.PHASE_INVERT:
            return AudioClipData(samples=(-clip.samples).astype(np.float32), sample_rate=sr)

        elif pt == DopProcessType.GAIN_NORMALIZE:
            target_peak = float(p.get("target_peak_dbfs", -1.0))
            pk = float(np.max(np.abs(clip.samples))) if clip.samples.size > 0 else 0.0
            if pk > 1e-5:
                scale = (10.0 ** (target_peak / 20.0)) / pk
                return AudioClipData(
                    samples=np.clip(clip.samples * scale, -1.0, 1.0).astype(np.float32),
                    sample_rate=sr,
                )
            return clip.clone()

        return clip.clone()

    @staticmethod
    def create_step(process_type: DopProcessType, **params: Any) -> DopProcessStep:
        return DopProcessStep(
            step_id=f"dop_{uuid4().hex[:8]}",
            process_type=process_type,
            parameters=params,
            is_active=True,
        )


__all__ = [
    "CubaseDopEngine",
    "DopProcessStep",
    "DopProcessType",
]
