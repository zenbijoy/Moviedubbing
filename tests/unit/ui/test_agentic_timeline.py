from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from aidub.application.agentic_studio import (
    AutomationStage,
    StageStatus,
    StudioSessionStore,
    create_automation_plan,
)
from aidub.ui.screens.timeline_editor import TimelineScreen


def test_timeline_canvas_owns_its_graphics_scene() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        screen.resize(1_280, 800)
        screen.show()
        app.processEvents()

        assert screen.canvas_view.scene() is not None
        assert len(screen.canvas_view.scene().items()) > 20
    finally:
        screen.close()
        app.processEvents()


def test_timeline_imports_real_srt_time_ranges(tmp_path: Path) -> None:
    subtitle = tmp_path / "dialogue.srt"
    subtitle.write_text(
        "1\n00:00:01,250 --> 00:00:03,750\nHello there.\n",
        encoding="utf-8",
    )

    cues = TimelineScreen._parse_subtitle_file_cues(str(subtitle))

    assert len(cues) == 1
    assert cues[0][:3] == ("S1", 1.25, 2.5)

    target_cues = TimelineScreen._parse_subtitle_file_cues(
        str(subtitle),
        track_id="S2",
    )
    assert target_cues[0][:3] == ("S2", 1.25, 2.5)


def test_review_master_does_not_claim_unrun_lip_sync_pass(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    screen._session_store = StudioSessionStore(tmp_path)
    try:
        screen._on_dubbing_completed({})

        assert screen._automation_state.stage(AutomationStage.LIP_SYNC).status is (
            StageStatus.SKIPPED
        )
        assert screen._automation_state.stage(AutomationStage.QUALITY_CONTROL).status is (
            StageStatus.FAILED
        )
        assert screen._automation_state.quality_report is None
    finally:
        screen.close()
        app.processEvents()


def test_reference_workspace_exposes_navigation_tools_and_ai_actions() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        assert tuple(screen.stage_bar._buttons) == (
            "Ingest",
            "Dubbing",
            "Review",
            "Delivery",
        )
        assert tuple(screen.navigation_rail._buttons) == ("Subtitles",)
        assert screen.tool_palette._buttons["Select"].isChecked()
        assert not screen.ai_overlay.run_btn.isHidden()
        started = []
        screen.ai_overlay.run_requested.disconnect()
        screen.ai_overlay.run_requested.connect(lambda: started.append(True))
        screen.ai_overlay.run_btn.click()
        assert started == [True]
        assert tuple(
            button.toolTip()
            for button in screen.timeline_bar.findChildren(QPushButton)
        ) == ("Add Marker", "Timeline Settings")
        assert not screen.status_dock.findChildren(QPushButton)
        ai_actions = {
            button.text().strip().split("  ")[-1]
            for button in screen.ai_overlay.findChildren(QPushButton)
            if button is not screen.ai_overlay.run_btn
        }
        assert ai_actions == {
            "Select Dub Voice",
            "Improve Emotion",
            "Audio Analysis",
            "Match Timing",
            "Rewrite Translation",
            "Shorten Translation",
            "Fix Pronunciation",
            "Properties",
        }
        assert (
            not {
                "Match Original Voice",
                "Detect Characters",
                "Detect Emotions",
                "Clone Character Voice",
                "Improve Lip Sync",
                "Lip Sync Active Shot",
                "Improve Audio",
                "Reanalyze Speaker",
            }
            & ai_actions
        )
        assert "AUTO DUB MASTER" in screen.ai_overlay.run_btn.text()
        screen._on_ai_action_clicked("Audio Analysis")
        assert screen._audio_analysis_dialog is not None
        assert screen._audio_analysis_dialog.isVisible()
        screen._audio_analysis_dialog.close()
    finally:
        screen.close()
        app.processEvents()


def test_timeline_settings_controls_real_canvas_preferences() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    opened: list[bool] = []
    screen._show_timeline_settings = lambda: opened.append(True)
    try:
        screen._on_timeline_toolbar_action("Timeline Settings")
        assert opened == [True]

        menu = screen._build_timeline_settings_menu()
        snapping = next(
            action for action in menu.actions()
            if action.text() == "Snap to clip edges and markers"
        )
        snapping.trigger()
        assert screen.canvas_view._snapping_enabled is False
        assert screen._timeline_toggles["Toggle Snapping"] is False

        linked = next(
            action for action in menu.actions()
            if action.text() == "Link related dialogue and dub clips"
        )
        linked.trigger()
        assert screen.canvas_view._linked_selection_enabled is False
        assert screen._timeline_toggles["Linked Selection"] is False

        fit = next(
            action for action in menu.actions()
            if action.text() == "Fit timeline to window"
        )
        fit.trigger()
        assert 0.55 <= screen.canvas_view.transform().m11() <= 3.5
        screen._set_timeline_zoom(200)
        assert screen.canvas_view.transform().m11() == 2.0
    finally:
        screen.close()
        app.processEvents()


def test_pipeline_stage_events_do_not_infer_success_from_percentages() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    screen._automation_state = create_automation_plan("Test Project", quality_profile="fast")
    try:
        screen._on_dubbing_progress("ingest", 2, "Inspecting the source movie")
        screen._on_dubbing_progress(
            "separate_stems_skipped", 18, "Stem separation disabled by run profile"
        )
        screen._on_dubbing_progress(
            "diarize_skipped", 32, "Speaker diarization disabled by run profile"
        )
        screen._on_dubbing_progress("asr", 80, "Transcribing source dialogue")

        assert screen._automation_state.stage(AutomationStage.AUDIO_SEPARATION).status is (
            StageStatus.SKIPPED
        )
        assert screen._automation_state.stage(AutomationStage.SPEAKER_ANALYSIS).status is (
            StageStatus.SKIPPED
        )
        assert screen._automation_state.stage(AutomationStage.TRANSCRIPTION).status is (
            StageStatus.RUNNING
        )
    finally:
        screen.close()
        app.processEvents()


def test_quality_control_navigation_runs_real_target_subtitle_qc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    subtitle = tmp_path / "target.srt"
    subtitle.write_text(
        "1\n00:00:01,000 --> 00:00:05,000\n" + ("আ" * 80) + "\n",
        encoding="utf-8",
    )
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: messages.append(_args[-1]))
    try:
        screen.import_subtitle_file(str(subtitle), track_id="S2")
        screen.stage_bar._buttons["Review"].click()

        assert messages
        assert "Subtitle QC:   REVIEW" in screen.inspector_panel.pass_lbl.text()
        assert "line" in messages[0].lower()
        assert "characters/second" in messages[0]
    finally:
        screen.close()
        app.processEvents()


def test_quality_control_explains_when_target_subtitles_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: messages.append(_args[-1]))
    try:
        screen.stage_bar._buttons["Review"].click()

        assert messages
        assert "No target subtitle cues are loaded" in messages[0]
        assert "Subtitle QC not run" in screen.status_msg_lbl.text()
    finally:
        screen.close()
        app.processEvents()


def test_razor_edit_is_undoable() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    original: list[tuple[str, float, float, str, float | None]] = [
        ("V1", 0.0, 10.0, "source.mp4", None)
    ]
    screen._current_project_data["duration"] = 10.0
    screen._current_project_data["clips"] = list(original)
    screen.canvas_view.set_clips(original, 10.0)
    try:
        was_split = screen.canvas_view._split_clip(
            {"tid": "V1", "start": 0.0, "dur": 10.0, "label": "source.mp4"},
            4.0,
        )

        assert was_split is True
        assert [clip[2] for clip in screen._current_project_data["clips"]] == [4.0, 6.0]

        screen.undo()

        assert screen._current_project_data["clips"] == original
    finally:
        screen.close()
        app.processEvents()
