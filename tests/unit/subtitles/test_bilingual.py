"""Unit tests for standard SRT and dual-language bilingual SRT generation."""

from __future__ import annotations

from pathlib import Path

from aidub.subtitles.bilingual import LineMode, format_srt_timestamp, write_bilingual_srt, write_srt


def test_format_srt_timestamp() -> None:
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.432) == "00:01:05,432"
    assert format_srt_timestamp(3661.100) == "01:01:01,100"


def test_write_srt(tmp_path: Path) -> None:
    segs = [
        {"start": 1.0, "end": 3.5, "text": "Hello world", "tgt": "হ্যালো বিশ্ব"},
        {"start": 4.0, "end": 6.0, "text": "Testing SRT", "tgt": "পরীক্ষা এসআরটি"},
    ]

    out_src = tmp_path / "src.srt"
    write_srt(segs, out_src, translated=False)
    content_src = out_src.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:03,500" in content_src
    assert "Hello world" in content_src

    out_tgt = tmp_path / "tgt.srt"
    write_srt(segs, out_tgt, translated=True)
    content_tgt = out_tgt.read_text(encoding="utf-8")
    assert "হ্যালো বিশ্ব" in content_tgt


def test_write_bilingual_srt(tmp_path: Path) -> None:
    segs = [
        {"start": 1.0, "end": 3.5, "text": "Hello world", "tgt": "হ্যালো বিশ্ব"},
    ]

    out_bi_bot = tmp_path / "bi_bot.srt"
    write_bilingual_srt(segs, out_bi_bot, mode=LineMode.BILINGUAL_TARGET_BOTTOM)
    content_bot = out_bi_bot.read_text(encoding="utf-8")
    lines_bot = [line.strip() for line in content_bot.splitlines() if line.strip()]
    # Expected order: index, timestamp, source text, target text
    assert lines_bot[2] == "Hello world"
    assert lines_bot[3] == "হ্যালো বিশ্ব"

    out_bi_top = tmp_path / "bi_top.srt"
    write_bilingual_srt(segs, out_bi_top, mode=LineMode.BILINGUAL_TARGET_TOP)
    content_top = out_bi_top.read_text(encoding="utf-8")
    lines_top = [line.strip() for line in content_top.splitlines() if line.strip()]
    # Expected order: index, timestamp, target text, source text
    assert lines_top[2] == "হ্যালো বিশ্ব"
    assert lines_top[3] == "Hello world"
