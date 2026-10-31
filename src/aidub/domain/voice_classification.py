"""
Domain contracts for Voice and Character Classification.

Supports multi-speaker diarization clustering, confidence attribution,
character roster assignment, and audit-logged manual reassignments.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GenderIdentity(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    CHILD = "child"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Speaker classification decision for a single dialogue cue."""

    cue_id: str
    predicted_speaker: str
    confidence: float
    is_uncertain: bool = False
    suggested_alternatives: list[tuple[str, float]] = field(default_factory=list)
    face_track_id: str | None = None
    manual_override_speaker: str | None = None
    override_reason: str = ""
    updated_at_s: float = field(default_factory=time.time)

    @property
    def effective_speaker(self) -> str:
        """Returns manual override if specified, otherwise the predicted speaker."""
        return self.manual_override_speaker or self.predicted_speaker


@dataclass
class DiarizationCluster:
    """Group of dialogue segments assigned to the same speaker embedding."""

    cluster_id: str  # e.g., "SPEAKER_00"
    cue_ids: list[str] = field(default_factory=list)
    total_duration_s: float = 0.0
    average_confidence: float = 1.0
    gender_estimate: GenderIdentity = GenderIdentity.UNKNOWN
    assigned_character_id: str | None = None
    assigned_voice_id: str = "bn-BD-PradeepNeural"
    color_hex: str = "#38BDF8"

    @property
    def line_count(self) -> int:
        return len(self.cue_ids)


@dataclass
class SpeakerMergeOperation:
    """Command specification for merging two diarization clusters."""

    source_cluster_id: str  # To be merged and removed
    target_cluster_id: str  # Receiving cluster
    affected_cue_ids: list[str] = field(default_factory=list)
    performed_by: str = "editor"
    timestamp_s: float = field(default_factory=time.time)


@dataclass
class CharacterRosterEntry:
    """Character definition in the production cast roster."""

    character_id: str
    name: str
    actor_name: str = ""
    assigned_voice_id: str = "bn-BD-PradeepNeural"
    gender: GenderIdentity = GenderIdentity.UNKNOWN
    consent_granted: bool = True
    notes: str = ""
    color_hex: str = "#38BDF8"


# Alias for compatibility with spec
CharacterVoiceProfile = CharacterRosterEntry


__all__ = [
    "CharacterRosterEntry",
    "CharacterVoiceProfile",
    "ClassificationResult",
    "DiarizationCluster",
    "GenderIdentity",
    "SpeakerMergeOperation",
]
