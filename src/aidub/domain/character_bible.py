"""
Multi-Episode Character Bible & Glossary Domain Models.

Tracks character relationships, vocal tone rules, age/accent metadata,
glossary terms, pronunciation entries, and personality descriptors across multi-episode projects.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class SpeechRegister(StrEnum):
    FORMAL = "formal"
    INFORMAL = "informal"
    SLANG = "slang"
    POETIC = "poetic"
    ARCHAIC = "archaic"


class GlossaryTerm(ContractModel):
    """Glossary term domain model."""

    term_id: Identifier
    source_term: str = Field(min_length=1)
    target_term: str = Field(min_length=1)
    language_code: str = Field(default="bn-BD", max_length=16)
    source_language: str = Field(default="en-US", max_length=16)
    target_language: str = Field(default="bn-BD", max_length=16)
    notes: str = Field(default="")
    case_sensitive: bool = False


class PronunciationEntry(ContractModel):
    """Pronunciation override entry."""

    entry_id: Identifier
    word: str = Field(min_length=1)
    phonetic_spelling: str = Field(min_length=1)
    language_code: str = Field(default="bn-BD", max_length=16)


class CharacterProfile(ContractModel):
    """Legacy Character Profile model."""

    character_id: Identifier
    name: str = Field(default="")
    gender: str = Field(default="neutral", max_length=16)
    preferred_voice_id: str = Field(default="")
    localized_name: str = Field(default="")
    speech_register: SpeechRegister = SpeechRegister.INFORMAL
    pronunciation_phonetic: str = Field(default="")


class CharacterRelationship(ContractModel):
    """Relationship descriptor between two characters."""

    target_character_id: Identifier
    relationship_type: str = Field(min_length=1)  # e.g. "rival", "parent", "ally"
    honorific_mode: str = Field(default="formal", max_length=32)


class CharacterBibleEntry(ContractModel):
    """Complete character bible profile record."""

    character_id: Identifier
    display_name: str = Field(default="")
    name: str = Field(default="")
    localized_name: str = Field(default="")
    speech_register: SpeechRegister = SpeechRegister.INFORMAL
    pronunciation_phonetic: str = Field(default="")
    archetype: str = Field(default="protagonist", max_length=64)
    vocal_description: str = Field(default="warm baritone", max_length=128)
    age_category: str = Field(default="adult", max_length=32)
    accent: str = Field(default="standard", max_length=32)
    forbidden_terms: list[str] = Field(default_factory=list)
    relationships: list[CharacterRelationship] = Field(default_factory=list)


class ProjectCharacterBible(ContractModel):
    """Glossary and Character Bible project container."""

    project_id: Identifier
    version: str = Field(default="1.0.0", max_length=32)
    terms: list[GlossaryTerm] = Field(default_factory=list)
    pronunciations: list[PronunciationEntry] = Field(default_factory=list)
    characters: list[CharacterBibleEntry | CharacterProfile] = Field(default_factory=list)

    @property
    def glossary_terms(self) -> list[GlossaryTerm]:
        return self.terms

    @property
    def pronunciation_overrides(self) -> list[PronunciationEntry]:
        return self.pronunciations

    @property
    def character_profiles(self) -> list[CharacterBibleEntry | CharacterProfile]:
        return self.characters

    def get_character(self, character_id: str) -> CharacterBibleEntry | CharacterProfile | None:
        for c in self.characters:
            if c.character_id == character_id:
                return c
        return None

    def get_glossary(self, source_language: str, target_language: str) -> dict[str, str]:
        glossary_dict = {}
        for t in self.terms:
            if (
                t.source_language == source_language and t.target_language == target_language
            ) or t.language_code == target_language:
                glossary_dict[t.source_term] = t.target_term
        return glossary_dict


class CharacterBible(ContractModel):
    """Multi-episode project Character Bible container."""

    bible_id: Identifier
    project_series_title: str = Field(min_length=1)
    entries: dict[str, CharacterBibleEntry] = Field(default_factory=dict)


__all__ = [
    "CharacterBible",
    "CharacterBibleEntry",
    "CharacterProfile",
    "CharacterRelationship",
    "GlossaryTerm",
    "ProjectCharacterBible",
    "PronunciationEntry",
    "SpeechRegister",
]
