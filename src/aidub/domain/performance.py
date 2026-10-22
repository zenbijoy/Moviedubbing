"""
Tripartite Voice Synthesis Domain Models.

Decouples voice synthesis into 3 distinct abstractions:
  1. Voice Identity (WHO is speaking: timbre, embedding, formants, age/accent metadata)
  2. Performance Intent (HOW they are speaking: continuous emotion, intensity, pitch trajectory, pauses)
  3. Linguistic Content (WHAT they are saying: text, language, phonemes, timing constraints)
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.speaker_embedding import SpeakerEmbedding


class VoiceIdentity(ContractModel):
    """Vocal timbre and identity specification."""

    character_id: Identifier
    profile_id: Identifier
    embedding: SpeakerEmbedding | None = None
    timbre_characteristics: str = Field(default="natural", max_length=64)
    pitch_offset_semitones: float = Field(default=0.0, ge=-12.0, le=12.0)
    accent_code: str = Field(default="standard", max_length=32)


class PerformanceIntent(ContractModel):
    """Emotional and prosodic performance specification."""

    primary_emotion: str = Field(default="neutral", max_length=32)
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)  # Positive vs Negative
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)  # Calm vs Excited
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)  # Submissive vs Dominant
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    energy_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    pause_locations_ms: list[int] = Field(default_factory=list)


class LinguisticContent(ContractModel):
    """Text and phonetic content specification."""

    text: str = Field(min_length=1)
    target_language_code: str = Field(default="en-US", max_length=16)
    phonemes: str = Field(default="", max_length=256)
    pronunciation_overrides: dict[str, str] = Field(default_factory=dict)
    target_duration_ms: int | None = None


class SynthesisRequest(ContractModel):
    """Complete, fully decoupled voice synthesis request payload."""

    request_id: Identifier
    voice_identity: VoiceIdentity
    performance_intent: PerformanceIntent
    linguistic_content: LinguisticContent
    allow_zero_shot: bool = True
    timing_strictness: float = Field(default=0.8, ge=0.0, le=1.0)


__all__ = [
    "LinguisticContent",
    "PerformanceIntent",
    "SynthesisRequest",
    "VoiceIdentity",
]
