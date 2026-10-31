from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtMultimedia import QAudioDevice, QMediaDevices
from PySide6.QtWidgets import QApplication

from aidub.ui.dub_dialog import DubbingErrorDialog, DubDialog
from aidub.ui.screens.timeline_editor import TimelineScreen
from aidub.ui.studio_window import AIDubStudioWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_crash_guard_runs_without_audio_when_no_audio_outputs(qapp: QApplication) -> None:
    """Task 1: Verify that when QMediaDevices.audioOutputs() is empty,

    the crash guard prevents QAudioOutput creation, sets _audio_output to None,
    and runs the player without audio output while notifying the user.
    """
    with patch.object(QMediaDevices, "audioOutputs", return_value=[]):
        screen = TimelineScreen()
        try:
            assert screen.monitor_panel._audio_output is None
            assert screen.monitor_panel._player is not None
            # Verify take audio output also handles empty audio outputs gracefully
            assert getattr(screen, "_take_audio_output", None) is None
        finally:
            screen.close()
            qapp.processEvents()


def test_crash_guard_creates_audio_output_when_devices_present(qapp: QApplication) -> None:
    """Verify that when audio output devices are present, QAudioOutput is initialized normally."""
    mock_device = MagicMock(spec=QAudioDevice)
    mock_device.isNull.return_value = False

    with patch.object(QMediaDevices, "audioOutputs", return_value=[mock_device]):
        screen = TimelineScreen()
        try:
            assert screen.monitor_panel._audio_output is not None
            assert screen.monitor_panel._player is not None
        finally:
            screen.close()
            qapp.processEvents()


def test_dub_dialog_defaults_to_bengali_and_quality_profile(qapp: QApplication) -> None:
    """Task 2: DubDialog must default to Bengali ('bn') and Quality profile."""
    dialog = DubDialog()
    try:
        lang, profile = dialog.get_settings()
        assert lang == "bn"
        assert profile == "quality"
        assert "Bengali" in dialog.lang_combo.currentText()

        # Change profile to Fast
        dialog.fast_radio.setChecked(True)
        assert dialog.get_settings() == ("bn", "fast")

        # Change language to index 1 (Hindi)
        dialog.lang_combo.setCurrentIndex(1)
        lang2, profile2 = dialog.get_settings()
        assert lang2 == "hi"
        assert profile2 == "fast"
    finally:
        dialog.close()
        qapp.processEvents()


def test_dubbing_error_dialog_copy_details(qapp: QApplication) -> None:
    """Task 2: Readable error dialog with working 'Copy details' button."""
    test_title = "Engine Dubbing Failed"
    test_msg = "ASR worker encountered an out-of-memory error."
    test_details = "Traceback (most recent call last):\n  File 'pipeline.py', line 42\nMemoryError"

    dialog = DubbingErrorDialog(
        title=test_title,
        message=test_msg,
        details=test_details,
    )
    try:
        assert dialog.windowTitle() == test_title
        assert dialog.msg_lbl.text() == test_msg
        assert dialog.details_edit.toPlainText() == test_details

        # Clear clipboard first
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.clear()

        # Click copy button
        dialog.copy_btn.click()
        qapp.processEvents()

        # Check clipboard content
        if clipboard is not None:
            assert clipboard.text() == test_details
        assert "Copied" in dialog.copy_btn.text()
    finally:
        dialog.close()
        qapp.processEvents()


def test_no_fake_numbers_scores_and_metrics_show_not_measured(qapp: QApplication) -> None:
    """Task 3: Scores and metrics must display 'Not measured' until a real job produces them."""
    screen = TimelineScreen()
    try:
        # Simulate dubbing completion without explicit lip sync metrics
        screen._on_dubbing_completed({"status": "completed"})
        assert screen.inspector_panel.l_score_lbl.text() == "Lip Sync:  Not measured"

        # Update clip info with score=None -> must show Not measured
        screen.inspector_panel.update_clip_info(
            char_name="Hero",
            lang="bn",
            orig_text="Original text",
            trans_text="অনুবাদ পাঠ্য",
            score=None,
        )
        assert screen.inspector_panel.v_score_lbl.text() == "Voice:     Not measured"
    finally:
        screen.close()
        qapp.processEvents()


def test_studio_window_dub_toolbar_and_progress_integration(qapp: QApplication) -> None:
    """Task 2: Studio window toolbar contains Dub action, Cancel action,

    and progress controls that reflect active job stages.
    """
    window = AIDubStudioWindow()
    try:
        assert hasattr(window, "dub_action")
        assert hasattr(window, "cancel_action")
        assert hasattr(window, "toolbar_progress_bar")
        assert hasattr(window, "toolbar_stage_label")

        # Initial state: Cancel is disabled, Dub is enabled, progress bar is hidden
        assert not window.cancel_action.isEnabled()
        assert window.dub_action.isEnabled()
        assert window.toolbar_progress_bar.isHidden()

        # Update progress during running job
        window.update_dub_progress("TRANSLATE", 45, "Translating subtitles to Bengali...")
        assert window.cancel_action.isEnabled()
        assert not window.toolbar_progress_bar.isHidden()
        assert window.toolbar_progress_bar.value() == 45
        assert "TRANSLATE" in window.toolbar_stage_label.text()

        # Finish job
        window.set_dub_completed(True, "Dubbing completed successfully.")
        assert not window.cancel_action.isEnabled()
        assert window.dub_action.isEnabled()
        assert window.toolbar_progress_bar.value() == 100
    finally:
        window.close()
        qapp.processEvents()
