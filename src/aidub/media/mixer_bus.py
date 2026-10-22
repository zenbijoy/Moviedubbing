"""
Broadcast subgroup bus routing & sidechain ducking engine.

Features:
  - Subgroup Buses: DIALOGUE_BUS, ME_BUS (Music & Effects), MASTER_BUS.
  - Sidechain Ducking: Automatically attenuates Music (A3) & Ambience (A4/A5)
    when Dialogue (A1/A2) is active, with configurable threshold, ducking depth,
    attack, release, and hold time.
"""

from __future__ import annotations

import logging
import math
from enum import StrEnum

import numpy as np
from pydantic import Field

from aidub.contracts.base import ContractModel
from aidub.ui.timeline.model import TrackId

logger = logging.getLogger(__name__)


class BusKind(StrEnum):
    DIALOGUE_BUS = "dialogue_bus"
    ME_BUS = "me_bus"
    MASTER_BUS = "master_bus"


class DuckingSettings(ContractModel):
    """Configuration for automatic sidechain music/ambience ducking."""

    enabled: bool = True
    threshold_dbfs: float = Field(default=-30.0, ge=-60.0, le=0.0)
    duck_reduction_db: float = Field(default=12.0, ge=0.0, le=36.0)
    attack_ms: float = Field(default=15.0, ge=1.0, le=200.0)
    release_ms: float = Field(default=300.0, ge=10.0, le=2000.0)
    hold_ms: float = Field(default=100.0, ge=0.0, le=1000.0)


class SidechainDucker:
    """
    Computes smooth gain reduction curves for ducking music/effects under dialogue.
    """

    def __init__(self, settings: DuckingSettings | None = None) -> None:
        self.settings = settings or DuckingSettings()
        self._current_reduction_db: float = 0.0

    def compute_ducking_gain(self, dialogue_peak_dbfs: float) -> float:
        """
        Calculate ducking linear gain factor (0.0 to 1.0) based on dialogue level.
        """
        s = self.settings
        if not s.enabled:
            return 1.0

        if dialogue_peak_dbfs > s.threshold_dbfs:
            # Dialogue active: apply reduction
            target_reduction = s.duck_reduction_db
            self._current_reduction_db = max(self._current_reduction_db, target_reduction)
        else:
            # Release reduction with exponential decay factor
            decay = math.exp(-30.0 / max(10.0, s.release_ms))
            self._current_reduction_db = max(0.0, self._current_reduction_db * decay)

        linear_gain = 10.0 ** (-self._current_reduction_db / 20.0)
        return float(round(linear_gain, 4))

    def duck_buffers(
        self,
        music_samples: np.ndarray,
        vocal_samples: np.ndarray,
        sample_rate: int = 44100,
    ) -> np.ndarray:
        """
        Vectorized audio buffer ducking applying exponential attack/release envelope.
        """
        s = self.settings
        if not s.enabled or music_samples.size == 0 or vocal_samples.size == 0:
            return music_samples.copy()

        from aidub.media.dsp_engine import VectorizedDspEngine

        dsp = VectorizedDspEngine()
        return dsp.process_dynamic_ducking(
            music_samples=music_samples,
            vocal_samples=vocal_samples,
            threshold_db=s.threshold_dbfs,
            duck_db=s.duck_reduction_db,
            attack_ms=s.attack_ms,
            release_ms=s.release_ms,
            sample_rate=sample_rate,
        )


class MasterBusRouter(ContractModel):
    """Subgroup bus configuration mapping tracks to subgroup output buses."""

    dialogue_tracks: list[TrackId] = Field(default_factory=lambda: [TrackId.A1, TrackId.A2])
    me_tracks: list[TrackId] = Field(default_factory=lambda: [TrackId.A3, TrackId.A4, TrackId.A5])
    ducking: DuckingSettings = Field(default_factory=DuckingSettings)

    def route_track(self, track_id: TrackId) -> BusKind:
        """Resolve subgroup bus destination for a given audio track."""
        if track_id in self.dialogue_tracks:
            return BusKind.DIALOGUE_BUS
        if track_id in self.me_tracks:
            return BusKind.ME_BUS
        return BusKind.MASTER_BUS


__all__ = [
    "BusKind",
    "DuckingSettings",
    "MasterBusRouter",
    "SidechainDucker",
]
