"""
Unit tests for domain viseme models, timelines, and ITU-R BT.1359 compliance.
"""

from __future__ import annotations

import pytest

from aidub.domain.viseme import (
    VISEME_GEOMETRIES,
    VisemeGeometry,
    VisemeGroup,
    VisemeKeyframe,
    VisemeTimeline,
)


def test_viseme_keyframe_and_geometry() -> None:
    kf = VisemeKeyframe(
        viseme=VisemeGroup.BILABIAL,
        start_s=0.5,
        end_s=0.8,
    )
    assert kf.duration_s == pytest.approx(0.3)
    assert kf.label == "BILA"
    assert kf.geometry.openness == 0.0  # Bilabial mouth is closed
    assert not kf.is_manual_override


def test_viseme_timeline_nudge_and_itu_compliance() -> None:
    timeline = VisemeTimeline(
        utterance_id="utt_001",
        duration_s=2.0,
        keyframes=[
            VisemeKeyframe(viseme=VisemeGroup.SILENCE, start_s=0.0, end_s=0.2),
            VisemeKeyframe(viseme=VisemeGroup.OPEN_VOWEL, start_s=0.2, end_s=0.8),
            VisemeKeyframe(viseme=VisemeGroup.LABIODENTAL, start_s=0.8, end_s=1.5),
            VisemeKeyframe(viseme=VisemeGroup.SILENCE, start_s=1.5, end_s=2.0),
        ],
    )

    # Initially 0ms offset -> compliant
    compliant, status, offset = timeline.evaluate_itu_compliance()
    assert compliant
    assert offset == 0.0

    # Query viseme at t = 0.5s -> OPEN_VOWEL
    kf = timeline.get_viseme_at(0.5)
    assert kf is not None
    assert kf.viseme == VisemeGroup.OPEN_VOWEL

    # Manual override at t = 0.5s to BILABIAL
    overridden = timeline.override_viseme_at(0.5, VisemeGroup.BILABIAL)
    assert overridden is not None
    assert overridden.viseme == VisemeGroup.BILABIAL
    assert overridden.is_manual_override

    # Nudge offset +33ms (1 frame at 30fps)
    timeline.nudge_offset(33.0)
    compliant, status, offset = timeline.evaluate_itu_compliance()
    assert compliant
    assert offset == 33.0

    # Nudge to +80ms (> +45ms audio lead limit)
    timeline.nudge_offset(50.0)
    compliant, status, offset = timeline.evaluate_itu_compliance()
    assert not compliant
    assert "Audio Leads Video" in status

    # Nudge negative to -150ms (< -125ms audio lag limit)
    timeline.lead_lag_offset_ms = -150.0
    compliant, status, offset = timeline.evaluate_itu_compliance()
    assert not compliant
    assert "Audio Lags Video" in status

    # Export to mocap dictionary
    mocap = timeline.to_mocap_dict()
    assert mocap["utterance_id"] == "utt_001"
    assert mocap["keyframe_count"] == 4
    assert len(mocap["keyframes"]) == 4
    assert "geometry" in mocap["keyframes"][0]
