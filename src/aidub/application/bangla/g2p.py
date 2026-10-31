"""
Bangla Grapheme-to-Phoneme (G2P) and Viseme Mapping Engine for Film Lip-Sync.
Converts Bengali script into IPA phonetic transcriptions and Disney/MPEG-4 facial visemes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Bengali Vowels to Visemes
BN_VOWEL_VISEME_MAP: dict[str, str] = {
    "অ": "O",
    "আ": "AA",
    "ই": "I",
    "ঈ": "I",
    "উ": "U",
    "ঊ": "U",
    "ঋ": "I",
    "এ": "E",
    "ঐ": "E",
    "ও": "O",
    "ঔ": "O",
}

# Bengali Matras (Vowel Diacritics)
BN_MATRA_VISEME_MAP: dict[str, str] = {
    "া": "AA",
    "ি": "I",
    "ী": "I",
    "ু": "U",
    "ূ": "U",
    "ৃ": "I",
    "ে": "E",
    "ৈ": "E",
    "ো": "O",
    "ৌ": "O",
}

# Bengali Consonants to Visemes
BN_CONSONANT_VISEME_MAP: dict[str, str] = {
    # Bilabials (lips closed)
    "প": "BMP", "ফ": "BMP", "ব": "BMP", "ভ": "BMP", "ম": "BMP",
    # Dentals / Alveolars (tongue behind teeth)
    "ত": "TDNL", "থ": "TDNL", "দ": "TDNL", "ধ": "TDNL", "ন": "TDNL",
    "ট": "TDNL", "ঠ": "TDNL", "ড": "TDNL", "ঢ": "TDNL", "ণ": "TDNL",
    "ল": "TDNL", "র": "TDNL", "ড়": "TDNL", "ঢ়": "TDNL", "ৎ": "TDNL",
    # Velars (open mouth, tongue at soft palate)
    "ক": "GK", "খ": "GK", "গ": "GK", "ঘ": "GK", "ঙ": "GK", "ং": "GK",
    # Palato-alveolars & Sibilants (teeth close)
    "চ": "CH_SH", "ছ": "CH_SH", "জ": "SZ", "ঝ": "SZ", "য": "SZ", "য়": "I",
    "শ": "CH_SH", "ষ": "CH_SH", "স": "SZ", "হ": "REST",
    "ঃ": "REST", "ঁ": "REST",
}


@dataclass
class BanglaPhoneme:
    char: str
    ipa: str
    viseme: str
    is_vowel: bool


class BanglaG2P:
    """
    Bangla G2P rules and viseme converter for visual speech alignment.
    Supports Bengali orthography, matras, hasanta combinations, and conjuncts.
    """

    @classmethod
    def char_to_viseme(cls, char: str) -> str:
        """Returns the facial viseme corresponding to a Bengali character or matra."""
        if char in BN_MATRA_VISEME_MAP:
            return BN_MATRA_VISEME_MAP[char]
        if char in BN_VOWEL_VISEME_MAP:
            return BN_VOWEL_VISEME_MAP[char]
        if char in BN_CONSONANT_VISEME_MAP:
            return BN_CONSONANT_VISEME_MAP[char]
        return "REST"

    @classmethod
    def text_to_visemes(cls, text: str) -> list[str]:
        """Converts Bengali dialogue text into an ordered sequence of facial visemes."""
        visemes: list[str] = []
        cleaned = re.sub(r"[^\u0980-\u09FF\s]", "", text)

        for word in cleaned.split():
            word_visemes: list[str] = []
            i = 0
            while i < len(word):
                ch = word[i]
                # Check next character for matra
                if i + 1 < len(word) and word[i + 1] in BN_MATRA_VISEME_MAP:
                    c_vis = cls.char_to_viseme(ch)
                    v_vis = cls.char_to_viseme(word[i + 1])
                    word_visemes.append(c_vis)
                    word_visemes.append(v_vis)
                    i += 2
                    continue
                # Inherent vowel 'অ' (O) for consonants without hasanta or matra
                if ch in BN_CONSONANT_VISEME_MAP:
                    word_visemes.append(cls.char_to_viseme(ch))
                    # Inherent vowel
                    if i + 1 == len(word) or word[i + 1] not in {"্", "া", "ি", "ী", "ু", "ূ", "ৃ", "ে", "ৈ", "ো", "ৌ"}:
                        word_visemes.append("O")
                elif ch in BN_VOWEL_VISEME_MAP or ch in BN_MATRA_VISEME_MAP:
                    word_visemes.append(cls.char_to_viseme(ch))
                i += 1

            if word_visemes:
                # Add word visemes + brief inter-word pause
                visemes.extend(word_visemes)
                visemes.append("REST")

        return visemes if visemes else ["REST"]

    @classmethod
    def align_sentence_timing(
        cls,
        text: str,
        start_s: float = 0.0,
        end_s: float | None = None,
        total_duration_sec: float | None = None,
    ) -> list[tuple[str, float, float]]:
        """
        Distributes Bengali visemes evenly across the spoken duration.
        Returns list of (viseme_code, start_time_s, end_time_s).
        """
        if end_s is None:
            end_s = start_s + (total_duration_sec if total_duration_sec is not None else 2.0)

        visemes = cls.text_to_visemes(text)
        if not visemes:
            return [("REST", start_s, end_s)]

        dur = max(0.05, end_s - start_s)
        step = dur / len(visemes)

        timeline: list[tuple[str, float, float]] = []
        for i, v in enumerate(visemes):
            st = round(start_s + (i * step), 3)
            et = round(st + step, 3)
            timeline.append((v, st, et))

        return timeline


__all__ = ["BanglaG2P", "BN_VOWEL_VISEME_MAP", "BN_CONSONANT_VISEME_MAP", "BN_MATRA_VISEME_MAP"]
