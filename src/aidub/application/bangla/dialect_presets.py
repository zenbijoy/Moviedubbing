"""
Bangla Regional Dialect & Accent Presets for Movie Dubbing.
Provides phonetic and prosodic rules for Dhaka, Chittagong, Sylhet, Barisal, and Standard Sadhu.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DialectProfile:
    dialect_id: str
    display_name_bn: str
    display_name_en: str
    pitch_scale: float  # Pitch shift factor
    rate_scale: float   # Speaking rate factor
    prosody_intonation: str  # Intonation curve descriptor
    formant_tilt_db: float  # EQ warmth / chest resonance
    lexical_substitutions: dict[str, str]  # Common regional dialect vocabulary shifts

    @property
    def speaking_rate_scale(self) -> float:
        return self.rate_scale

    @property
    def pitch_semitones(self) -> float:
        return round((self.pitch_scale - 1.0) * 12.0, 1)

    @property
    def prosody_description(self) -> str:
        return self.prosody_intonation


class BanglaDialectManager:
    """Manages regional Bangladeshi dialect acoustic and lexical configurations."""

    DIALECTS: dict[str, DialectProfile] = {
        "dhaka_standard": DialectProfile(
            dialect_id="dhaka_standard",
            display_name_bn="ঢাকা প্রমিত চলিত",
            display_name_en="Dhaka Standard Colloquial",
            pitch_scale=1.0,
            rate_scale=1.0,
            prosody_intonation="standard_neutral",
            formant_tilt_db=0.0,
            lexical_substitutions={
                "কোথায়": "কই",
                "কীভাবে": "কেমনে",
                "কেন": "কেন",
            },
        ),
        "chittagong": DialectProfile(
            dialect_id="chittagong",
            display_name_bn="চট্টগ্রাম (চাঁটগাঁইয়া)",
            display_name_en="Chittagonian (Chatgaiya)",
            pitch_scale=1.05,
            rate_scale=0.95,
            prosody_intonation="sing_song_rising",
            formant_tilt_db=1.5,
            lexical_substitutions={
                "আমি": "আঁই",
                "তুমি": "তুঁই",
                "কোথায়": "হণ্ডে",
                "ভালো": "গম",
                "পানি": "পানি",
            },
        ),
        "sylhet": DialectProfile(
            dialect_id="sylhet",
            display_name_bn="সিলেটি",
            display_name_en="Sylheti",
            pitch_scale=0.98,
            rate_scale=1.08,
            prosody_intonation="spirantized_cadence",
            formant_tilt_db=-1.0,
            lexical_substitutions={
                "আমি": "আমি",
                "তুমি": "তুমি",
                "কোথায়": "খুনো",
                "পানি": "পানি",
                "ভালো": "ভালা",
            },
        ),
        "barisal": DialectProfile(
            dialect_id="barisal",
            display_name_bn="বরিশাইল্লা",
            display_name_en="Barisali",
            pitch_scale=1.02,
            rate_scale=1.02,
            prosody_intonation="rhythmic_lilt",
            formant_tilt_db=0.8,
            lexical_substitutions={
                "সে": "হ্যার",
                "কী": "কী",
                "কোথায়": "কই",
                "আমি": "মুই",
            },
        ),
        "classic_sadhu": DialectProfile(
            dialect_id="classic_sadhu",
            display_name_bn="ধ্রুপদী সাধু ভাষা",
            display_name_en="Classic Sadhu (Historical / Period Drama)",
            pitch_scale=0.95,
            rate_scale=0.90,
            prosody_intonation="authoritative_grave",
            formant_tilt_db=-2.0,
            lexical_substitutions={
                "বলছি": "বলিতেছি",
                "করছি": "করিতেছি",
                "তার": "তাহার",
            },
        ),
    }

    @classmethod
    def list_dialects(cls) -> list[str]:
        return list(cls.DIALECTS.keys())

    @classmethod
    def get_profile(cls, dialect_id: str) -> DialectProfile:
        return cls.DIALECTS.get(dialect_id, cls.DIALECTS["dhaka_standard"])

    @classmethod
    def adapt_dialogue_text(cls, text: str, dialect_id: str) -> str:
        """Substitutes standard Bengali words with regional dialect vocabulary."""
        profile = cls.get_profile(dialect_id)
        out = text
        for k, v in profile.lexical_substitutions.items():
            out = out.replace(k, v)
        return out

    adapt_text = adapt_dialogue_text


__all__ = ["BanglaDialectManager", "DialectProfile"]
