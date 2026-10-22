"""
Cross-Scene Voice Profile Persistence Service.

Re-identifies speakers and maintains character voice consistency across multiple movie reels.
"""

from __future__ import annotations

import logging

from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile

logger = logging.getLogger(__name__)


class CrossSceneVoicePersistence:
    """
    Maintains persistent voice profile mappings across multiple reels/scenes.
    """

    def __init__(self) -> None:
        self.persistent_profiles: dict[str, CharacterVoiceProfile] = {}

    def register_profile(self, profile: CharacterVoiceProfile) -> None:
        """
        Store profile in global project memory.
        """
        self.persistent_profiles[profile.character_id] = profile
        logger.info(
            "cross_scene_persistence: registered voice profile for %s", profile.character_id
        )

    def find_matching_profile(self, character_id: str) -> CharacterVoiceProfile | None:
        """
        Retrieve existing profile for character.
        """
        return self.persistent_profiles.get(Identifier(character_id))


__all__ = [
    "CrossSceneVoicePersistence",
]
