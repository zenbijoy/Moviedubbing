"""
Non-destructive per-utterance audio DSP processing chain.

Chain steps (applied in order):
  1. Noise Gate / De-noise
  2. 4-band parametric EQ
  3. Dynamic compressor
  4. De-esser
  5. Spatial panning

All parameters are non-destructive — they describe the processing to
apply to the audio artifact; actual DSP execution is performed by the
audio render worker (FFmpeg filter_complex or native scipy pipeline).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


# ── Band EQ ──────────────────────────────────────────────────────────────────


class EqBand(ContractModel):
    """A single parametric EQ band."""

    frequency_hz: float = Field(ge=20.0, le=20_000.0)
    gain_db: float = Field(ge=-24.0, le=24.0)
    q_factor: float = Field(default=1.0, ge=0.1, le=20.0)


class ParametricEq(ContractModel):
    """4-band corrective parametric EQ."""

    bands: list[EqBand] = Field(default_factory=list, max_length=4)
    enabled: bool = True


# ── Noise Gate ────────────────────────────────────────────────────────────────


class NoiseGate(ContractModel):
    """Noise gate / de-noise parameters."""

    threshold_db: float = Field(default=-40.0, ge=-80.0, le=0.0)
    attack_ms: float = Field(default=5.0, ge=0.1, le=100.0)
    release_ms: float = Field(default=50.0, ge=1.0, le=1_000.0)
    enabled: bool = True


# ── Compressor ───────────────────────────────────────────────────────────────


class Compressor(ContractModel):
    """Dynamic compressor parameters."""

    threshold_db: float = Field(default=-18.0, ge=-60.0, le=0.0)
    ratio: float = Field(default=3.0, ge=1.0, le=20.0)
    attack_ms: float = Field(default=10.0, ge=0.1, le=200.0)
    release_ms: float = Field(default=100.0, ge=5.0, le=2_000.0)
    makeup_gain_db: float = Field(default=0.0, ge=-12.0, le=24.0)
    enabled: bool = True


# ── De-esser ─────────────────────────────────────────────────────────────────


class Deesser(ContractModel):
    """De-esser targeting sibilant frequencies."""

    frequency_hz: float = Field(default=6_000.0, ge=2_000.0, le=16_000.0)
    threshold_db: float = Field(default=-12.0, ge=-40.0, le=0.0)
    reduction_db: float = Field(default=6.0, ge=0.0, le=20.0)
    enabled: bool = True


# ── Spatial Pan ───────────────────────────────────────────────────────────────


class SpatialPan(ContractModel):
    """Stereo/surround panning parameters (-1.0=hard left, 0=center, +1.0=hard right)."""

    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    width: float = Field(default=1.0, ge=0.0, le=2.0)
    enabled: bool = True


# ── DSP Chain Presets ─────────────────────────────────────────────────────────


class DspPreset(StrEnum):
    FLAT = "flat"
    DIALOGUE_CLEAN = "dialogue_clean"
    DIALOGUE_WARM = "dialogue_warm"
    BROADCAST = "broadcast"


_PRESETS: dict[DspPreset, dict[str, Any]] = {
    DspPreset.FLAT: {},
    DspPreset.DIALOGUE_CLEAN: {
        "noise_gate": {
            "threshold_db": -42.0,
            "attack_ms": 3.0,
            "release_ms": 40.0,
            "enabled": True,
        },
        "eq": {
            "bands": [
                {"frequency_hz": 80.0, "gain_db": -6.0, "q_factor": 0.7},
                {"frequency_hz": 200.0, "gain_db": -2.0, "q_factor": 1.0},
                {"frequency_hz": 3_000.0, "gain_db": 2.0, "q_factor": 1.5},
                {"frequency_hz": 10_000.0, "gain_db": 1.5, "q_factor": 0.9},
            ],
            "enabled": True,
        },
        "compressor": {
            "threshold_db": -20.0,
            "ratio": 3.5,
            "attack_ms": 8.0,
            "release_ms": 120.0,
            "makeup_gain_db": 2.0,
            "enabled": True,
        },
        "deesser": {
            "frequency_hz": 6_500.0,
            "threshold_db": -14.0,
            "reduction_db": 5.0,
            "enabled": True,
        },
    },
    DspPreset.BROADCAST: {
        "noise_gate": {
            "threshold_db": -38.0,
            "attack_ms": 2.0,
            "release_ms": 30.0,
            "enabled": True,
        },
        "eq": {
            "bands": [
                {"frequency_hz": 100.0, "gain_db": -4.0, "q_factor": 0.7},
                {"frequency_hz": 300.0, "gain_db": -1.5, "q_factor": 1.0},
                {"frequency_hz": 2_500.0, "gain_db": 3.0, "q_factor": 1.2},
                {"frequency_hz": 8_000.0, "gain_db": 2.0, "q_factor": 0.9},
            ],
            "enabled": True,
        },
        "compressor": {
            "threshold_db": -16.0,
            "ratio": 4.0,
            "attack_ms": 5.0,
            "release_ms": 80.0,
            "makeup_gain_db": 3.0,
            "enabled": True,
        },
        "deesser": {
            "frequency_hz": 7_000.0,
            "threshold_db": -10.0,
            "reduction_db": 7.0,
            "enabled": True,
        },
    },
}


# ── Main Chain ────────────────────────────────────────────────────────────────


class AudioDspChain(ContractModel):
    """
    Non-destructive per-utterance audio DSP processing chain descriptor.

    Stores all parameters needed to reproduce the processing on any render.
    Actual DSP is executed by the render worker, not this class.
    """

    utterance_id: Identifier
    noise_gate: NoiseGate = Field(default_factory=NoiseGate)
    eq: ParametricEq = Field(default_factory=ParametricEq)
    compressor: Compressor = Field(default_factory=Compressor)
    deesser: Deesser = Field(default_factory=Deesser)
    pan: SpatialPan = Field(default_factory=SpatialPan)
    output_gain_db: float = Field(default=0.0, ge=-24.0, le=24.0)

    @classmethod
    def from_preset(cls, utterance_id: str, preset: DspPreset) -> AudioDspChain:
        """Create a chain from a named preset."""
        preset_data = _PRESETS.get(preset, {})
        kwargs: dict[str, Any] = {"utterance_id": Identifier(utterance_id)}
        if "noise_gate" in preset_data:
            kwargs["noise_gate"] = NoiseGate.model_validate(preset_data["noise_gate"])
        if "eq" in preset_data:
            kwargs["eq"] = ParametricEq.model_validate(preset_data["eq"])
        if "compressor" in preset_data:
            kwargs["compressor"] = Compressor.model_validate(preset_data["compressor"])
        if "deesser" in preset_data:
            kwargs["deesser"] = Deesser.model_validate(preset_data["deesser"])
        return cls(**kwargs)

    def to_ffmpeg_filter(self) -> str:
        """
        Generate an FFmpeg audio filter_complex string from the chain parameters.
        Only enabled stages are included.
        """
        filters: list[str] = []

        if self.noise_gate.enabled:
            filters.append(
                f"agate=threshold={_db_to_linear(self.noise_gate.threshold_db):.6f}"
                f":attack={self.noise_gate.attack_ms}"
                f":release={self.noise_gate.release_ms}"
            )

        if self.eq.enabled and self.eq.bands:
            for band in self.eq.bands:
                filters.append(
                    f"equalizer=f={band.frequency_hz:.1f}"
                    f":width_type=o:width={band.q_factor:.2f}"
                    f":g={band.gain_db:.2f}"
                )

        if self.compressor.enabled:
            filters.append(
                f"acompressor=threshold={_db_to_linear(self.compressor.threshold_db):.6f}"
                f":ratio={self.compressor.ratio:.1f}"
                f":attack={self.compressor.attack_ms:.1f}"
                f":release={self.compressor.release_ms:.1f}"
                f":makeup={_db_to_linear(self.compressor.makeup_gain_db):.6f}"
            )

        if self.deesser.enabled:
            filters.append(
                f"highpass=f={self.deesser.frequency_hz:.0f},volume={_db_to_linear(self.deesser.reduction_db * -1):.6f}"
            )

        if self.pan.enabled and abs(self.pan.pan) > 0.01:
            l_gain = max(0.0, 1.0 - self.pan.pan)
            r_gain = max(0.0, 1.0 + self.pan.pan)
            filters.append(f"pan=stereo|c0={l_gain:.4f}*c0|c1={r_gain:.4f}*c1")

        if self.output_gain_db != 0.0:
            filters.append(f"volume={_db_to_linear(self.output_gain_db):.6f}")

        return ",".join(filters) if filters else "anull"


def _db_to_linear(db: float) -> float:
    return float(10.0 ** (db / 20.0))


__all__ = [
    "AudioDspChain",
    "Compressor",
    "Deesser",
    "DspPreset",
    "EqBand",
    "NoiseGate",
    "ParametricEq",
    "SpatialPan",
]
