"""
Unit tests for LipSyncVisemeEngine and LipSyncInspectorDialog (Feature 3).
"""

from __future__ import annotations

import pytest

from aidub.media.lipsync_viseme_engine import (
    LipSyncVisemeEngine,
    VisemeGeometry,
    VisemeGroup,
)

try:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    _QT = True
except ImportError:
    _QT = False


@pytest.fixture(scope="session")
def qapp() -> QApplication | None:
    if not _QT:
        return None
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_viseme_timeline_generation_bengali() -> None:
    text = "বন্ধু কথা বলতে আসছিল"
    cues = LipSyncVisemeEngine.generate_viseme_timeline(text, start_time_s=1.0, duration_s=2.5, language="bn")

    assert len(cues) >= 3
    # Check start and end boundaries
    assert cues[0].start_s == pytest.approx(1.0, abs=0.01)
    assert cues[-1].end_s == pytest.approx(3.5, abs=0.01)

    viseme_groups = {c.viseme for c in cues}
    # Should include bilabial for 'ব'/'ম' and dental for 'থ'/'স'
    assert VisemeGroup.BILABIAL in viseme_groups or VisemeGroup.DENTAL_ALVEOLAR in viseme_groups


def test_viseme_timeline_generation_english() -> None:
    text = "Peter bought five apples"
    cues = LipSyncVisemeEngine.generate_viseme_timeline(text, start_time_s=0.0, duration_s=2.0, language="en")

    assert len(cues) >= 3
    viseme_groups = {c.viseme for c in cues}
    assert VisemeGroup.BILABIAL in viseme_groups  # Peter, bought
    assert VisemeGroup.LABIODENTAL in viseme_groups  # five


def test_lip_sync_compliance_itu_r_bt1359() -> None:
    text = "Synchronized dialogue test"
    cues = LipSyncVisemeEngine.generate_viseme_timeline(text, start_time_s=0.0, duration_s=1.5, language="en")

    # 1. Perfect 0ms alignment
    rep_0 = LipSyncVisemeEngine.evaluate_lip_sync_compliance(cues, offset_ms=0.0)
    assert rep_0.is_broadcast_compliant is True
    assert rep_0.compliance_score == 1.0
    assert rep_0.lead_lag_status == "In Sync"

    # 2. Tolerable audio lag (+30ms within +125ms ITU-R window)
    rep_lag30 = LipSyncVisemeEngine.evaluate_lip_sync_compliance(cues, offset_ms=30.0)
    assert rep_lag30.is_broadcast_compliant is True
    assert rep_lag30.compliance_score > 0.85

    # 3. Severe audio lead (-120ms exceeds -45ms threshold)
    rep_lead120 = LipSyncVisemeEngine.evaluate_lip_sync_compliance(cues, offset_ms=-120.0)
    assert rep_lead120.is_broadcast_compliant is False
    assert rep_lead120.lead_lag_status == "Audio Leading Video"
    assert rep_lead120.compliance_score < 0.50

    # 4. Severe audio lag (+250ms exceeds +125ms threshold)
    rep_lag250 = LipSyncVisemeEngine.evaluate_lip_sync_compliance(cues, offset_ms=250.0)
    assert rep_lag250.is_broadcast_compliant is False
    assert rep_lag250.lead_lag_status == "Audio Lagging Video"
    assert rep_lag250.compliance_score < 0.50


def test_interpolate_mouth_geometry() -> None:
    text = "Open mouth vowel test"
    cues = LipSyncVisemeEngine.generate_viseme_timeline(text, start_time_s=0.0, duration_s=1.0, language="en")

    geom = LipSyncVisemeEngine.interpolate_mouth_geometry(cues, playhead_s=0.5)
    assert isinstance(geom, VisemeGeometry)
    assert 0.0 <= geom.openness <= 1.0
    assert 0.0 <= geom.width <= 1.0
    assert 0.0 <= geom.lip_protrusion <= 1.0


@pytest.mark.skipif(not _QT, reason="PySide6 required for UI dialog testing")
def test_lipsync_inspector_dialog_lifecycle(qapp: QApplication | None) -> None:
    from aidub.ui.dialogs.lipsync_inspector_dialog import LipSyncInspectorDialog

    dialog = LipSyncInspectorDialog(
        utterance_index=2,
        dialogue_text="এটি লিপ-সিঙ্ক পরীক্ষার বাক্য",
        duration_s=2.4,
        language="bn",
    )

    # Initial state
    assert dialog.utterance_index == 2
    assert dialog.compliance_bar.value() == 100
    assert dialog._current_offset_ms == 0.0

    # Slip slider test
    dialog.slip_slider.setValue(45)
    assert dialog._current_offset_ms == 45.0
    assert "45.0 ms" in dialog.lbl_slider_val.text()

    # Nudge button test (-33ms)
    dialog.btn_nudge_left.click()
    assert dialog.slip_slider.value() == 12

    # Reset button test
    dialog.btn_reset_slip.click()
    assert dialog.slip_slider.value() == 0

    # Signal emission test on Apply
    received_signals = []
    dialog.offset_applied.connect(lambda idx, off: received_signals.append((idx, off)))
    dialog._current_offset_ms = 33.0
    dialog._on_apply_offset()

    assert len(received_signals) == 1
    assert received_signals[0] == (2, pytest.approx(0.033, abs=0.001))
    dialog.close()
