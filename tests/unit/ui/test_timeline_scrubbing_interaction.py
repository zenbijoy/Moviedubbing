"""
Tests for high-precision timeline scrubbing and audio-video synchronization.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from aidub.ui.screens.timeline_editor import (
    _ProgramMonitorPanel,
    _TimelineCanvasView,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_timeline_canvas_mouse_drag_scrubbing(qapp: QApplication) -> None:
    view = _TimelineCanvasView()
    view.set_clips([], duration_sec=120.0)

    received_timecodes: list[float] = []
    view.timecode_changed.connect(received_timecodes.append)

    pt1 = QPointF(200.0, 10.0)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pt1,
        pt1,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(press_event)

    assert len(received_timecodes) >= 1
    t_first = received_timecodes[-1]
    assert t_first > 0.0
    assert view._is_dragging_playhead is True

    pt2 = QPointF(400.0, 10.0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pt2,
        pt2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseMoveEvent(move_event)

    assert len(received_timecodes) >= 2
    t_second = received_timecodes[-1]
    assert t_second > t_first

    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        pt2,
        pt2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseReleaseEvent(release_event)
    assert view._is_dragging_playhead is False


def test_program_monitor_set_playhead_sync(qapp: QApplication) -> None:
    monitor = _ProgramMonitorPanel()
    monitor.set_project_info("Project", "Movie", "Character", "Quote", 60.0)

    monitor.set_playhead(15.5)
    assert monitor._playhead_sec == 15.5
    assert monitor.tc_overlay.text() == "00:00:15:500"
    assert monitor.scrubber.value() == 15500
