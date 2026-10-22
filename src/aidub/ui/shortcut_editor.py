"""
Customizable hotkey rebinding, conflict detection, and profile import/export engine.

Features:
  - Conflict detection: prevents duplicate hotkey assignments across actions.
  - JSON import/export for custom user shortcut files (.aidub-keys).
  - Reset to default bindings per action or profile.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel
from aidub.ui.keyboard_shortcuts import (
    NleProfile,
    ShortcutAction,
    ShortcutManager,
)

logger = logging.getLogger(__name__)


class ShortcutConflict(ContractModel):
    """Details of a hotkey assignment conflict."""

    key_sequence: str
    existing_action: ShortcutAction
    attempted_action: ShortcutAction


class CustomShortcutProfile(ContractModel):
    """Serializable custom keyboard shortcut configuration profile."""

    name: str = Field(min_length=1, max_length=128)
    base_nle_profile: NleProfile = NleProfile.DEFAULT
    bindings: dict[str, ShortcutAction] = Field(default_factory=dict)


class ShortcutEditor:
    """
    Manages custom hotkey rebinding, conflict validation, and profile persistence.
    """

    def __init__(self, manager: ShortcutManager | None = None) -> None:
        self._manager = manager or ShortcutManager()

    def check_conflict(self, key_sequence: str, action: ShortcutAction) -> ShortcutConflict | None:
        """
        Check if assigning key_sequence to action causes a conflict with an existing binding.
        """
        seq_clean = key_sequence.strip().upper()
        existing = self._manager.resolve(seq_clean)
        if existing is not None and existing != action:
            return ShortcutConflict(
                key_sequence=seq_clean,
                existing_action=existing,
                attempted_action=action,
            )
        return None

    def rebind(
        self, key_sequence: str, action: ShortcutAction, *, force: bool = False
    ) -> ShortcutConflict | None:
        """
        Rebind key_sequence to action. If force is False, returns conflict if present.
        """
        conflict = self.check_conflict(key_sequence, action)
        if conflict and not force:
            return conflict

        self._manager.bind(key_sequence, action)
        logger.info("shortcut_editor: rebound %s -> %s", key_sequence, action.value)
        return None

    def export_profile(self, profile_name: str, file_path: str | Path) -> None:
        """Export current key bindings to a JSON file."""
        profile = CustomShortcutProfile(
            name=profile_name,
            base_nle_profile=self._manager.profile,
            bindings=dict(self._manager._map),
        )
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        logger.info("shortcut_editor: exported profile %s to %s", profile_name, path)

    def import_profile(self, file_path: str | Path) -> CustomShortcutProfile:
        """Import key bindings from a JSON profile file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"shortcut profile file {file_path!r} not found")

        content = path.read_text(encoding="utf-8")
        profile = CustomShortcutProfile.model_validate_json(content)

        self._manager.load_profile(profile.base_nle_profile)
        for key_seq, action in profile.bindings.items():
            self._manager.bind(key_seq, action)

        logger.info("shortcut_editor: imported profile %s from %s", profile.name, path)
        return profile


__all__ = [
    "CustomShortcutProfile",
    "ShortcutConflict",
    "ShortcutEditor",
]
