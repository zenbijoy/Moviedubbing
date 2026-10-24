"""
Tests for Isometric Syllable-Constrained Translation & Dialogue Adaptation Engine.
"""

from __future__ import annotations

import pytest

from aidub.translation.isometric_engine import (
    IsometricCandidate,
    IsometricReport,
    IsometricTranslationEngine,
)


def test_calculate_syllable_budget() -> None:
    # 2.0 seconds at ~5.4 syllables/second in Bengali -> ~11 syllables
    budget_bn = IsometricTranslationEngine.calculate_syllable_budget(2.0, "bn")
    assert 9 <= budget_bn <= 13

    # 3.0 seconds in English (~4.4 syl/s) -> ~13 syllables
    budget_en = IsometricTranslationEngine.calculate_syllable_budget(3.0, "en")
    assert 11 <= budget_en <= 15


def test_evaluate_candidate_metrics() -> None:
    # Bengali dialogue line: "আমরা এখন বের হব" (~6 syllables)
    cand = IsometricTranslationEngine.evaluate_candidate(
        text="আমরা এখন বের হব",
        target_duration_s=1.2,
        target_language="bn",
    )
    assert isinstance(cand, IsometricCandidate)
    assert cand.syllable_count > 0
    assert 0.0 <= cand.isometric_score <= 1.0
    assert 0.5 <= cand.time_stretch_ratio <= 2.0


def test_adapt_bengali_text_contraction() -> None:
    # Overly verbose line with "আমার মনে হয় যে"
    verbose_text = "আমার মনে হয় যে আমরা যাব"
    target_budget = 4

    adapted = IsometricTranslationEngine.adapt_bengali_text(verbose_text, target_budget)
    assert "মনে হয়" in adapted
    assert len(adapted) < len(verbose_text)


def test_optimize_dialogue_selects_best_candidate() -> None:
    candidates = [
        "খুব বেশি পরিমাণে কথা বলতে থাকা ঠিক হবে না",  # Very long (~15 syllables)
        "আমাদের যাওয়া উচিত",                         # Moderate (~7 syllables)
        "যাব",                                       # Very short (2 syllables)
    ]

    report = IsometricTranslationEngine.optimize_dialogue(
        source_text="We should leave now.",
        candidate_translations=candidates,
        source_duration_s=1.4,
        source_language="en",
        target_language="bn",
    )

    assert isinstance(report, IsometricReport)
    assert report.ideal_syllable_budget > 0
    assert len(report.all_evaluated_candidates) >= 3
    # The best candidate should have the highest isometric score
    assert report.best_candidate.isometric_score >= report.all_evaluated_candidates[-1].isometric_score
    assert report.best_candidate.text in [c.text for c in report.all_evaluated_candidates]
