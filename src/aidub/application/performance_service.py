"""Utterance performance and prosody editing service."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.utterance import Emotion, Prosody, Utterance, UtteranceStatus

logger = logging.getLogger(__name__)


class VocalizationKind(StrEnum):
    """Non-verbal vocalizations injected alongside or replacing dialogue."""

    BREATH = "breath"
    SIGH = "sigh"
    GASP = "gasp"
    LAUGH = "laugh"
    CRY = "cry"
    GRUNT = "grunt"
    WHISTLE = "whistle"


class VocalizationMarker(ContractModel):
    """A non-verbal vocalization annotation on an utterance."""

    utterance_id: Identifier
    kind: VocalizationKind
    position_ms: int = Field(ge=0, description="Offset from utterance start in ms")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class PerformanceEdit(ContractModel):
    """An atomic performance parameter override for a single utterance."""

    utterance_id: Identifier
    emotion_label: str = Field(default="", max_length=64)
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    pace_rate: float = Field(default=1.0, gt=0.0, le=4.0)
    pitch_semitones: float = Field(default=0.0, ge=-24.0, le=24.0)
    energy: float = Field(default=1.0, ge=0.0, le=4.0)


class PerformanceService:
    """
    Applies line-level performance overrides to Utterance domain objects.

    Handles:
      - Emotion label + intensity (neutral, angry, sad, fear, whisper, shout, joy)
      - Pace multiplier, pitch shift, energy contour
      - Non-verbal vocalization markers (stored alongside utterance)
    """

    def __init__(self) -> None:
        self._vocalizations: dict[str, list[VocalizationMarker]] = {}

    def apply_performance(
        self,
        utterance: Utterance,
        edit: PerformanceEdit,
    ) -> Utterance:
        """
        Apply a PerformanceEdit to an Utterance and return the updated copy.

        Raises ValueError if the utterance is LOCKED.
        """
        if utterance.status == UtteranceStatus.LOCKED:
            raise ValueError(f"utterance {utterance.utterance_id!r} is LOCKED and cannot be edited")
        if edit.utterance_id != utterance.utterance_id:
            raise ValueError(
                f"edit targets {edit.utterance_id!r} but utterance is {utterance.utterance_id!r}"
            )

        emotion = None
        if edit.emotion_label:
            emotion = Emotion(
                label=edit.emotion_label,
                intensity=edit.emotion_intensity,
            )

        prosody = Prosody(
            rate=edit.pace_rate,
            pitch_semitones=edit.pitch_semitones,
            energy=edit.energy,
        )

        updated = utterance.model_copy(
            update={
                "emotion": emotion,
                "prosody": prosody,
                "status": UtteranceStatus.DRAFT,
                "revision": utterance.revision + 1,
            }
        )

        logger.debug(
            "performance_service: %s emotion=%s intensity=%.2f rate=%.2f pitch=%.2f energy=%.2f",
            utterance.utterance_id,
            edit.emotion_label or "none",
            edit.emotion_intensity,
            edit.pace_rate,
            edit.pitch_semitones,
            edit.energy,
        )
        return updated

    def add_vocalization(self, marker: VocalizationMarker) -> None:
        """Register a non-verbal vocalization marker for an utterance."""
        uid = marker.utterance_id
        if uid not in self._vocalizations:
            self._vocalizations[uid] = []
        self._vocalizations[uid].append(marker)

    def get_vocalizations(self, utterance_id: str) -> list[VocalizationMarker]:
        """Return all vocalization markers for an utterance, ordered by position."""
        markers = self._vocalizations.get(utterance_id, [])
        return sorted(markers, key=lambda m: m.position_ms)

    def reset_performance(self, utterance: Utterance) -> Utterance:
        """Reset emotion and prosody to neutral defaults."""
        return utterance.model_copy(
            update={
                "emotion": None,
                "prosody": None,
                "revision": utterance.revision + 1,
            }
        )

    def build_synthesis_overrides(self, utterance: Utterance) -> dict[str, Any]:
        """
        Serialize current performance parameters into a synthesis payload dict.
        Used by TTS workers to apply all performance overrides.
        """
        overrides: dict[str, Any] = {}
        if utterance.emotion is not None:
            overrides["emotion"] = utterance.emotion.label
            overrides["emotion_intensity"] = utterance.emotion.intensity
        if utterance.prosody is not None:
            overrides["pace_multiplier"] = utterance.prosody.rate
            overrides["pitch_shift_semitones"] = utterance.prosody.pitch_semitones
            overrides["energy"] = utterance.prosody.energy
        vocs = self.get_vocalizations(utterance.utterance_id)
        if vocs:
            overrides["vocalizations"] = [v.model_dump(mode="json") for v in vocs]
        return overrides


__all__ = [
    "PerformanceEdit",
    "PerformanceService",
    "VocalizationKind",
    "VocalizationMarker",
]
