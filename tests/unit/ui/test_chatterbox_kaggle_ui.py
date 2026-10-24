"""Unit tests for Voice Model Dialog, Kaggle Accelerator Dialog, and NLE Shortcuts."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog
from aidub.ui.dialogs.voice_model_dialog import VoiceModelDialog
from aidub.ui.screens.timeline_editor import TimelineScreen


def test_voice_model_dialog_options() -> None:
    app = QApplication.instance() or QApplication([])
    dlg = VoiceModelDialog(current_engine="chatterbox", target_language="bn")
    try:
        assert dlg.get_selected_engine() == "chatterbox"
        assert dlg.get_selected_emotion() == "neutral"

        dlg.engine_combo.setCurrentIndex(1)
        assert dlg.get_selected_engine() == "edge_tts"

        dlg.emo_combo.setCurrentText("Joy")
        assert dlg.get_selected_emotion() == "joy"
    finally:
        dlg.close()
        app.processEvents()


def test_kaggle_accelerator_dialog_exports_notebook(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    dlg = KaggleAcceleratorDialog(
        movie_path="test_inception_clip.mp4",
        target_language="bn",
        voice_engine="chatterbox",
        enable_lipsync=True,
    )
    try:
        dest_ipynb = tmp_path / "dubbing_kaggle.ipynb"
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(dest_ipynb), "")):
            with patch("PySide6.QtWidgets.QMessageBox.information"):
                dlg._generate_notebook()

        assert dest_ipynb.is_file()
        assert dest_ipynb.stat().st_size > 500
    finally:
        dlg.close()
        app.processEvents()


def test_timeline_screen_kaggle_and_voice_shortcuts() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Verify stage bar buttons exist
        assert hasattr(screen.stage_bar, "kaggle_requested")
        assert hasattr(screen.stage_bar, "voice_model_requested")

        # Test Space key press delegates to play/pause
        with patch.object(screen.monitor_panel, "_toggle_play") as mock_play:
            space_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
            screen.keyPressEvent(space_ev)
            mock_play.assert_called_once()

        # Test Ctrl+K triggers _open_kaggle_accelerator
        with patch.object(screen, "_open_kaggle_accelerator") as mock_kaggle:
            k_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
            screen.keyPressEvent(k_ev)
            mock_kaggle.assert_called_once()

        # Test Ctrl+D triggers _run_agentic_dub
        with patch.object(screen, "_run_agentic_dub") as mock_dub:
            d_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
            screen.keyPressEvent(d_ev)
            mock_dub.assert_called_once()
    finally:
        screen.close()
        app.processEvents()

