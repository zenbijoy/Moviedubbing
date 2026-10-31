"""Voice cloning profile management."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceCloneProfile:
    profile_id: str
    speaker_name: str
    reference_audio_paths: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)
    pitch_shift_semitones: float = 0.0
    formant_ratio: float = 1.0
    speaking_rate: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_embedding(self) -> bool:
        return len(self.embedding) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "speaker_name": self.speaker_name,
            "reference_audio_paths": self.reference_audio_paths,
            "embedding_dim": len(self.embedding),
            "pitch_shift_semitones": self.pitch_shift_semitones,
            "formant_ratio": self.formant_ratio,
            "speaking_rate": self.speaking_rate,
            "metadata": self.metadata,
        }


class VoiceCloneRegistry:
    def __init__(self) -> None:
        self.profiles: dict[str, VoiceCloneProfile] = {}

    def add(self, profile: VoiceCloneProfile) -> None:
        self.profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> VoiceCloneProfile | None:
        return self.profiles.get(profile_id)

    def remove(self, profile_id: str) -> None:
        self.profiles.pop(profile_id, None)

    def list_ids(self) -> list[str]:
        return sorted(self.profiles.keys())


__all__ = ["VoiceCloneProfile", "VoiceCloneRegistry"]
