"""
Character Cast Registry and Voice Consent Audit Service.

Manages character roster, assigned voices, actor metadata, and rights audit logs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aidub.domain.voice_classification import CharacterVoiceProfile, GenderIdentity

logger = logging.getLogger(__name__)


@dataclass
class CastAuditLogEntry:
    """Audit log entry for cast alterations."""

    entry_id: str
    action: str
    character_id: str
    details: str
    timestamp_s: float = field(default_factory=time.time)


class CharacterRegistry:
    """Production cast roster repository with consent verification."""

    def __init__(self) -> None:
        self._characters: dict[str, CharacterVoiceProfile] = {}
        self._audit_log: list[CastAuditLogEntry] = []

    def register_character(
        self,
        character_id: str,
        name: str,
        actor_name: str = "",
        assigned_voice_id: str = "bn-BD-PradeepNeural",
        gender: GenderIdentity = GenderIdentity.UNKNOWN,
        consent_granted: bool = True,
        notes: str = "",
        color_hex: str = "#38BDF8",
    ) -> CharacterVoiceProfile:
        char = CharacterVoiceProfile(
            character_id=character_id,
            name=name,
            actor_name=actor_name,
            assigned_voice_id=assigned_voice_id,
            gender=gender,
            consent_granted=consent_granted,
            notes=notes,
            color_hex=color_hex,
        )
        self._characters[character_id] = char
        self._log_audit("REGISTER", character_id, f"Registered character '{name}' (voice={assigned_voice_id})")
        return char

    def get_character(self, character_id: str) -> CharacterVoiceProfile | None:
        return self._characters.get(character_id)

    def list_characters(self) -> list[CharacterVoiceProfile]:
        return list(self._characters.values())

    def update_voice_assignment(self, character_id: str, new_voice_id: str) -> bool:
        char = self.get_character(character_id)
        if not char:
            return False
        old_voice = char.assigned_voice_id
        char.assigned_voice_id = new_voice_id
        self._log_audit("VOICE_UPDATE", character_id, f"Changed voice from {old_voice} to {new_voice_id}")
        return True

    def set_consent_status(self, character_id: str, consent_granted: bool) -> bool:
        char = self.get_character(character_id)
        if not char:
            return False
        char.consent_granted = consent_granted
        self._log_audit("CONSENT_UPDATE", character_id, f"Set consent to {consent_granted}")
        return True

    def get_audit_log(self) -> list[CastAuditLogEntry]:
        return list(self._audit_log)

    def _log_audit(self, action: str, character_id: str, details: str) -> None:
        import uuid
        entry = CastAuditLogEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:8]}",
            action=action,
            character_id=character_id,
            details=details,
        )
        self._audit_log.append(entry)


__all__ = [
    "CastAuditLogEntry",
    "CharacterRegistry",
]
