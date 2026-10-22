from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from aidub.ui.screens.timeline_editor import TimelineScreen


def test_inspector_tabs_and_scroll_areas() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        insp = screen.inspector_panel
        # Verify 3 interactive tabs exist
        assert len(insp.tab_buttons) == 3
        assert [b.text() for b in insp.tab_buttons] == ["Inspector", "AI Assistant", "Metadata"]

        # Default is page 0 (Inspector)
        assert insp.panel_stack.currentIndex() == 0
        assert insp.tab_buttons[0].isChecked()

        # Switch to AI Assistant (page 1)
        insp.tab_buttons[1].click()
        app.processEvents()
        assert insp.panel_stack.currentIndex() == 1
        assert insp.tab_buttons[1].isChecked()
        assert not insp.tab_buttons[0].isChecked()

        # Switch to Metadata (page 2)
        insp.tab_buttons[2].click()
        app.processEvents()
        assert insp.panel_stack.currentIndex() == 2
        assert insp.tab_buttons[2].isChecked()

        # Switch back to Inspector (page 0)
        insp.tab_buttons[0].click()
        app.processEvents()
        assert insp.panel_stack.currentIndex() == 0
        assert insp.tab_buttons[0].isChecked()

        # Verify all 3 pages are wrapped in scroll areas
        assert insp.panel_stack.count() == 3
        for i in range(3):
            widget = insp.panel_stack.widget(i)
            assert widget.metaObject().className() == "QScrollArea"
    finally:
        screen.close()
        app.processEvents()


def test_dialogue_inputs_zero_overlap() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        screen.resize(1280, 800)
        screen.show()
        app.processEvents()

        insp = screen.inspector_panel
        # Ensure Inspector page is shown
        insp._switch_tab(0)
        app.processEvents()

        char_geom = insp.char_in.geometry()
        lang_geom = insp.lang_in.geometry()
        orig_geom = insp.orig_in.geometry()
        trans_geom = insp.trans_in.geometry()

        # Check that inputs do not overlap vertically
        assert char_geom.bottom() < lang_geom.top(), f"Overlap: char bottom {char_geom.bottom()} >= lang top {lang_geom.top()}"
        assert lang_geom.bottom() < orig_geom.top(), f"Overlap: lang bottom {lang_geom.bottom()} >= orig top {orig_geom.top()}"
        assert orig_geom.bottom() < trans_geom.top(), f"Overlap: orig bottom {orig_geom.bottom()} >= trans top {trans_geom.top()}"
    finally:
        screen.close()
        app.processEvents()


def test_track_lock_and_visibility_toggles() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        header = screen.header_p
        canvas = screen.canvas_view

        # Initially no tracks are locked or hidden
        assert len(canvas._locked_tracks) == 0
        assert len(canvas._hidden_tracks) == 0

        # Find lock and eye buttons on track S1
        lock_btns = [b for b in header.findChildren(QPushButton) if b.text() in {"🔓", "🔒"}]
        eye_btns = [b for b in header.findChildren(QPushButton) if b.text() in {"👁️", "🎙", "💬", "🚫", "🔇", "🗨️"}]

        assert len(lock_btns) == 10
        assert len(eye_btns) == 10

        # Toggle first lock button (V3)
        btn_v3_lock = lock_btns[0]
        assert btn_v3_lock.text() == "🔓"
        assert not btn_v3_lock.isChecked()

        btn_v3_lock.click()
        app.processEvents()
        assert btn_v3_lock.isChecked()
        assert btn_v3_lock.text() == "🔒"
        assert "V3" in canvas._locked_tracks

        # Toggle unlock
        btn_v3_lock.click()
        app.processEvents()
        assert not btn_v3_lock.isChecked()
        assert btn_v3_lock.text() == "🔓"
        assert "V3" not in canvas._locked_tracks

        # Toggle visibility on first track (V3)
        btn_eye = eye_btns[0]
        btn_eye.click()
        app.processEvents()
        assert btn_eye.isChecked()
        assert "V3" in canvas._hidden_tracks

        btn_eye.click()
        app.processEvents()
        assert not btn_eye.isChecked()
        assert "V3" not in canvas._hidden_tracks
    finally:
        screen.close()
        app.processEvents()


def test_ai_assistant_actions_wired() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    actions_called: list[str] = []

    screen._run_subtitle_qc = lambda: actions_called.append("Subtitle QC")
    screen._show_pipeline_readiness = lambda: actions_called.append("Pipeline Readiness")
    screen._open_character_manager = lambda: actions_called.append("Character Manager")
    screen._open_audio_analysis = lambda: actions_called.append("Audio Analysis")

    try:
        screen._on_ai_action_clicked("Subtitle QC")
        assert "Subtitle QC" in actions_called

        screen._on_ai_action_clicked("Pipeline Readiness")
        assert "Pipeline Readiness" in actions_called

        screen._on_ai_action_clicked("Manage Characters")
        assert "Character Manager" in actions_called

        screen._on_ai_action_clicked("Audio Analysis & Diagnostics")
        assert "Audio Analysis" in actions_called
    finally:
        screen.close()
        app.processEvents()


