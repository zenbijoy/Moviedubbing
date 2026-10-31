"""
Bangla Dialogue Emotion Classifier for Film Dubbing.
Analyzes Bengali script semantics and returns emotional categories with 3D PAD vectors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aidub.application.voice.pro_emotion_engine import PADVector


@dataclass
class BanglaEmotionResult:
    emotion_bn: str
    emotion_en: str
    confidence: float
    pad: PADVector
    suggested_ssml_style: str

    @property
    def primary_emotion(self) -> str:
        return self.emotion_en.lower()

    @property
    def pleasure(self) -> float:
        return self.pad.valence

    @property
    def arousal(self) -> float:
        return self.pad.arousal

    @property
    def dominance(self) -> float:
        return self.pad.dominance

    @property
    def ssml_style(self) -> str:
        return self.suggested_ssml_style

    @property
    def intensity(self) -> float:
        return self.confidence


class BanglaEmotionClassifier:
    """Classifies the emotional intent of Bengali movie dialogue."""

    # Lexical indicator keywords for emotion detection
    EMOTION_KEYWORDS: dict[str, tuple[str, list[str], PADVector, str]] = {
        "anger": (
            "রাগ",
            ["খুন", "মারব", "ধ্বংস", "শয়তান", "মর", "চুপ", "হতভাগা", "ঘৃণা", "প্রতিশোধ", "বদমাশ", "রাগ", "রেগে", "অন্যায়", "অন্যায়"],
            PADVector(valence=-0.75, arousal=0.85, dominance=0.80),
            "angry",
        ),
        "joy": (
            "আনন্দ",
            ["খুশি", "আনন্দ", "আনন্দিত", "দারুণ", "ধন্যবাদ", "জিতে গেছি", "চমৎকার", "মিষ্টি", "হাসি", "উৎসব"],
            PADVector(valence=0.80, arousal=0.60, dominance=0.50),
            "cheerful",
        ),
        "sadness": (
            "দুঃখ",
            ["কান্না", "কষ্ট", "হারিয়ে", "মৃত্যু", "ক্ষমা", "একা", "ব্যথা", "অসহায়", "হতাশ", "খারাপ", "দুঃখ", "ভেঙে"],
            PADVector(valence=-0.80, arousal=0.20, dominance=-0.70),
            "sad",
        ),
        "fear": (
            "ভয়",
            ["বাঁচাও", "ভয়", "পালিয়ে", "বিপদ", "অন্ধকার", "আতঙ্ক", "সাহায্য", "কী হবে"],
            PADVector(valence=-0.70, arousal=0.80, dominance=-0.80),
            "terrified",
        ),
        "romance": (
            "প্রেম",
            ["ভালোবাসি", "প্রিয়", "হৃদয়", "চোখ", "স্বপ্ন", "চিরকাল", "জীবন", "কাছে"],
            PADVector(valence=0.75, arousal=0.35, dominance=0.0),
            "affectionate",
        ),
    }

    @classmethod
    def classify(cls, text: str) -> BanglaEmotionResult:
        """Classifies the emotion of a Bengali dialogue utterance."""
        clean_text = text.strip()
        if not clean_text:
            return BanglaEmotionResult(
                emotion_bn="শান্ত",
                emotion_en="Neutral",
                confidence=0.9,
                pad=PADVector(valence=0.0, arousal=0.35, dominance=0.0),
                suggested_ssml_style="neutral",
            )

        # Check for punctuation cues
        has_exclamation = "!" in clean_text
        has_question = "?" in clean_text

        best_emotion = "neutral"
        best_score = 0
        best_pad = PADVector(valence=0.0, arousal=0.35, dominance=0.0)
        best_bn = "শান্ত"
        best_style = "neutral"

        for emo_en, (emo_bn, keywords, pad, style) in cls.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in clean_text)
            if score > best_score:
                best_score = score
                best_emotion = emo_en
                best_bn = emo_bn
                best_pad = pad
                best_style = style

        # If exclamation mark is present with anger or joy, increase arousal
        if has_exclamation:
            best_pad.arousal = min(1.0, best_pad.arousal + 0.15)
        elif has_question:
            best_pad.arousal = min(1.0, best_pad.arousal + 0.08)

        confidence = 0.85 if best_score > 0 else 0.65
        return BanglaEmotionResult(
            emotion_bn=best_bn,
            emotion_en=best_emotion.title(),
            confidence=confidence,
            pad=best_pad,
            suggested_ssml_style=best_style,
        )

    classify_text = classify


__all__ = ["BanglaEmotionClassifier", "BanglaEmotionResult"]
