"""
Isometric Syllable-Constrained Translation & Dialogue Adaptation Engine.

Ensures localized movie dialogue matches the exact syllable count, mouth cadence,
and time duration of the original actor's speech to achieve cinematic lip-sync.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

from aidub.media.syllable_alignment import SyllableAlignmentEngine

logger = logging.getLogger(__name__)


# ── Language Pacing Profiles (Phonetic Syllables per Second) ─────────────────
# Standard cinematic dialogue pacing distributions (mu, sigma)
PACING_PROFILES: dict[str, tuple[float, float]] = {
    "en": (4.4, 0.6),  # English: ~4.4 syl/sec
    "bn": (5.4, 0.7),  # Bengali: ~5.4 syl/sec (higher agglutinative density)
    "hi": (5.2, 0.7),  # Hindi: ~5.2 syl/sec
    "es": (5.8, 0.8),  # Spanish: ~5.8 syl/sec (syllable-timed language)
    "ja": (6.5, 0.9),  # Japanese: ~6.5 morae/sec
    "de": (4.2, 0.5),  # German: ~4.2 syl/sec
    "fr": (5.1, 0.6),  # French: ~5.1 syl/sec
}


# ── Bengali Phrase Simplifications & Contractions for Syllable Fitting ────────
# (Pattern, Replacement, Syllable delta)
BENGALI_CONTRACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"আমার মনে হয় যে", re.IGNORECASE), "মনে হয়"),  # 6 -> 3 syl
    (re.compile(r"এই কারণে যে", re.IGNORECASE), "কারণ"),  # 5 -> 2 syl
    (re.compile(r"করতে সমর্থ হওয়া", re.IGNORECASE), "পারা"),  # 7 -> 2 syl
    (re.compile(r"কথা বলতে থাকা", re.IGNORECASE), "বলা"),  # 6 -> 2 syl
    (re.compile(r"অনুগ্রহ করে", re.IGNORECASE), "দয়া করে"),  # 5 -> 4 syl
    (re.compile(r"খুব বেশি পরিমাণে", re.IGNORECASE), "প্রচুর"),  # 7 -> 2 syl
    (re.compile(r"এখন এই মুহূর্তে", re.IGNORECASE), "এখনই"),  # 6 -> 3 syl
    (re.compile(r"কোনো সন্দেহ নেই", re.IGNORECASE), "নিশ্চিত"),  # 6 -> 2 syl
    (re.compile(r"চেষ্টা করতে থাকা", re.IGNORECASE), "চেষ্টা করা"),  # 6 -> 4 syl
    (re.compile(r"ঠিক এই সময়ে", re.IGNORECASE), "তখনই"),  # 5 -> 2 syl
]

# Bengali Expansion Rules (for padding undershooting lines)
BENGALI_EXPANSIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^না$", re.IGNORECASE), "কখনোই না"),  # 1 -> 4 syl
    (re.compile(r"^হ্যাঁ$", re.IGNORECASE), "হ্যাঁ অবশ্যই"),  # 1 -> 4 syl
    (re.compile(r"\bযাব\b", re.IGNORECASE), "চলে যাব"),  # 2 -> 3 syl
    (re.compile(r"\bবলব\b", re.IGNORECASE), "বলে দেব"),  # 2 -> 3 syl
    (re.compile(r"\bকরব\b", re.IGNORECASE), "করে ফেলব"),  # 2 -> 4 syl
]


@dataclass
class IsometricCandidate:
    """An isometric translation candidate with duration and syllable metrics."""

    text: str
    syllable_count: int
    target_budget_syllables: int
    syllable_deviation: int
    estimated_duration_s: float
    target_duration_s: float
    time_stretch_ratio: float
    isometric_score: float  # 0.0 to 1.0 (1.0 = perfect mathematical match)
    is_lip_compliant: bool
    adaptation_applied: str = "none"
    bilabial_sync_score: float = 1.0


@dataclass
class IsometricReport:
    """Comprehensive isometric analysis of a dialogue line."""

    source_text: str
    source_language: str
    source_duration_s: float
    source_syllables: int
    target_language: str
    ideal_syllable_budget: int
    best_candidate: IsometricCandidate
    all_evaluated_candidates: list[IsometricCandidate] = field(default_factory=list)
    remediation_advice: str = ""


class IsometricTranslationEngine:
    """
    Mathematical Isometric Translation & Syllable-Constrained Adaptation Engine.

    Calculates optimal syllable budgets from source dialogue audio duration,
    evaluates translation candidates against visual speech constraints,
    and applies linguistic contractions/expansions to hit target syllable envelopes.
    """

    @classmethod
    def calculate_bilabial_sync(cls, source_text: str, target_text: str) -> float:
        """
        Calculate bilabial consonant alignment synchrony between source and target dialogue.

        In film dubbing, bilabial consonants (B/P/M/W <-> প/ফ/ব/ভ/ম) require complete
        physical closure of the lips. Aligning relative positions creates convincing lip sync.

        Returns:
            Score between 0.0 and 1.0 (1.0 = optimal lip closure synchrony).
        """
        src_bilabials = set("bpmwBPMW")
        tgt_bilabials = set("পফবভম")

        src_clean = re.sub(r"[^\w\s]", "", source_text)
        tgt_clean = re.sub(r"[^\w\s\u0980-\u09FF]", "", target_text)

        src_len = max(1, len(src_clean))
        tgt_len = max(1, len(tgt_clean))

        src_pos = [i / src_len for i, ch in enumerate(src_clean) if ch in src_bilabials]
        tgt_pos = [i / tgt_len for i, ch in enumerate(tgt_clean) if ch in tgt_bilabials]

        if not src_pos and not tgt_pos:
            return 1.0
        if not src_pos or not tgt_pos:
            return 0.70

        # Mean minimum distance between normalized positions
        dist_sum = sum(min(abs(sp - tp) for tp in tgt_pos) for sp in src_pos)
        mean_dist = dist_sum / len(src_pos)

        sync = math.exp(-pow(mean_dist * 3.5, 2))
        return round(float(max(0.1, min(1.0, sync))), 3)

    @classmethod
    def get_speaking_rate(cls, language: str) -> float:
        """Get baseline speaking rate (syllables/second) for a language."""
        lang_code = language.lower().split("-")[0]
        return PACING_PROFILES.get(lang_code, (5.0, 0.6))[0]

    @classmethod
    def calculate_syllable_budget(cls, duration_s: float, language: str) -> int:
        """
        Calculate ideal syllable budget for an audio duration slot.

        Mathematical model:
            S_target = round(duration_s * rate_mu)
        """
        rate = cls.get_speaking_rate(language)
        clamped_dur = max(0.2, duration_s)
        return max(1, round(clamped_dur * rate))

    @classmethod
    def evaluate_candidate(
        cls,
        text: str,
        target_duration_s: float,
        target_language: str = "bn",
        adaptation_applied: str = "none",
        source_text: str = "",
    ) -> IsometricCandidate:
        """
        Evaluate an isometric candidate against target speech duration and bilabial alignment.
        """
        rate = cls.get_speaking_rate(target_language)
        dur = max(0.1, target_duration_s)
        budget = cls.calculate_syllable_budget(dur, target_language)

        actual_syllables = SyllableAlignmentEngine.count_syllables(text, language=target_language)
        deviation = abs(actual_syllables - budget)

        estimated_duration = actual_syllables / rate
        stretch_ratio = dur / max(0.05, estimated_duration)

        # Gaussian penalty on syllable mismatch and stretch divergence
        syl_penalty = math.exp(-pow(deviation / max(1.0, float(budget)), 2) * 5.0)
        stretch_penalty = math.exp(-pow(stretch_ratio - 1.0, 2) * 10.0)
        base_score = max(0.0, min(1.0, syl_penalty * stretch_penalty))

        bilabial_score = 1.0
        if source_text.strip():
            bilabial_score = cls.calculate_bilabial_sync(source_text, text)
            combined_score = round(base_score * 0.75 + bilabial_score * 0.25, 3)
        else:
            combined_score = round(base_score, 3)

        # Lip-sync compliant if within 15% syllable budget and stretch between 0.85 and 1.20
        is_compliant = (deviation <= max(1, round(budget * 0.15))) and (
            0.85 <= stretch_ratio <= 1.20
        )

        return IsometricCandidate(
            text=text,
            syllable_count=actual_syllables,
            target_budget_syllables=budget,
            syllable_deviation=deviation,
            estimated_duration_s=round(estimated_duration, 2),
            target_duration_s=round(dur, 2),
            time_stretch_ratio=round(stretch_ratio, 3),
            isometric_score=combined_score,
            is_lip_compliant=is_compliant,
            adaptation_applied=adaptation_applied,
            bilabial_sync_score=bilabial_score,
        )

    @classmethod
    def adapt_bengali_text(cls, text: str, target_budget: int) -> str:
        """
        Algorithmically compress or expand Bengali text to fit syllable budget.
        """
        current_syl = SyllableAlignmentEngine.count_bengali_syllables(text)
        if current_syl == target_budget:
            return text

        adapted = text

        # If too long, apply contractions
        if current_syl > target_budget:
            for pattern, repl in BENGALI_CONTRACTIONS:
                if pattern.search(adapted):
                    candidate = pattern.sub(repl, adapted, count=1)
                    new_syl = SyllableAlignmentEngine.count_bengali_syllables(candidate)
                    if abs(new_syl - target_budget) < abs(current_syl - target_budget):
                        adapted = candidate
                        current_syl = new_syl
                    if current_syl <= target_budget:
                        break

        # If still too short, apply expansions
        elif current_syl < target_budget:
            for pattern, repl in BENGALI_EXPANSIONS:
                if pattern.search(adapted):
                    candidate = pattern.sub(repl, adapted, count=1)
                    new_syl = SyllableAlignmentEngine.count_bengali_syllables(candidate)
                    if abs(new_syl - target_budget) < abs(current_syl - target_budget):
                        adapted = candidate
                        current_syl = new_syl
                    if current_syl >= target_budget:
                        break

        return adapted

    @classmethod
    def generate_candidate_variations(
        cls,
        source_text: str,
        base_bengali_text: str,
        target_duration_s: float,
        target_language: str = "bn",
    ) -> list[IsometricCandidate]:
        """
        Generate multiple distinct translation candidates tailored to film dubbing:
        1. Literal / Direct (মূল অনুবাদ)
        2. Contracted (সংক্ষেপিত)
        3. Expanded (অনুদিত পরিবর্ধিত)
        4. Colloquial / Conversational (চলিত কথ্য রূপ)
        5. Bilabial Lip-Sync Optimized (ঠোঁট বন্ধকরণে সামঞ্জস্যপূর্ণ রূপ)
        """
        budget = cls.calculate_syllable_budget(target_duration_s, target_language)
        candidates_map: dict[str, str] = {}

        clean_base = base_bengali_text.strip()
        if not clean_base:
            clean_base = source_text

        # 1. Literal / Base
        candidates_map["literal"] = clean_base

        # 2. Contracted
        contracted = cls.adapt_bengali_text(clean_base, budget)
        if contracted != clean_base:
            candidates_map["contracted"] = contracted
        else:
            for pat, rep in BENGALI_CONTRACTIONS:
                if pat.search(clean_base):
                    candidates_map["contracted"] = pat.sub(rep, clean_base)
                    break

        # 3. Colloquial Conversational
        colloquial = clean_base
        colloquial_rules = [
            (re.compile(r"করতেছি(?=[\s।?!,;]|$)"), "করছি"),
            (re.compile(r"বলতেছি(?=[\s।?!,;]|$)"), "বলছি"),
            (re.compile(r"যাইতেছি(?=[\s।?!,;]|$)"), "যাচ্ছি"),
            (re.compile(r"খাইতেছি(?=[\s।?!,;]|$)"), "খাচ্ছি"),
            (re.compile(r"তাহাকে(?=[\s।?!,;]|$)"), "তাকে"),
            (re.compile(r"তাহাদের(?=[\s।?!,;]|$)"), "তাদের"),
            (re.compile(r"আমার সহিত(?=[\s।?!,;]|$)"), "আমার সাথে"),
            (re.compile(r"আমার সঙ্গে(?=[\s।?!,;]|$)"), "আমার সাথে"),
            (re.compile(r"এই কারণে(?=[\s।?!,;]|$)"), "তাই"),
            (re.compile(r"এই বিষয়ে(?=[\s।?!,;]|$)"), "এ নিয়ে"),
        ]
        for pat, rep in colloquial_rules:
            colloquial = pat.sub(rep, colloquial)
        if colloquial != clean_base:
            candidates_map["colloquial"] = colloquial

        # 4. Expanded (if syllables are below target budget)
        curr_syl = SyllableAlignmentEngine.count_syllables(clean_base, language=target_language)
        if curr_syl < budget:
            expanded = clean_base
            for pat, rep in BENGALI_EXPANSIONS:
                if pat.search(expanded):
                    expanded = pat.sub(rep, expanded)
                    break
            if expanded == clean_base:
                if "না" in expanded and "কখনোই না" not in expanded:
                    expanded = expanded.replace("না", "কখনোই না", 1)
                elif not expanded.startswith("আসলে"):
                    expanded = f"আসলে {expanded}"
            candidates_map["expanded"] = expanded
        elif curr_syl > budget and "contracted" not in candidates_map:
            candidates_map["concise"] = re.sub(r"\b(যে|তো|তাহলে|বেশ)\b", "", clean_base).strip()

        # 5. Bilabial Lip-Sync Optimized
        src_has_bilabials = bool(re.search(r"[bpmwBPMW]", source_text))
        tgt_has_bilabials = bool(re.search(r"[পফবভম]", clean_base))
        if src_has_bilabials and not tgt_has_bilabials:
            if clean_base.startswith("মনে হয়"):
                candidates_map["lip_aligned"] = clean_base.replace("মনে হয়", "বোধহয়", 1)
            else:
                candidates_map["lip_aligned"] = f"বোধহয় {clean_base}"
        elif not src_has_bilabials and tgt_has_bilabials:
            lip_alt = clean_base.replace("বোধহয়", "মনে হয়").replace("ব্যাপারটা", "বিষয়টা")
            if lip_alt != clean_base:
                candidates_map["lip_aligned"] = lip_alt

        results: list[IsometricCandidate] = []
        for tag, text_cand in candidates_map.items():
            if not text_cand.strip():
                continue
            cand_eval = cls.evaluate_candidate(
                text=text_cand.strip(),
                target_duration_s=target_duration_s,
                target_language=target_language,
                adaptation_applied=tag,
                source_text=source_text,
            )
            results.append(cand_eval)

        results.sort(key=lambda c: c.isometric_score, reverse=True)
        return results

    @classmethod
    def optimize_dialogue(
        cls,
        source_text: str,
        candidate_translations: list[str],
        source_duration_s: float,
        source_language: str = "en",
        target_language: str = "bn",
    ) -> IsometricReport:
        """
        Analyze and select or algorithmically adapt the best isometric candidate for a dialogue line.
        """
        budget = cls.calculate_syllable_budget(source_duration_s, target_language)
        src_syl = SyllableAlignmentEngine.count_syllables(source_text, language=source_language)

        evaluated: list[IsometricCandidate] = []

        # Evaluate all original candidates
        for raw_cand in candidate_translations:
            clean_cand = raw_cand.strip()
            if not clean_cand:
                continue
            cand_eval = cls.evaluate_candidate(
                clean_cand,
                target_duration_s=source_duration_s,
                target_language=target_language,
                adaptation_applied="raw_candidate",
                source_text=source_text,
            )
            evaluated.append(cand_eval)

            # If not perfectly compliant, attempt algorithmic adaptation
            if not cand_eval.is_lip_compliant and target_language.lower().startswith("bn"):
                adapted_text = cls.adapt_bengali_text(clean_cand, budget)
                if adapted_text != clean_cand:
                    adapted_eval = cls.evaluate_candidate(
                        adapted_text,
                        target_duration_s=source_duration_s,
                        target_language=target_language,
                        adaptation_applied="algorithmic_bengali_adaptation",
                        source_text=source_text,
                    )
                    evaluated.append(adapted_eval)

        # Fallback if no valid candidate supplied
        if not evaluated:
            fallback_text = candidate_translations[0] if candidate_translations else source_text
            evaluated.append(
                cls.evaluate_candidate(
                    fallback_text,
                    target_duration_s=source_duration_s,
                    target_language=target_language,
                    adaptation_applied="fallback",
                )
            )

        # Sort candidates by isometric score descending
        evaluated.sort(key=lambda c: c.isometric_score, reverse=True)
        best = evaluated[0]

        advice = (
            "✓ Isometric match verified: Line aligns seamlessly with actor's jaw cadence."
            if best.is_lip_compliant
            else f"⚠ Syllable divergence ({best.syllable_deviation} syl). Time-stretch: {best.time_stretch_ratio}x. Minor WSOLA alignment needed."
        )

        return IsometricReport(
            source_text=source_text,
            source_language=source_language,
            source_duration_s=source_duration_s,
            source_syllables=src_syl,
            target_language=target_language,
            ideal_syllable_budget=budget,
            best_candidate=best,
            all_evaluated_candidates=evaluated,
            remediation_advice=advice,
        )


__all__ = [
    "PACING_PROFILES",
    "IsometricCandidate",
    "IsometricReport",
    "IsometricTranslationEngine",
]
