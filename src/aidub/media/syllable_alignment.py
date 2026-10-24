"""
Phonetic Syllable Alignment & ADR Rhythm Match Engine for Movie Dubbing.

Computes syllable counts, phonetic speaking rates, rhythm match scores,
and optimal WSOLA time-stretch recommendations between source and translated dialogue lines.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

# Bengali Vowel Characters (Independent and Dependent Matras)
BENGALI_VOWELS = set("অআইঈউঊঋএঐওঔািীুূৃেৈোৌ")
# Devanagari Vowel Characters (Hindi, Marathi, Nepali, Sanskrit)
DEVANAGARI_VOWELS = set("अआइईउऊऋएऐओऔािीुूृेैोौॉॅंः")
# English Vowel Pattern for Syllable Approximation
ENGLISH_VOWEL_PATTERN = re.compile(r"[aeiouy]+", re.IGNORECASE)


@dataclass
class RhythmMatchReport:
    """Detailed ADR rhythm and lip-sync syllable compatibility report."""

    source_text: str
    target_text: str
    source_syllables: int
    target_syllables: int
    source_duration_s: float
    target_duration_s: float
    source_rate: float  # syllables per second
    target_rate: float  # syllables per second
    match_score: float  # 0.0 to 1.0 (1.0 = identical speaking rhythm)
    recommended_stretch: float  # 0.75 to 1.35
    is_lip_compatible: bool
    remediation_hint: str


class SyllableAlignmentEngine:
    """Analyzes dialogue rhythmic timing and syllable density for cinematic lip-sync matching."""

    @classmethod
    def count_bengali_syllables(cls, text: str) -> int:
        """Count phonetic syllable nuclei in Bengali text."""
        cleaned = re.sub(r"[^\u0980-\u09FF\s]", "", text).strip()
        if not cleaned:
            return max(1, len(text.split()))

        count = 0
        words = cleaned.split()
        for word in words:
            vowels_in_word = sum(1 for ch in word if ch in BENGALI_VOWELS)
            # In Bengali, consonants with inherent 'অ' vowel also form syllables if no halant
            if vowels_in_word == 0:
                count += max(1, len(word) // 2)
            else:
                count += vowels_in_word
        return max(1, count)

    @classmethod
    def count_devanagari_syllables(cls, text: str) -> int:
        """Count phonetic syllable nuclei in Devanagari (Hindi, Marathi, etc.) text."""
        cleaned = re.sub(r"[^\u0900-\u097F\s]", "", text).strip()
        if not cleaned:
            return max(1, len(text.split()))

        count = 0
        words = cleaned.split()
        for word in words:
            vowels_in_word = sum(1 for ch in word if ch in DEVANAGARI_VOWELS)
            if vowels_in_word == 0:
                count += max(1, len(word) // 2)
            else:
                count += vowels_in_word
        return max(1, count)

    @classmethod
    def count_cjk_syllables(cls, text: str) -> int:
        """Count syllables/moras in CJK text (Chinese, Japanese, Korean)."""
        cjk_chars = [
            ch
            for ch in text
            if ("\u4e00" <= ch <= "\u9fff")
            or ("\u3040" <= ch <= "\u30ff")
            or ("\uac00" <= ch <= "\ud7af")
        ]
        return max(1, len(cjk_chars)) if cjk_chars else max(1, len(text.split()))

    @classmethod
    def count_english_syllables(cls, text: str) -> int:
        """Estimate syllable count in English text using vowel-chunk analysis."""
        words = re.findall(r"[a-z]+", text.lower())
        if not words:
            return max(1, len(text.split()))

        total_syllables = 0
        for word in words:
            matches = ENGLISH_VOWEL_PATTERN.findall(word)
            syllables = len(matches)
            # Subtract silent final 'e'
            if word.endswith("e") and not word.endswith("le") and syllables > 1:
                syllables -= 1
            total_syllables += max(1, syllables)
        return max(1, total_syllables)

    @classmethod
    def count_syllables(cls, text: str, language: str = "auto") -> int:
        """Determine syllable count based on detected script or language code."""
        lang = language.lower().split("-")[0]
        # Check if text contains Bengali unicode block
        has_bengali = any("\u0980" <= ch <= "\u09FF" for ch in text)
        if has_bengali or lang == "bn":
            return cls.count_bengali_syllables(text)

        has_devanagari = any("\u0900" <= ch <= "\u097F" for ch in text)
        if has_devanagari or lang in ("hi", "mr", "ne", "sa"):
            return cls.count_devanagari_syllables(text)

        has_cjk = any(
            ("\u4e00" <= ch <= "\u9fff")
            or ("\u3040" <= ch <= "\u30ff")
            or ("\uac00" <= ch <= "\ud7af")
            for ch in text
        )
        if has_cjk or lang in ("zh", "ja", "ko"):
            return cls.count_cjk_syllables(text)

        return cls.count_english_syllables(text)

    @classmethod
    def analyze_rhythm_match(
        cls,
        source_text: str,
        target_text: str,
        source_duration_s: float,
        target_duration_s: float | None = None,
    ) -> RhythmMatchReport:
        """
        Evaluate rhythm match and lip-sync feasibility between source and translated dialogue.

        Args:
            source_text: Original dialogue (e.g. English).
            target_text: Translated dialogue (e.g. Bengali).
            source_duration_s: Available time slot in the video in seconds.
            target_duration_s: Duration of synthesized localized audio in seconds.
        """
        src_dur = max(0.1, source_duration_s)
        tgt_dur = max(0.1, target_duration_s if target_duration_s is not None else src_dur)

        src_syl = cls.count_syllables(source_text, language="en")
        tgt_syl = cls.count_syllables(target_text, language="bn")

        src_rate = src_syl / src_dur
        tgt_rate = tgt_syl / tgt_dur

        # Calculate rhythm divergence using Gaussian kernel
        rate_diff = abs(tgt_rate - src_rate)
        match_score = math.exp(-rate_diff / 3.0)
        match_score = max(0.0, min(1.0, match_score))

        # Recommended WSOLA stretch factor (clamped between 0.75x and 1.35x)
        raw_stretch = tgt_dur / src_dur
        recommended_stretch = max(0.75, min(1.35, raw_stretch))

        is_compatible = match_score >= 0.70

        if match_score >= 0.85:
            hint = "✓ Excellent lip-sync alignment and rhythmic cadence."
        elif tgt_rate > src_rate:
            overshoot = round((tgt_rate - src_rate) / src_rate * 100)
            hint = f"Target dialogue is {overshoot}% too fast for natural lip motion. Consider shortening the translation."
        else:
            undershoot = round((src_rate - tgt_rate) / src_rate * 100)
            hint = f"Target dialogue is {undershoot}% slower than source. Natural pacing with WSOLA padding recommended."

        return RhythmMatchReport(
            source_text=source_text,
            target_text=target_text,
            source_syllables=src_syl,
            target_syllables=tgt_syl,
            source_duration_s=src_dur,
            target_duration_s=tgt_dur,
            source_rate=round(src_rate, 2),
            target_rate=round(tgt_rate, 2),
            match_score=round(match_score, 3),
            recommended_stretch=round(recommended_stretch, 3),
            is_lip_compatible=is_compatible,
            remediation_hint=hint,
        )


__all__ = [
    "BENGALI_VOWELS",
    "DEVANAGARI_VOWELS",
    "RhythmMatchReport",
    "SyllableAlignmentEngine",
]
