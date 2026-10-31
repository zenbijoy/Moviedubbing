"""
NLE Edit Tools Bar for Multitrack Timeline.

Provides standard Hollywood keyboard/mouse tool modes:
  - Arrow / Selection Tool (V)
  - Razor Blade / Split at Playhead (C)
  - Trim In / Trim Out (T)
  - Ripple Delete (Shift+X / Shift+Del)
  - Slip / Slide Tool (Y)
  - Speed Ramp Tool (R)
  - Timeline Marker Insertion (M)
  - Headless safe for environments without PySide6.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QButtonGroup,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


class TimelineToolMode(StrEnum):
    SELECT = "select"  # V
    BLADE = "blade"  # C
    TRIM = "trim"  # T
    RIPPLE = "ripple"  # B
    SLIP = "slip"  # Y
    SPEED = "speed"  # R


if _QT_AVAILABLE:

    class TimelineEditToolbarWidget(QWidget):
        """Toolbar providing NLE tool selectors and action triggers."""

        tool_changed = Signal(str)  # TimelineToolMode value
        blade_requested = Signal()
        ripple_delete_requested = Signal()
        marker_requested = Signal()

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._current_mode = TimelineToolMode.SELECT
            self._init_ui()

        def _init_ui(self) -> None:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(6)

            self.btn_group = QButtonGroup(self)
            self.btn_group.setExclusive(True)

            tools = [
                ("↖ Selection (V)", TimelineToolMode.SELECT),
                ("✂️ Razor Blade (C)", TimelineToolMode.BLADE),
                ("↔ Trim (T)", TimelineToolMode.TRIM),
                ("🌊 Ripple (B)", TimelineToolMode.RIPPLE),
                ("⇄ Slip/Slide (Y)", TimelineToolMode.SLIP),
                ("⚡ Speed (R)", TimelineToolMode.SPEED),
            ]

            for label, mode in tools:
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setStyleSheet(
                    "QPushButton{background: #1E293B; color: #CBD5E1; padding: 5px 10px; border-radius: 4px; font-size: 11px;}"
                    "QPushButton:checked{background: #2563EB; color: white; font-weight: bold;}"
                )
                if mode == TimelineToolMode.SELECT:
                    btn.setChecked(True)
                btn.clicked.connect(lambda _, m=mode: self._set_mode(m))
                self.btn_group.addButton(btn)
                layout.addWidget(btn)

            layout.addSpacing(10)

            # Quick Action Buttons
            self.btn_split_now = QPushButton("Split at Playhead")
            self.btn_split_now.setStyleSheet("background: #DC2626; color: white; font-weight: bold; padding: 5px 10px;")
            self.btn_split_now.clicked.connect(self.blade_requested.emit)
            layout.addWidget(self.btn_split_now)

            self.btn_ripple_del = QPushButton("Ripple Delete Gap")
            self.btn_ripple_del.setStyleSheet("background: #D97706; color: white; padding: 5px 10px;")
            self.btn_ripple_del.clicked.connect(self.ripple_delete_requested.emit)
            layout.addWidget(self.btn_ripple_del)

            self.btn_marker = QPushButton("📍 Add Marker (M)")
            self.btn_marker.setStyleSheet("background: #059669; color: white; padding: 5px 10px;")
            self.btn_marker.clicked.connect(self.marker_requested.emit)
            layout.addWidget(self.btn_marker)

            layout.addStretch()

        def _set_mode(self, mode: TimelineToolMode) -> None:
            self._current_mode = mode
            self.tool_changed.emit(mode.value)

        @property
        def current_mode(self) -> TimelineToolMode:
            return self._current_mode

else:
    class TimelineEditToolbarWidget:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


__all__ = [
    "TimelineEditToolbarWidget",
    "TimelineToolMode",
]
