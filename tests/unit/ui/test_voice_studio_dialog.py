"""Unit tests for VoiceStudioDialog UI tabs, controls, and consent gate."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from aidub.ui.dialogs.voice_studio_dialog import VoiceStudioDialog

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


@pytest.mark.skipif(not _QT, reason="PySide6 is required for UI tests")
def test_voice_studio_dialog_initialization(qapp: QApplication) -> None:
    dlg = VoiceStudioDialog()
    assert dlg.tabs.count() == 5

    tab_titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert any("Voice Library" in t for t in tab_titles)
    assert any("Voice Design" in t for t in tab_titles)
    assert any("Authorized Voice Cloning" in t for t in tab_titles)
    assert any("Multi-Speaker Dialogue" in t for t in tab_titles)
    assert any("Audio Quality" in t for t in tab_titles)

    # Clean up
    dlg.close()


@pytest.mark.skipif(not _QT, reason="PySide6 is required for UI tests")
def test_voice_studio_consent_gate(qapp: QApplication) -> None:
    dlg = VoiceStudioDialog()

    # On Tab 3 (Cloning), generate button must be disabled until consent checkbox is checked
    assert dlg.clone_generate_btn.isEnabled() is False

    dlg.consent_checkbox.setChecked(True)
    assert dlg.clone_generate_btn.isEnabled() is True

    dlg.consent_checkbox.setChecked(False)
    assert dlg.clone_generate_btn.isEnabled() is False

    dlg.close()


@pytest.mark.skipif(not _QT, reason="PySide6 is required for UI tests")
def test_voice_studio_dialogue_table_controls(qapp: QApplication) -> None:
    dlg = VoiceStudioDialog()

    initial_rows = dlg.dialogue_table.rowCount()
    assert initial_rows >= 3

    dlg._add_dialogue_turn()
    assert dlg.dialogue_table.rowCount() == initial_rows + 1

    dlg.dialogue_table.setCurrentCell(initial_rows, 0)
    dlg._remove_dialogue_turn()
    assert dlg.dialogue_table.rowCount() == initial_rows

    dlg.close()
