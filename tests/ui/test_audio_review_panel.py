"""Unit tests for AudioReviewDialog."""

from __future__ import annotations

import os

import pytest

from aidub.contracts.base import Identifier

os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtWidgets import QApplication

    from aidub.ui.dialogs.audio_review_panel import AudioReviewDialog

    _QT = True
except ImportError:
    _QT = False


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def mock_qmessagebox(monkeypatch: pytest.MonkeyPatch) -> None:
    if _QT:
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
        monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)


@pytest.mark.skipif(not _QT, reason="PySide6 is not available")
def test_audio_review_dialog_initialization(qapp: QApplication) -> None:
    dlg = AudioReviewDialog()
    assert dlg.windowTitle() == "Professional Dialogue Audio Review & QC Panel"
    assert dlg.tbl_cues.rowCount() >= 2
    assert dlg._current_cue is not None
    dlg.close()


@pytest.mark.skipif(not _QT, reason="PySide6 is not available")
def test_audio_review_dialog_cue_selection(qapp: QApplication) -> None:
    dlg = AudioReviewDialog()
    # Select second row
    dlg.tbl_cues.selectRow(1)
    dlg._on_cue_selected()
    assert dlg._current_cue is not None
    assert dlg._current_cue.cue_id == Identifier("cue_02")
    assert "রক্তিম সূর্য" in dlg.lbl_target_text.text()
    dlg.close()


@pytest.mark.skipif(not _QT, reason="PySide6 is not available")
def test_audio_review_dialog_qc_and_autofit(qapp: QApplication) -> None:
    dlg = AudioReviewDialog()
    dlg.tbl_cues.selectRow(0)
    dlg._on_cue_selected()

    # Run QC
    dlg._run_qc_on_current_cue()
    assert "QC Status:" in dlg.lbl_qc_status.text()

    # Trigger Auto-fit
    initial_candidates_count = len(dlg._current_cue.candidate_takes)
    dlg._autofit_duration_current_cue()
    assert len(dlg._current_cue.candidate_takes) == initial_candidates_count + 1
    dlg.close()


@pytest.mark.skipif(not _QT, reason="PySide6 is not available")
def test_audio_review_dialog_approval_and_rejection(qapp: QApplication) -> None:
    dlg = AudioReviewDialog()
    dlg.tbl_cues.selectRow(0)
    dlg._on_cue_selected()

    dlg._approve_current_take()
    assert dlg._current_cue.validation_status == "validated"

    dlg._reject_current_take()
    active_take = next(t for t in dlg._current_cue.candidate_takes if t.take_id == dlg._current_cue.selected_take_id)
    assert active_take.is_rejected is True
    dlg.close()
