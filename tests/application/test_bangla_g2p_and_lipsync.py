"""Unit tests for Bengali G2P and Phoneme-to-Viseme Lip-Sync Alignment."""

from __future__ import annotations

import pytest

from aidub.application.bangla.g2p import BanglaG2P
from aidub.application.lipsync.lip_sync_aligner import LipSyncAligner
from aidub.domain.viseme import VisemeGroup, VisemeKeyframe, VisemeTimeline


def test_bangla_g2p_char_viseme_mapping() -> None:
    g2p = BanglaG2P()
    # Bilabial plosives
    for ch in ["প", "ফ", "ব", "ভ", "ম"]:
        assert g2p.char_to_viseme(ch) == "BMP"
    # Open vowels
    assert g2p.char_to_viseme("আ") == "AA"
    assert g2p.char_to_viseme("া") == "AA"
    # Rounded vowels
    assert g2p.char_to_viseme("উ") == "U"
    assert g2p.char_to_viseme("ু") == "U"
    assert g2p.char_to_viseme("ও") == "O"
    assert g2p.char_to_viseme("ো") == "O"
    # Alveolar sibilants
    assert g2p.char_to_viseme("স") == "SZ"
    assert g2p.char_to_viseme("শ") == "CH_SH"
    # Punctuation/silence
    assert g2p.char_to_viseme("।") == "REST"
    assert g2p.char_to_viseme(" ") == "REST"


def test_bangla_g2p_text_to_visemes() -> None:
    g2p = BanglaG2P()
    visemes = g2p.text_to_visemes("আমি তোমাকে ভালোবাসি।")
    assert len(visemes) > 0
    # Must contain speech visemes and silence at the end
    assert "AA" in visemes
    assert "BMP" in visemes  # from ভ/ব/ম
    assert "REST" in visemes


def test_bangla_g2p_align_sentence_timing() -> None:
    g2p = BanglaG2P()
    total_dur = 2.5
    timed = g2p.align_sentence_timing("তুমি কেমন আছো?", start_s=0.0, end_s=total_dur)
    assert len(timed) > 0
    # First begins at 0.0, last ends at total_dur
    assert timed[0][1] == 0.0
    assert pytest.approx(timed[-1][2], abs=0.01) == total_dur
    # Monotonically increasing intervals
    for i in range(len(timed) - 1):
        assert timed[i][1] < timed[i][2]
        assert pytest.approx(timed[i][2], abs=0.01) == timed[i + 1][1]


def test_lip_sync_aligner_bangla_dialogue() -> None:
    aligner = LipSyncAligner()
    timeline = aligner.align_bangla_dialogue(
        text="হ্যালো, কেমন আছেন?",
        start_s=0.0,
        end_s=2.0,
        utterance_id="utt_bn_001",
    )
    assert isinstance(timeline, VisemeTimeline)
    assert timeline.duration_s == 2.0
    assert len(timeline.keyframes) > 5
    # Check keyframe structure
    kf = timeline.keyframes[0]
    assert isinstance(kf, VisemeKeyframe)
    assert 0.0 <= kf.start_s <= 2.0
    assert isinstance(kf.viseme, VisemeGroup)
