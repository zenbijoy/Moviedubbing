"""Voice take versioning, A/B preview management, and active master selection."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.base import UtcDatetime, utc_now

logger = logging.getLogger(__name__)

MAX_TAKES_PER_UTTERANCE = 10


class TakeStatus(StrEnum):
    GENERATED = "generated"
    SELECTED = "selected"  # Active A/B preview selection
    MASTER = "master"  # Final approved take for render queue
    REJECTED = "rejected"
    ARCHIVED = "archived"


class VoiceTake(ContractModel):
    """A single generated voice take with metadata for A/B comparison."""

    take_id: Identifier
    utterance_id: Identifier
    take_number: int = Field(ge=1)
    audio_path: str = Field(min_length=1)
    engine_kind: str = Field(min_length=1, max_length=64)
    seed: int = Field(ge=0)
    emotion_label: str = Field(default="neutral", max_length=64)
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    pace_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch_semitones: float = Field(default=0.0, ge=-12.0, le=12.0)
    duration_ms: int = Field(ge=0)
    sample_rate: int = Field(default=48_000, ge=8_000)
    status: TakeStatus = TakeStatus.GENERATED
    created_at: UtcDatetime = Field(default_factory=utc_now)
    notes: str = Field(default="", max_length=1_000)


class TakeManager:
    """
    Voice take version store with A/B preview switching and master selection.

    Guarantees:
      - Exactly one take per utterance can be MASTER at a time.
      - Exactly one take per utterance can be SELECTED (A/B preview) at a time.
      - Render queue always uses the MASTER take if set, otherwise SELECTED.
      - Takes are versioned and never deleted (only archived/rejected).
      - Raise ValueError if take limit is exceeded.
    """

    def __init__(self) -> None:
        # utterance_id -> list of VoiceTake (ordered by take_number)
        self._takes: dict[str, list[VoiceTake]] = {}

    def add_take(self, take: VoiceTake) -> None:
        """Register a new voice take. Enforces per-utterance take limit."""
        uid = take.utterance_id
        takes = self._takes.setdefault(uid, [])

        if any(t.take_id == take.take_id for t in takes):
            raise ValueError(f"take {take.take_id!r} already exists for utterance {uid!r}")

        if len(takes) >= MAX_TAKES_PER_UTTERANCE:
            raise ValueError(
                f"utterance {uid!r} already has {MAX_TAKES_PER_UTTERANCE} takes; "
                "archive or reject existing takes before adding more"
            )

        takes.append(take)
        logger.debug(
            "take_manager: added take %s (take #%d) for %s", take.take_id, take.take_number, uid
        )

    def select_for_preview(self, utterance_id: str, take_id: str) -> VoiceTake:
        """Mark a take as SELECTED for A/B preview (clears previous selection)."""
        return self._transition(utterance_id, take_id, TakeStatus.SELECTED)

    def set_master(self, utterance_id: str, take_id: str) -> VoiceTake:
        """
        Promote a take to MASTER for the render queue.
        Demotes any previously MASTER take back to GENERATED.
        """
        return self._transition(utterance_id, take_id, TakeStatus.MASTER)

    def reject_take(self, utterance_id: str, take_id: str) -> VoiceTake:
        """Mark a take as REJECTED."""
        return self._transition(utterance_id, take_id, TakeStatus.REJECTED)

    def archive_take(self, utterance_id: str, take_id: str) -> VoiceTake:
        """Move a take to ARCHIVED (not visible in normal A/B UI)."""
        return self._transition(utterance_id, take_id, TakeStatus.ARCHIVED)

    def render_take(self, utterance_id: str) -> VoiceTake | None:
        """
        Return the take that the render queue should use.
        Priority: MASTER > SELECTED > latest GENERATED.
        """
        takes = self._takes.get(utterance_id, [])
        active = [t for t in takes if t.status not in (TakeStatus.REJECTED, TakeStatus.ARCHIVED)]

        for status in (TakeStatus.MASTER, TakeStatus.SELECTED, TakeStatus.GENERATED):
            for take in reversed(active):  # latest first
                if take.status == status:
                    return take
        return None

    def list_takes(self, utterance_id: str) -> list[VoiceTake]:
        """Return all takes for an utterance ordered by take_number."""
        return sorted(self._takes.get(utterance_id, []), key=lambda t: t.take_number)

    def get_take(self, utterance_id: str, take_id: str) -> VoiceTake | None:
        """Retrieve a specific take by ID."""
        for take in self._takes.get(utterance_id, []):
            if take.take_id == take_id:
                return take
        return None

    def take_count(self, utterance_id: str) -> int:
        return len(self._takes.get(utterance_id, []))

    def _transition(
        self,
        utterance_id: str,
        take_id: str,
        new_status: TakeStatus,
    ) -> VoiceTake:
        """Apply a status transition, enforcing single-MASTER / single-SELECTED invariants."""
        takes = self._takes.get(utterance_id)
        if not takes:
            raise KeyError(f"utterance {utterance_id!r} has no takes")

        target_idx = next((i for i, t in enumerate(takes) if t.take_id == take_id), None)
        if target_idx is None:
            raise KeyError(f"take {take_id!r} not found for utterance {utterance_id!r}")

        target = takes[target_idx]
        if target.status in (TakeStatus.REJECTED, TakeStatus.ARCHIVED):
            raise ValueError(f"cannot promote take {take_id!r} with status {target.status.value!r}")

        # Clear conflicting exclusive statuses
        exclusive = {TakeStatus.MASTER, TakeStatus.SELECTED}
        if new_status in exclusive:
            for i, t in enumerate(takes):
                if t.status == new_status and t.take_id != take_id:
                    takes[i] = t.model_copy(update={"status": TakeStatus.GENERATED})
                    logger.debug("take_manager: demoted %s from %s", t.take_id, new_status.value)

        updated = target.model_copy(update={"status": new_status})
        takes[target_idx] = updated
        logger.info(
            "take_manager: %s -> %s for utterance %s",
            take_id,
            new_status.value,
            utterance_id,
        )
        return updated


__all__ = [
    "MAX_TAKES_PER_UTTERANCE",
    "TakeManager",
    "TakeStatus",
    "VoiceTake",
]
