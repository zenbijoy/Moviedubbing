"""
Unit tests for Bengali ASS Subtitle & Typography Styler (libass / HarfBuzz).
"""

from __future__ import annotations

from pathlib import Path

from aidub.subtitles.bengali_ass_styler import (
    BengaliAssStyler,
    BengaliSubtitleStyle,
    format_ass_timestamp,
    normalize_bengali_unicode,
)


def test_bengali_unicode_normalization_preserves_conjuncts() -> None:
    # Test complex juktoborno strings
    sample = "এআই মুভি ডাবিং স্টুডিওতে স্বাগতম। আন্তর্জাতিক মানের ডাবিং।"
    normalized = normalize_bengali_unicode(sample)

    assert normalized == sample
    assert "স্টুডিও" in normalized
    assert "আন্তর্জাতিক" in normalized
    assert "স্বাগতম" in normalized


def test_format_ass_timestamp() -> None:
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(1.5) == "0:00:01.50"
    assert format_ass_timestamp(65.25) == "0:01:05.25"
    assert format_ass_timestamp(3661.08) == "1:01:01.08"


def test_generate_ass_bilingual_stacked(tmp_path: Path) -> None:
    output_ass = tmp_path / "test_bilingual.ass"

    segments = [
        {
            "start": 1.2,
            "end": 3.8,
            "src": "Welcome to the dubbing suite.",
            "tgt": "ডাবিং স্টুডিওতে আপনাকে স্বাগতম।",
            "speaker": "SPEAKER_00",
        },
        {
            "start": 4.5,
            "end": 6.0,
            "src": "Let us begin.",
            "tgt": "আসুন শুরু করি।",
            "speaker": "SPEAKER_01",
        },
    ]

    res_path = BengaliAssStyler.generate_ass(
        segments=segments,
        output_path=output_ass,
        style_preset=BengaliSubtitleStyle.BILINGUAL_STACKED,
    )

    assert res_path.is_file()
    content = res_path.read_text(encoding="utf-8-sig")

    # Verify ASS V4+ syntax
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Style: Bengali_Main" in content
    assert "Style: English_Source" in content

    # Verify Cues
    assert "ডাবিং স্টুডিওতে আপনাকে স্বাগতম।" in content
    assert "Welcome to the dubbing suite." in content
    assert "Dialogue: 0,0:00:01.20,0:00:03.80,Bengali_Main" in content
