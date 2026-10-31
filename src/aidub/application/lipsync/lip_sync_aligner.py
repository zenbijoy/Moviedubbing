"""
Lip-sync phoneme-to-viseme alignment engine with Bengali & English multimodal support.
Maps ASR phoneme events and Bengali orthography to Disney/MPEG-4 facial viseme timelines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aidub.application.bangla.g2p import BanglaG2P
from aidub.domain.viseme import VisemeGroup, VisemeKeyframe, VisemeTimeline

VISEME_MAP: dict[str, str] = {
    # English & Latin IPA
    "p": "BMP", "b": "BMP", "m": "BMP",
    "f": "FV", "v": "FV",
    "t": "TDNL", "d": "TDNL", "n": "TDNL", "l": "TDNL", "r": "TDNL",
    "k": "GK", "g": "GK", "ng": "GK",
    "s": "SZ", "z": "SZ", "sh": "CH_SH", "ch": "CH_SH", "j": "SZ",
    "th": "TH", "dh": "TH",
    "a": "AA", "aa": "AA", "ae": "AA",
    "e": "E", "eh": "E", "ey": "E",
    "i": "I", "ih": "I", "iy": "I",
    "o": "O", "ow": "O", "aw": "O",
    "u": "U", "uw": "U", "uh": "U",
}


@dataclass
class VisemeEvent:
    viseme: str
    start_s: float
    end_s: float


class LipSyncAligner:
    """
    Multilingual lip-sync alignment engine.
    Maps acoustic phoneme boundaries or Bengali dialogue text into frame-accurate visemes.
    """

    @staticmethod
    def phoneme_to_viseme(phoneme: str) -> str:
        """Converts Latin or phonetic notation to a standardized facial viseme."""
        ph = phoneme.lower().strip()
        # Check standard Latin map
        if ph in VISEME_MAP:
            return VISEME_MAP[ph]
        # Check Bangla char
        if ph:
            return BanglaG2P.char_to_viseme(ph[0])
        return "REST"

    @classmethod
    def align(cls, phonemes: list[tuple[str, float, float]]) -> list[VisemeEvent]:
        """Aligns a sequence of (phoneme, start_s, end_s) tuples into VisemeEvents."""
        out: list[VisemeEvent] = []
        for ph, s, e in phonemes:
            v = cls.phoneme_to_viseme(ph)
            out.append(VisemeEvent(viseme=v, start_s=s, end_s=e))
        return out

    @classmethod
    def align_bangla_dialogue(
        cls,
        text: str,
        start_s: float,
        end_s: float,
        utterance_id: str = "utt_001",
    ) -> VisemeTimeline:
        """
        Converts Bengali dialogue text into a complete VisemeTimeline with blendshape keyframes.
        """
        _G2P_TO_GROUP = {
            "BMP": VisemeGroup.BILABIAL,
            "PP": VisemeGroup.BILABIAL,
            "FV": VisemeGroup.LABIODENTAL,
            "TDNL": VisemeGroup.DENTAL_ALVEOLAR,
            "SZ": VisemeGroup.DENTAL_ALVEOLAR,
            "CH": VisemeGroup.VELAR_PALATAL,
            "CH_SH": VisemeGroup.VELAR_PALATAL,
            "KG": VisemeGroup.VELAR_PALATAL,
            "GK": VisemeGroup.VELAR_PALATAL,
            "AA": VisemeGroup.OPEN_VOWEL,
            "O": VisemeGroup.ROUNDED_VOWEL,
            "U": VisemeGroup.ROUNDED_VOWEL,
            "I": VisemeGroup.SPREAD_VOWEL,
            "E": VisemeGroup.SPREAD_VOWEL,
            "REST": VisemeGroup.SILENCE,
            "SIL": VisemeGroup.SILENCE,
        }

        events = BanglaG2P.align_sentence_timing(text, start_s, end_s)
        timeline = VisemeTimeline(utterance_id=utterance_id, duration_s=max(0.1, end_s - start_s))

        for v_name, st, et in events:
            group = _G2P_TO_GROUP.get(v_name.upper(), VisemeGroup.SILENCE)
            timeline.add_keyframe(
                VisemeKeyframe(
                    viseme=group,
                    start_s=st,
                    end_s=et,
                )
            )

        return timeline


__all__ = ["VisemeEvent", "LipSyncAligner", "VISEME_MAP"]
