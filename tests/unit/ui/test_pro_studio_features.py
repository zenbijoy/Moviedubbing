"""Unit tests for Pro Studio Features: Character Casting, Broadcast Export, Colab, Split Monitor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from aidub.ui.dialogs.broadcast_export_dialog import BroadcastExportDialog
from aidub.ui.dialogs.character_casting_dialog import CharacterCastingStudioDialog
from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog
from aidub.ui.screens.timeline_editor import TimelineScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_character_casting_studio_dialog_lifecycle(qapp):
    dlg = CharacterCastingStudioDialog(
        characters=["Hero", "Villain", "Narrator"],
        current_casting={"Hero": "chatterbox_male_deep"},
        target_language="bn",
    )
    assert dlg.table.rowCount() == 3
    voices = dlg.get_character_voices()
    assert "Hero" in voices
    assert len(voices) == 3

    # Test auto match
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        dlg._auto_match_voices()

    # Test adding a row
    dlg._add_character_row()
    assert dlg.table.rowCount() == 4


def test_broadcast_export_dialog_presets(qapp, tmp_path: Path):
    vid = tmp_path / "vid.mp4"
    vid.write_bytes(b"vid")
    aud = tmp_path / "aud.wav"
    aud.write_bytes(b"aud")

    dlg = BroadcastExportDialog(
        video_path=str(vid),
        audio_path=str(aud),
    )
    assert dlg.preset_combo.count() >= 5

    # Check 1-Click Studio Master Bundle (Default Index 0)
    dlg.preset_combo.setCurrentIndex(0)
    assert "STUDIO MASTER" in dlg.spec_card.text().upper() or "C2PA" in dlg.spec_card.text().upper()

    # Find and select Netflix preset
    netflix_idx = -1
    for idx in range(dlg.preset_combo.count()):
        if "netflix" in dlg.preset_combo.itemText(idx).lower():
            netflix_idx = idx
            break
    assert netflix_idx >= 0
    dlg.preset_combo.setCurrentIndex(netflix_idx)
    assert "NETFLIX" in dlg.spec_card.text().upper()
    assert "-23.0 LUFS" in dlg.spec_card.text()


def test_cloud_accelerator_dialog_colab_support(qapp, tmp_path: Path):
    movie = tmp_path / "scene.mp4"
    movie.write_bytes(b"movie")

    dlg = KaggleAcceleratorDialog(
        movie_path=str(movie),
        target_language="bn",
        voice_engine="chatterbox",
    )

    assert hasattr(dlg, "colab_btn")
    assert hasattr(dlg, "_generate_colab_notebook")

    out_ipynb = tmp_path / "test_colab.ipynb"
    with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(out_ipynb), "")), \
         patch("PySide6.QtWidgets.QMessageBox.information"):
        dlg._generate_colab_notebook()

    assert out_ipynb.is_file()


def test_program_monitor_split_screen_mode(qapp):
    screen = TimelineScreen()
    monitor = screen.monitor_panel

    assert hasattr(monitor, "toggle_split_view")
    assert hasattr(monitor, "load_comparison_media")
    assert not monitor._split_mode

    # Toggle split mode on
    monitor.toggle_split_view(True)
    assert monitor._split_mode
    if monitor._split_btn is not None:
        assert monitor._split_btn.isChecked()

    # Simulate fake frame and update surface without crashing
    fake_frame = QImage(320, 240, QImage.Format.Format_RGB32)
    fake_frame.fill(Qt.GlobalColor.blue)
    monitor._last_video_image = fake_frame
    monitor._update_video_surface()

    # Toggle split off
    monitor.toggle_split_view(False)
    assert not monitor._split_mode
    monitor._update_video_surface()


def test_inspector_panel_realtime_syllable_rhythm_sync(qapp):
    screen = TimelineScreen()
    inspector = screen.inspector_panel
    inspector.update_clip_info(
        orig_text="I must protect the innocent people of this city.",
        trans_text="আমাকে এই শহরের নিরীহ মানুষদের রক্ষা করতেই হবে।",
        char_name="Hero",
        lang="bn",
        source_duration=3.0,
        dub_duration=2.9,
    )
    assert "%" in inspector.t_score_lbl.text()
    assert "syl" in inspector.t_score_lbl.text()
    assert "Lip Sync" in inspector.l_score_lbl.text()

