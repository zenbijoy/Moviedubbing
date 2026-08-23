"""Glossary and Character Bible service for enforcing translation consistency."""

from __future__ import annotations

import logging
import re

from aidub.domain.character_bible import (
    CharacterBibleEntry,
    GlossaryTerm,
    ProjectCharacterBible,
)
from aidub.domain.types import LanguageTag

logger = logging.getLogger(__name__)


class GlossaryNotFoundError(LookupError):
    """Raised when a requested glossary term does not exist."""


class GlossaryService:
    """
    Manages project glossary and Character Bible rules.

    Provides:
      - Term enforcement (apply all glossary substitutions to translated text)
      - Character name localization lookup
      - Phonetic pronunciation dictionary overrides
    """

    def __init__(self, bible: ProjectCharacterBible) -> None:
        self._bible = bible

    def add_term(self, term: GlossaryTerm) -> None:
        """Add a glossary term rule to the project bible."""
        existing_ids = {t.term_id for t in self._bible.glossary_terms}
        if term.term_id in existing_ids:
            raise ValueError(f"glossary term {term.term_id!r} already exists")
        self._bible.glossary_terms.append(term)
        logger.debug("glossary term added: %s -> %s", term.source_term, term.target_term)

    def add_character(self, entry: CharacterBibleEntry) -> None:
        """Add a character entry to the Character Bible."""
        existing_ids = {c.character_id for c in self._bible.characters}
        if entry.character_id in existing_ids:
            raise ValueError(f"character {entry.character_id!r} already exists")
        self._bible.characters.append(entry)
        logger.debug("character added: %s", entry.name)

    def enforce_glossary(
        self,
        text: str,
        source_language: LanguageTag,
        target_language: LanguageTag,
    ) -> str:
        """Apply all matching glossary substitutions to translated text."""
        glossary = self._bible.get_glossary(source_language, target_language)
        for source_term, target_term in sorted(glossary.items(), key=lambda x: -len(x[0])):
            flags = 0 if _term_is_case_sensitive(self._bible, source_term) else re.IGNORECASE
            text = re.sub(re.escape(source_term), target_term, text, flags=flags)
        return text

    def localized_character_name(
        self,
        character_id: str,
        fallback: str = "",
    ) -> str:
        """Return localized name for a character, falling back to source name."""
        char = self._bible.get_character(character_id)
        if char is None:
            return fallback
        return char.localized_name or char.name

    def phonetic_pronunciation(self, character_id: str) -> str | None:
        """Return phonetic pronunciation override for a character name."""
        char = self._bible.get_character(character_id)
        if char is None:
            return None
        return char.pronunciation_phonetic or None

    def get_character(self, character_id: str) -> CharacterBibleEntry | None:
        return self._bible.get_character(character_id)


def _term_is_case_sensitive(bible: ProjectCharacterBible, source_term: str) -> bool:
    for term in bible.glossary_terms:
        if term.source_term == source_term:
            return term.case_sensitive
    return False


__all__ = ["GlossaryNotFoundError", "GlossaryService"]
