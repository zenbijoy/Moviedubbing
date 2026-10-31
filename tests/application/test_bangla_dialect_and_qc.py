"""Unit tests for Bangla Dialects, Emotion Classifier (PAD vectors), and Subtitle QC."""

from __future__ import annotations

import pytest

from aidub.application.bangla.dialect_presets import BanglaDialectManager
from aidub.application.bangla.emotion_classifier import BanglaEmotionClassifier
from aidub.application.bangla.subtitle_qc import BanglaSubtitleQC, SubtitleIssue


def test_bangla_dialect_presets_and_adaptation() -> None:
    mgr = BanglaDialectManager()
    profiles = mgr.list_dialects()
    assert len(profiles) >= 5
    assert "dhaka_standard" in profiles
    assert "chittagong" in profiles
    assert "sylhet" in profiles
    assert "barisal" in profiles
    assert "classic_sadhu" in profiles

    # Chittagong dialect word adaptations
    ctg = mgr.adapt_text("তুমি কোথায় যাচ্ছ?", "chittagong")
    assert "তুঁই" in ctg
    assert "হণ্ডে" in ctg

    # Sylhet dialect adaptations
    syl = mgr.adapt_text("তুমি কোথায় আছো এবং ভালো আছো?", "sylhet")
    assert "খুনো" in syl
    assert "ভালা" in syl

    # Sadhu dialect adaptations
    sadhu = mgr.adapt_text("আমি এই কাজ করছি।", "classic_sadhu")
    assert "করিতেছি" in sadhu


def test_bangla_emotion_classifier_pad_vectors() -> None:
    clf = BanglaEmotionClassifier()

    # Joy
    res_joy = clf.classify_text("আমি অনেক আনন্দিত ও খুশি!")
    assert res_joy.primary_emotion == "joy"
    assert res_joy.pleasure > 0.0
    assert res_joy.ssml_style == "cheerful"

    # Anger
    res_anger = clf.classify_text("এটা মারাত্মক অন্যায়, আমি খুব রেগে গেছি!")
    assert res_anger.primary_emotion == "anger"
    assert res_anger.pleasure < 0.0
    assert res_anger.arousal > 0.0
    assert res_anger.ssml_style == "angry"

    # Sorrow
    res_sorrow = clf.classify_text("আমার মন খুব খারাপ ও দুঃখজনকভাবে ভেঙে গেছে।")
    assert res_sorrow.primary_emotion in ("sadness", "sorrow")
    assert res_sorrow.pleasure < 0.0
    assert res_sorrow.dominance < 0.0
    assert res_sorrow.ssml_style == "sad"


def test_bangla_subtitle_qc_auditing_and_autofix() -> None:
    qc = BanglaSubtitleQC()

    # Normal clean line passes
    clean_line = "আমি কালকে যাব।"
    issues = qc.check_line(clean_line, duration_sec=2.0)
    assert len(issues) == 0

    # Western period triggers info/warning
    period_line = "আমি কালকে যাব."
    issues = qc.check_line(period_line, duration_sec=2.0)
    assert any("দাঁড়ি" in i.message or "Dari" in i.message for i in issues)

    # Auto-fix fixes period to Dari
    fixed = qc.auto_fix(period_line)
    assert fixed.endswith("।")
    assert "." not in fixed

    # Excessively fast reading speed (CPS > 18)
    fast_text = "এটি একটি অত্যন্ত দীর্ঘ বাক্য যা অত্যন্ত দ্রুত কথা বলা হয়েছে এবং দর্শকের পক্ষে এটি পড়া অসম্ভব।"
    issues = qc.check_line(fast_text, duration_sec=1.0)
    assert any("CPS" in i.message or "পড়ার গতি" in i.message for i in issues)