def test_ai_fix_auto_selection_fallback() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Load sample clips onto timeline
        screen._current_project_data["clips"] = [
            ("S1", 2.0, 3.0, "Source dialogue line", None),
            ("S2", 2.0, 3.0, "Translated dialogue line", None),
        ]
        screen.monitor_panel.set_playhead(2.5)

        # Active clip is currently None
        assert screen._active_clip_info is None

        # Mock the downstream workers so background threads aren't spawned
        timing_fixed = []
        trans_rewritten = []
        screen._apply_timing_fix = lambda: timing_fixed.append(True)
        screen._run_translation_assistant = lambda **kwargs: trans_rewritten.append(kwargs)

        # Clicking AI Fix should auto-select the nearest dialogue clip instead of failing
        screen._on_ai_fix_all()
        assert screen._active_clip_info is not None
        assert screen._active_clip_info["tid"] in {"S1", "S2"}
        assert screen._active_clip_info["start"] == 2.0
        assert timing_fixed == [True]
        assert len(trans_rewritten) == 1
    finally:
        screen.close()
        app.processEvents()


def test_preview_take_fallback_and_search(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    screen._session_store.workspace = tmp_path
    try:
        # Create a mock preview take file
        previews = tmp_path / "previews"
        previews.mkdir(parents=True, exist_ok=True)
        take_file = previews / "take_0001.mp3"
        take_file.write_bytes(b"\x00" * 128)

        # Call preview selected take when combo is empty
        screen._preview_selected_take()
        app.processEvents()

        # Should have found take_0001.mp3 and set it into take_combo
        assert screen.inspector_panel.take_combo.currentText() == "take_0001"
        assert Path(str(screen.inspector_panel.take_combo.currentData())).name == "take_0001.mp3"
    finally:
        if screen._take_audio_player is not None:
            screen._take_audio_player.stop()
        screen.close()
        app.processEvents()


def test_character_manager_dialog() -> None:
    from aidub.ui.character_manager_dialog import CharacterManagerDialog

    app = QApplication.instance() or QApplication([])
    counts = {"SPEAKER_00": 3, "SPEAKER_01": 2}
    voices = {"SPEAKER_00": "bn-BD-PradeepNeural"}
    dlg = CharacterManagerDialog(counts, voices)
    try:
        assert dlg.table.rowCount() == 2
        assert dlg.table.item(0, 0).text() == "SPEAKER_00"
        assert dlg.table.item(1, 0).text() == "SPEAKER_01"

        # Test renaming SPEAKER_00 -> "John"
        dlg._renames["SPEAKER_00"] = "John"
        count = dlg._counts.pop("SPEAKER_00")
        dlg._counts["John"] = count
        dlg._voices["John"] = dlg._voices.pop("SPEAKER_00")
        dlg._refresh_table()

        assert "John" in dlg._counts
        assert dlg._counts["John"] == 3
        assert dlg.get_renames() == {"SPEAKER_00": "John"}
        assert dlg.get_voices()["John"] == "bn-BD-PradeepNeural"
    finally:
        dlg.close()
        app.processEvents()


def test_import_bilingual_subtitles(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Create a sample bilingual SRT file
        bilingual_srt = tmp_path / "test_bilingual.srt"
        bilingual_srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nHello world.\nওহে বিশ্ব।\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nWelcome to AI dubbing.\nএআই ডাবিংয়ে স্বাগতম।\n",
            encoding="utf-8",
        )

        screen.import_bilingual_subtitle_file(str(bilingual_srt))
        clips = screen._current_project_data.get("clips", [])
        s1_clips = [c for c in clips if c[0] == "S1"]
        s2_clips = [c for c in clips if c[0] == "S2"]

        assert len(s1_clips) == 2
        assert len(s2_clips) == 2
        assert s1_clips[0][3] == "Hello world."
        assert s2_clips[0][3] == "ওহে বিশ্ব।"
        assert s1_clips[1][3] == "Welcome to AI dubbing."
        assert s2_clips[1][3] == "এআই ডাবিংয়ে স্বাগতম।"
    finally:
        screen.close()
        app.processEvents()


def test_track_header_import_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))

    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Verify import buttons are present on track headers
        imp_requests: list[str] = []
        screen.header_p.track_import_requested.connect(lambda tid: imp_requests.append(tid))

        # Emit import requested on S1, S2, and A2
        screen.header_p.track_import_requested.emit("S1")
        screen.header_p.track_import_requested.emit("S2")
        screen.header_p.track_import_requested.emit("A2")

        assert imp_requests == ["S1", "S2", "A2"]
    finally:
        screen.close()
        app.processEvents()

