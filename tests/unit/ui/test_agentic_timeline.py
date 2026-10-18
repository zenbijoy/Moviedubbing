from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from aidub.application.agentic_studio import (
    AutomationStage,
    StageStatus,
    StudioSessionStore,
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
            "Learning",
            "Assembly",
            "Editing",
            "Dubbing",
            "Color",
            "Audio",
            "Graphics",
            "Libraries",
        )
        assert screen.navigation_rail._buttons["Timeline"].isChecked()
        assert screen.tool_palette._buttons["Select"].isChecked()
        ai_actions = {
            button.text().strip().split("  ")[-1]
            for button in screen.ai_overlay.findChildren(QPushButton)
        }
        assert {
            "Regenerate Voice",
            "Match Original Voice",
            "Improve Emotion",
            "Match Timing",
            "Rewrite Translation",
            "Shorten Translation",
            "Improve Lip Sync",
            "Fix Pronunciation",
            "Improve Audio",
            "Reanalyze Speaker",
            "Properties",
        } <= ai_actions
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
