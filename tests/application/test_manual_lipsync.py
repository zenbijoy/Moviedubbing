"""
Unit tests for ManualLipSyncService.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidub.application.lipsync.manual_lipsync import ManualLipSyncService
from aidub.domain.viseme import (
    VisemeGroup,
    VisemeKeyframe,
    VisemeTimeline,
)


def test_manual_lipsync_nudge_and_itu() -> None:
    service = ManualLipSyncService()

    timeline = VisemeTimeline(
        utterance_id="utt_10",
        duration_s=2.0,
        keyframes=[
            VisemeKeyframe(viseme=VisemeGroup.BILABIAL, start_s=0.0, end_s=0.4),
            VisemeKeyframe(viseme=VisemeGroup.OPEN_VOWEL, start_s=0.4, end_s=1.2),
            VisemeKeyframe(viseme=VisemeGroup.SILENCE, start_s=1.2, end_s=2.0),
        ],
    )
    service.register_timeline(timeline)

    # Initial state is 0.0ms -> compliant
    compliant, msg, offset = service.evaluate_compliance("utt_10")
    assert compliant
    assert offset == 0.0

    # Nudge +33ms (1 frame)
    new_offset = service.nudge_offset("utt_10", 33.0)
    assert new_offset == 33.0
    compliant, _, _ = service.evaluate_compliance("utt_10")
    assert compliant

    # Nudge another +20ms -> 53ms (> 45ms lead) -> Non-compliant
    service.nudge_offset("utt_10", 20.0)
    compliant, msg, offset = service.evaluate_compliance("utt_10")
    assert not compliant
    assert "Audio Leads Video" in msg


def test_manual_lipsync_override_and_tier() -> None:
    service = ManualLipSyncService()
    timeline = VisemeTimeline(
        utterance_id="utt_20",
        duration_s=1.5,
        keyframes=[
            VisemeKeyframe(viseme=VisemeGroup.OPEN_VOWEL, start_s=0.0, end_s=1.5),
        ],
    )
    service.register_timeline(timeline)

    # Override at t=0.5s to LABIODENTAL
    kf = service.override_viseme("utt_20", 0.5, VisemeGroup.LABIODENTAL)
    assert kf is not None
    assert kf.viseme == VisemeGroup.LABIODENTAL
    assert kf.is_manual_override

    # Quality tier selection
    tier = service.set_quality_tier("utt_20", "Cinema Tier (LatentSync)")
    assert tier == "cinema"
    assert timeline.quality_tier == "cinema"

    # Shot eligibility
    assert service.set_shot_eligibility("utt_20", False) is False
    assert not timeline.shot_eligible_for_lipsync


def test_manual_lipsync_export_mocap(tmp_path: Path) -> None:
    service = ManualLipSyncService()
    timeline = VisemeTimeline(
        utterance_id="utt_30",
        duration_s=1.0,
        keyframes=[
            VisemeKeyframe(viseme=VisemeGroup.BILABIAL, start_s=0.0, end_s=0.5),
            VisemeKeyframe(viseme=VisemeGroup.OPEN_VOWEL, start_s=0.5, end_s=1.0),
        ],
    )
    service.register_timeline(timeline)

    out_file = tmp_path / "mocap_test.json"
    exported = service.export_mocap_json("utt_30", out_file)
    assert exported.exists()

    with open(exported, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["utterance_id"] == "utt_30"
    assert len(data["keyframes"]) == 2
    assert "geometry" in data["keyframes"][0]
