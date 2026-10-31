"""
Unit and UI Integration Tests for Isochronic Dialogue Translator & Syllable Adapter.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from aidub.translation.isometric_engine import (
    IsometricCandidate,
    IsometricReport,
    IsometricTranslationEngine,
)

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from aidub.ui.dialogs.isochronic_dialogue_adapter_dialog import IsochronicDialogueAdapterDialog


@pytest.fixture(autouse=True)
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_calculate_bilabial_sync_metrics() -> None:
    # 1. Matching bilabials (English "problem" [p, b, m] vs Bengali "সমস্যা" [ম])
    score_matched = IsometricTranslationEngine.calculate_bilabial_sync(
        "We have a big problem here.",
        "আমাদের এখানে একটা বড় সমস্যা আছে।"
    )
    assert 0.4 <= score_matched <= 1.0

    # 2. Neither has bilabials
    score_none = IsometricTranslationEngine.calculate_bilabial_sync("See it.", "দেখো।")
    assert score_none == 1.0

    # 3. Target has bilabials while source has open vowels
    score_partial = IsometricTranslationEngine.calculate_bilabial_sync("Go away.", "চলে যাও।")
    assert 0.0 <= score_partial <= 1.0


def test_generate_candidate_variations() -> None:
    source_text = "We have a big problem right now."
    target_text = "আমাদের এখন এই মুহূর্তে একটা সমস্যা আছে।"
    duration_s = 2.0

    variations = IsometricTranslationEngine.generate_candidate_variations(
        source_text=source_text,
        base_bengali_text=target_text,
        target_duration_s=duration_s,
        target_language="bn",
    )

    assert len(variations) >= 2
    # Verify candidate attributes
    for cand in variations:
        assert isinstance(cand, IsometricCandidate)
        assert cand.syllable_count > 0
        assert 0.0 <= cand.isometric_score <= 1.0
        assert 0.0 <= cand.bilabial_sync_score <= 1.0
        assert cand.adaptation_applied in [
            "literal",
            "contracted",
            "colloquial",
            "expanded",
            "concise",
            "lip_aligned",
        ]

    # Sorted by isometric score descending
    assert variations[0].isometric_score >= variations[-1].isometric_score


def test_colloquial_and_expansion_variations() -> None:
    # Short text needing expansion
    short_text = "না"
    vars_exp = IsometricTranslationEngine.generate_candidate_variations(
        source_text="No, absolutely not.",
        base_bengali_text=short_text,
        target_duration_s=1.5,  # Budget ~8 syl, base is only 1 syl
        target_language="bn",
    )
    assert any(c.adaptation_applied == "expanded" for c in vars_exp)

    # Verb requiring colloquial contraction
    sadhu_text = "আমরা কাজটি করতেছি"
    vars_coll = IsometricTranslationEngine.generate_candidate_variations(
        source_text="We are doing the work.",
        base_bengali_text=sadhu_text,
        target_duration_s=1.2,
        target_language="bn",
    )
    assert any(c.adaptation_applied == "colloquial" for c in vars_coll)


def test_isochronic_dialog_initialization_and_metrics(tmp_path: Path) -> None:
    dlg = IsochronicDialogueAdapterDialog(
        cue_id="cue_042",
        source_text="I will never forgive you for this.",
        source_duration_s=2.4,
        target_text="আমি তোমাকে কখনোই ক্ষমা করব না!",
        target_language="bn",
    )

    assert dlg.cue_id == "cue_042"
    assert dlg.badge_cue.text() == "CUE: CUE_042"
    assert dlg.txt_source.text() == "I will never forgive you for this."
    assert dlg.spn_duration.value() == 2.4
    assert dlg.table_candidates.rowCount() >= 2

    # Check metric cards
    assert dlg._current_eval is not None
    assert dlg._current_eval.target_budget_syllables > 0
    assert dlg._current_eval.syllable_count > 0


def test_isochronic_dialog_candidate_selection_and_auto_adapt() -> None:
    dlg = IsochronicDialogueAdapterDialog(
        cue_id="cue_010",
        source_text="Wait a moment, please.",
        source_duration_s=1.5,
        target_text="অনুগ্রহ করে একটু অপেক্ষা করুন।",
        target_language="bn",
    )

    # Click auto adapt
    initial_text = dlg.txt_target.text()
    dlg.btn_auto_adapt.click()
    assert dlg.txt_target.text() != ""

    # Test candidate row "Use This"
    if dlg.table_candidates.rowCount() > 0:
        btn_use = dlg.table_candidates.cellWidget(0, 6)
        if btn_use is not None:
            btn_use.click()
            assert dlg.txt_target.text() == dlg._candidates[0].text


def test_isochronic_dialog_audition_and_apply(tmp_path: Path) -> None:
    dlg = IsochronicDialogueAdapterDialog(
        cue_id="cue_099",
        source_text="Everything is ready.",
        source_duration_s=1.8,
        target_text="সবকিছু প্রস্তুত আছে।",
        target_language="bn",
    )

    auditioned_events: list[tuple[str, float]] = []
    dlg.variation_auditioned.connect(lambda txt, st: auditioned_events.append((txt, st)))

    dlg.btn_audition.click()
    assert len(auditioned_events) == 1
    assert auditioned_events[0][0] == "সবকিছু প্রস্তুত আছে।"
    assert Path("output/isochronic_audition.wav").exists()

    applied_events: list[tuple[str, str, float]] = []
    dlg.adapted_cue_applied.connect(lambda cid, txt, dur: applied_events.append((cid, txt, dur)))

    dlg.btn_apply.click()
    assert len(applied_events) == 1
    assert applied_events[0][0] == "cue_099"
    assert applied_events[0][1] == "সবকিছু প্রস্তুত আছে।"
    assert applied_events[0][2] > 0.0
