"""Unit tests for Phonetic Syllable Alignment & ADR Rhythm Match Engine."""

from __future__ import annotations

import pytest
from aidub.media.syllable_alignment import (
    BENGALI_VOWELS,
    RhythmMatchReport,
    SyllableAlignmentEngine,
)


def test_bengali_syllable_counting():
    # "আমি তোমাকে ভালোবাসি" has known vowel nuclei
    text = "আমি তোমাকে ভালোবাসি"
    count = SyllableAlignmentEngine.count_bengali_syllables(text)
    assert count >= 6
    assert isinstance(count, int)

    # Empty string fallback
    assert SyllableAlignmentEngine.count_bengali_syllables("") >= 1


def test_english_syllable_counting():
    text = "cinematic movie dubbing"
    count = SyllableAlignmentEngine.count_english_syllables(text)
    # ci-ne-ma-tic (4) + mo-vie (2) + dub-bing (2) ~ 8 syllables
    assert 6 <= count <= 9

    # Silent final 'e' reduction
    assert SyllableAlignmentEngine.count_english_syllables("make") == 1
    assert SyllableAlignmentEngine.count_english_syllables("table") >= 1


def test_auto_script_detection():
    bn_count = SyllableAlignmentEngine.count_syllables("বাংলা ভাষা", language="auto")
    en_count = SyllableAlignmentEngine.count_syllables("Hello world", language="auto")
    assert bn_count >= 2
    assert en_count >= 2


def test_analyze_rhythm_match_cadence():
    src_text = "I need you to listen to me right now."
    tgt_text = "আমি চাই তুমি এখনই আমার কথা শোনো।"

    report = SyllableAlignmentEngine.analyze_rhythm_match(
        source_text=src_text,
        target_text=tgt_text,
        source_duration_s=2.5,
        target_duration_s=2.4,
    )

    assert isinstance(report, RhythmMatchReport)
    assert report.source_duration_s == 2.5
    assert report.target_duration_s == 2.4
    assert report.source_rate > 0
    assert report.target_rate > 0
    assert 0.0 <= report.match_score <= 1.0
    # Recommended stretch clamped between 0.75 and 1.35
    assert 0.75 <= report.recommended_stretch <= 1.35
    assert isinstance(report.is_lip_compatible, bool)
    assert len(report.remediation_hint) > 0


def test_analyze_rhythm_match_extreme_mismatch():
    # Long translation stuffed into very short time slot
    report = SyllableAlignmentEngine.analyze_rhythm_match(
        source_text="No.",
        target_text="না এটা কোনোভাবেই সম্ভব নয় কারণ আমি এটা করতে পারব না কখনোই।",
        source_duration_s=0.5,
        target_duration_s=4.0,
    )
    assert report.match_score < 0.60
    assert not report.is_lip_compatible
    assert report.recommended_stretch == 1.35  # clamped at max
    assert "too fast" in report.remediation_hint


def test_devanagari_and_cjk_syllable_counting():
    # Hindi: "नमस्ते दुनिया" (Namaste duniya)
    hi_count = SyllableAlignmentEngine.count_devanagari_syllables("नमस्ते दुनिया")
    assert hi_count >= 4

    # CJK: Chinese "你好世界" (4 syllables/chars) and Japanese "こんにちは" (5 moras)
    zh_count = SyllableAlignmentEngine.count_cjk_syllables("你好世界")
    assert zh_count == 4
    ja_count = SyllableAlignmentEngine.count_cjk_syllables("こんにちは")
    assert ja_count == 5

    # Auto detection for Hindi and CJK
    assert SyllableAlignmentEngine.count_syllables("नमस्ते दुनिया", language="auto") >= 4
    assert SyllableAlignmentEngine.count_syllables("你好世界", language="auto") == 4

