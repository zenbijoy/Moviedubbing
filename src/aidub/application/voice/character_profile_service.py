"""
Cinematic Character Voice Consistency & Lifecycle Service (Phase 3).

Maintains persistent Character Voice Profiles across multiple reels and scenes:
  - Stable character IDs, authorized reference audio paths, and engine settings.
  - Tracking dialogue audio takes associated with character profiles.
  - Audio invalidation impact analysis: warns before changes invalidate existing dialogue.
  - Cross-scene voice similarity comparison via acoustic spectral analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidub.domain.voice_profile import CharacterVoiceProfile
from aidub.media.voice_dsp import measure_acoustic_similarity

logger = logging.getLogger(__name__)


@dataclass
class DialogueTakeRecord:
    """Record of a synthesized dialogue take associated with a character."""

    utterance_id: str
    character_id: str
    scene_id: str
    audio_path: str
    engine_kind: str
    voice_id: str
    reference_path: str
    is_stale: bool = False
    previous_audio_path: str = ""
    version: int = 1
    profile_version: int = 1


class CharacterProfileService:
    """
    Manages persistent character profiles, cross-scene consistency,
    and dialogue audio take invalidation.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self._profiles: dict[str, CharacterVoiceProfile] = {}
        self._takes: dict[str, DialogueTakeRecord] = {}  # utterance_id -> DialogueTakeRecord
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def register_profile(self, profile: CharacterVoiceProfile) -> None:
        """Register or update a character voice profile."""
        cid = str(profile.character_id)
        self._profiles[cid] = profile
        logger.info("character_profile_service: registered profile for character '%s'", cid)
        if self.storage_dir:
            self._save_to_disk(profile)

    def get_profile(self, character_id: str) -> CharacterVoiceProfile | None:
        """Look up profile by character ID."""
        return self._profiles.get(str(character_id))

    def list_profiles(self) -> list[CharacterVoiceProfile]:
        """Return all registered character voice profiles."""
        return list(self._profiles.values())

    def remove_profile(self, character_id: str) -> bool:
        """Delete character voice profile and clean storage."""
        cid = str(character_id)
        if cid in self._profiles:
            del self._profiles[cid]
            if self.storage_dir:
                prof_file = self.storage_dir / f"{cid}.json"
                prof_file.unlink(missing_ok=True)
            return True
        return False

    def link_take(
        self,
        character_id: str,
        utterance_id: str,
        scene_id: str,
        audio_path: str,
        engine_kind: str,
        voice_id: str = "",
        reference_path: str = "",
        profile_version: int = 1,
    ) -> None:
        """Associate a synthesized dialogue take with a character profile."""
        self._takes[utterance_id] = DialogueTakeRecord(
            utterance_id=utterance_id,
            character_id=str(character_id),
            scene_id=scene_id,
            audio_path=audio_path,
            engine_kind=engine_kind,
            voice_id=voice_id,
            reference_path=reference_path,
            is_stale=False,
            previous_audio_path="",
            version=1,
            profile_version=profile_version,
        )

    def get_character_takes(self, character_id: str) -> list[DialogueTakeRecord]:
        """Return all dialogue takes synthesized for a character across scenes."""
        cid = str(character_id)
        return [t for t in self._takes.values() if t.character_id == cid]

    def atomic_replace_take(
        self,
        utterance_id: str,
        new_audio_path: str,
        new_engine: str = "",
        new_voice_id: str = "",
        profile_version: int = 1,
    ) -> bool:
        """
        Atomically replace an existing dialogue take audio file.
        Preserves existing audio in previous_audio_path until replacement succeeds.
        Returns True if replacement succeeded, False if new audio is missing/empty.
        """
        take = self._takes.get(utterance_id)
        if not take:
            return False

        path_obj = Path(new_audio_path)
        if not path_obj.exists() or not path_obj.is_file() or path_obj.stat().st_size == 0:
            logger.warning(
                "atomic_replace_take: replacement audio '%s' is missing or zero-sized. "
                "Retaining original take at '%s'.",
                new_audio_path,
                take.audio_path,
            )
            return False

        take.previous_audio_path = take.audio_path
        take.audio_path = str(path_obj)
        take.version += 1
        take.profile_version = profile_version
        take.is_stale = False
        if new_engine:
            take.engine_kind = new_engine
        if new_voice_id:
            take.voice_id = new_voice_id

        logger.info(
            "atomic_replace_take: successfully updated utterance '%s' to version %d (audio: %s)",
            utterance_id,
            take.version,
            take.audio_path,
        )
        return True

    def rollback_take(self, utterance_id: str) -> bool:
        """Roll back take to previous audio if available."""
        take = self._takes.get(utterance_id)
        if not take or not take.previous_audio_path:
            return False
        prev_path = Path(take.previous_audio_path)
        if not prev_path.exists() or prev_path.stat().st_size == 0:
            return False

        temp = take.audio_path
        take.audio_path = take.previous_audio_path
        take.previous_audio_path = temp
        take.is_stale = True
        return True

    def get_affected_takes(self, character_id: str) -> list[DialogueTakeRecord]:
        """Return all dialogue takes for character marked stale or needing update."""
        cid = str(character_id)
        return [t for t in self._takes.values() if t.character_id == cid and t.is_stale]

    def update_profile(
        self,
        character_id: str,
        updates: dict[str, Any],
        change_summary: str = "",
    ) -> tuple[CharacterVoiceProfile | None, list[str]]:
        """
        Update a character voice profile with version history snapshotting
        and selective invalidation of affected dialogue takes.

        Returns (updated_profile, affected_utterance_ids).
        """
        profile = self.get_profile(character_id)
        if not profile:
            return None, []

        new_engine = updates.get("selected_engine", profile.selected_engine)
        new_voice_id = updates.get("default_voice_id", profile.default_voice_id)
        new_ref = updates.get("authorized_reference_path", profile.authorized_reference_path)

        invalidates, affected_ids = self.check_invalidation_impact(
            character_id=character_id,
            new_engine=new_engine,
            new_voice_id=new_voice_id,
            new_reference_path=new_ref,
        )

        # Snapshot current version before updating
        profile.create_version_snapshot(change_summary or f"Updated {', '.join(updates.keys())}")

        # Apply updates
        for key, val in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, val)

        if invalidates:
            self.mark_takes_stale(character_id)

        self.register_profile(profile)
        return profile, affected_ids

    def regenerate_take(
        self,
        utterance_id: str,
        synthesize_fn: Any,
    ) -> bool:
        """
        Regenerate a single dialogue take using a synthesis callback.
        Preserves existing audio if synthesis fails.
        """
        take = self._takes.get(utterance_id)
        if not take:
            return False
        try:
            new_path = synthesize_fn(take)
            if new_path and Path(new_path).exists() and Path(new_path).stat().st_size > 0:
                profile = self.get_profile(take.character_id)
                prof_version = profile.version if profile else 1
                return self.atomic_replace_take(
                    utterance_id,
                    new_path,
                    profile_version=prof_version,
                )
        except Exception as exc:
            logger.error("Failed regenerating take for utterance %s: %s", utterance_id, exc)
        return False


    def check_invalidation_impact(
        self,
        character_id: str,
        new_engine: str,
        new_voice_id: str = "",
        new_reference_path: str = "",
    ) -> tuple[bool, list[str]]:
        """
        Check if updating a character voice profile will invalidate existing dialogue audio.

        Returns:
            (will_invalidate: bool, affected_utterance_ids: list[str])
        """
        existing = self.get_profile(character_id)
        if not existing:
            return False, []

        affected: list[str] = []
        takes = self.get_character_takes(character_id)

        # Invalidation occurs if engine, voice identity, or reference audio changes
        engine_changed = existing.selected_engine != new_engine
        voice_changed = (
            existing.default_voice_id != new_voice_id
            if new_voice_id
            else False
        )
        ref_changed = (
            existing.authorized_reference_path != new_reference_path
            if new_reference_path
            else False
        )

        if engine_changed or voice_changed or ref_changed:
            affected = [t.utterance_id for t in takes if not t.is_stale]
            return len(affected) > 0, affected

        return False, []

    def mark_takes_stale(self, character_id: str) -> int:
        """
        Mark all dialogue takes for a character as stale after voice profile change.

        Returns count of takes marked stale.
        """
        cid = str(character_id)
        count = 0
        for take in self._takes.values():
            if take.character_id == cid and not take.is_stale:
                take.is_stale = True
                count += 1
        logger.warning(
            "character_profile_service: marked %d takes as stale for character '%s'",
            count,
            cid,
        )
        return count

    def compare_cross_scene_takes(self, utterance_id_a: str, utterance_id_b: str) -> float:
        """
        Evaluate acoustic spectral consistency between two dialogue takes
        (e.g., across Scene 1 and Scene 4).

        Returns spectral cosine similarity score between 0.0 and 1.0.
        """
        take_a = self._takes.get(utterance_id_a)
        take_b = self._takes.get(utterance_id_b)

        if not take_a or not take_b:
            return 0.0

        return measure_acoustic_similarity(take_a.audio_path, take_b.audio_path)

    def _save_to_disk(self, profile: CharacterVoiceProfile) -> None:
        if not self.storage_dir:
            return
        cid = str(profile.character_id)
        out_file = self.storage_dir / f"{cid}.json"
        try:
            out_file.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed saving profile %s to disk: %s", cid, exc)

    def _load_from_disk(self) -> None:
        if not self.storage_dir or not self.storage_dir.is_dir():
            return
        for json_path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                profile = CharacterVoiceProfile(**data)
                self._profiles[str(profile.character_id)] = profile
            except Exception as exc:
                logger.debug("Failed parsing voice profile from %s: %s", json_path.name, exc)


__all__ = [
    "CharacterProfileService",
    "DialogueTakeRecord",
]
