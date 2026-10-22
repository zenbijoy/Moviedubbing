"""
Character Voice Profile & Reference Quality Domain Models.

Manages dynamic reference banks per character (Neutral, Angry, Sad, Whisper, Shout)
and ranks candidate audio clips via comprehensive quality scoring.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

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


class CharacterVoiceProfile(ContractModel):
    """Full character voice profile containing multiple emotion reference banks."""

    profile_id: Identifier
    character_id: Identifier
    display_name: str = Field(min_length=1)
    consent_authorized: bool = False
    core_embedding: SpeakerEmbedding | None = None
    reference_banks: dict[str, ReferenceBank] = Field(
        default_factory=dict
    )  # "neutral", "angry", "sad", etc.


__all__ = [
    "CharacterVoiceProfile",
    "ReferenceBank",
    "ReferenceQualityReport",
    "ReferenceQualityTier",
    "ReferenceSample",
]
