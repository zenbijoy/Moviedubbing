"""
Character Voice Profile & Reference Quality Domain Models.

Manages dynamic reference banks per character (Neutral, Angry, Sad, Whisper, Shout)
and ranks candidate audio clips via comprehensive quality scoring.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.speaker_embedding import SpeakerEmbedding


class ReferenceQualityTier(StrEnum):
    EXCELLENT_REFERENCE = "excellent_reference"  # Score >= 90
    GOOD_REFERENCE = "good_reference"  # Score 80 - 89
    USABLE_WITH_WARNING = "usable_with_warning"  # Score 65 - 79
    POOR_REFERENCE = "poor_reference"  # Score 50 - 64
    REJECTED = "rejected"  # Score < 50


class ReferenceQualityReport(ContractModel):
    """Detailed audio quality evaluation report for a reference clip candidate."""

    sample_id: Identifier
    speech_duration_s: float = Field(ge=0.0)
    snr_db: float = Field(ge=0.0)
    overlapping_speech_score: float = Field(ge=0.0, le=1.0)
    background_music_score: float = Field(ge=0.0, le=1.0)
    reverb_score: float = Field(ge=0.0, le=1.0)
    phonetic_coverage: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=100.0)
    tier: ReferenceQualityTier = ReferenceQualityTier.GOOD_REFERENCE
    recommendation: str = Field(min_length=1)


class ReferenceSample(ContractModel):
    """Reference audio sample container."""

    sample_id: Identifier
    character_id: Identifier
    emotion_category: str = Field(
        default="neutral", max_length=32
    )  # "neutral", "angry", "sad", "whisper", "shout"
    audio_file_path: str = Field(min_length=1)
    duration_s: float = Field(gt=0.0)
    quality_report: ReferenceQualityReport
    embedding: SpeakerEmbedding | None = None


class ReferenceBank(ContractModel):
    """Dynamic reference bank per emotion category for a single character."""

    character_id: Identifier
    emotion_category: str = Field(default="neutral", max_length=32)
    references: list[ReferenceSample] = Field(default_factory=list)

    def get_best_reference(self) -> ReferenceSample | None:
        """Return highest scoring non-rejected reference sample."""
        valid = [
            r for r in self.references if r.quality_report.tier != ReferenceQualityTier.REJECTED
        ]
        if not valid:
            return None
        valid.sort(key=lambda r: r.quality_report.quality_score, reverse=True)
        return valid[0]


class ProfileVersionRecord(ContractModel):
    """Historical snapshot of a character voice profile version."""

    version: int = Field(ge=1)
    timestamp_iso: str = Field(min_length=1)
    change_summary: str = Field(default="")
    snapshot_json: str = Field(default="")


class CharacterVoiceProfile(ContractModel):
    """Full character voice profile containing multiple emotion reference banks and engine configs."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    profile_id: Identifier
    character_id: Identifier
    display_name: str = Field(min_length=1)
    consent_authorized: bool = False
    core_embedding: SpeakerEmbedding | None = None
    reference_banks: dict[str, ReferenceBank] = Field(
        default_factory=dict
    )  # "neutral", "angry", "sad", etc.

    # Engine & Consistency Attributes
    selected_engine: str = Field(default="edge_tts")
    model_version: str = Field(default="1.0.0")
    primary_language: str = Field(default="bn-BD")
    supported_accents: list[str] = Field(default_factory=lambda: ["standard"])
    default_voice_id: str = Field(default="")
    default_emotion: str = Field(default="neutral")
    default_pace: float = Field(default=1.0, ge=0.5, le=2.0)
    default_pitch_shift: float = Field(default=0.0, ge=-12.0, le=12.0)
    default_performance_style: str = Field(default="natural")
    authorized_reference_path: str = Field(default="")
    reference_audio_metadata: dict[str, Any] = Field(default_factory=dict)
    project_overrides: dict[str, Any] = Field(default_factory=dict)
    consent_notes: str = Field(default="")

    # Versioning & Update History
    version: int = Field(default=1, ge=1)
    history: list[ProfileVersionRecord] = Field(default_factory=list)

    def create_version_snapshot(self, change_summary: str = "") -> None:
        """Create a version snapshot and increment the version counter."""
        import json
        from datetime import UTC, datetime

        now_iso = datetime.now(UTC).isoformat()
        dump_dict = self.model_dump(exclude={"history"}, mode="json")
        snapshot = json.dumps(dump_dict)
        self.history.append(
            ProfileVersionRecord(
                version=self.version,
                timestamp_iso=now_iso,
                change_summary=change_summary,
                snapshot_json=snapshot,
            )
        )
        self.version += 1


__all__ = [
    "CharacterVoiceProfile",
    "ProfileVersionRecord",
    "ReferenceBank",
    "ReferenceQualityReport",
    "ReferenceQualityTier",
    "ReferenceSample",
]

