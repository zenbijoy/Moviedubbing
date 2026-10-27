"""Keyboard Shortcuts Reference and Editor Dialog."""

from __future__ import annotations

import logging
from typing import Any

from aidub.ui.keyboard_shortcuts import (
    DEFAULT_SHORTCUTS,
    PREMIERE_SHORTCUTS,
    NleProfile,
    ShortcutManager,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class KeyboardShortcutsDialog(QDialog):
        """Keyboard shortcuts viewer and NLE profile reference dialog."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Keyboard Shortcuts & Editorial Hotkeys")
            self.setMinimumSize(640, 520)
            self.setModal(True)
            self.setStyleSheet(
                "QDialog { background: #0E131F; color: #F1F5F9; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QLineEdit, QComboBox { background: #162032; color: #FFF; border: 1px solid #233045; "
                "border-radius: 4px; padding: 5px 8px; font-size: 11px; }"
                "QTableWidget { background: #111726; color: #E2E8F0; border: 1px solid #1E293B; "
                "gridline-color: #1A2436; selection-background-color: #1E3A8A; selection-color: #FFF; }"
                "QHeaderView::section { background: #0A0E18; color: #94A3B8; font-size: 10px; "
                "font-weight: 700; border: none; padding: 6px; border-bottom: 1px solid #233045; }"
            )

            self._manager = ShortcutManager()

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(12)

            # Header
            top_bar = QHBoxLayout()
            h_lbl = QLabel("⌨️ Keyboard Shortcuts Reference", self)
            h_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #38BDF8;")
            top_bar.addWidget(h_lbl)
            top_bar.addStretch()

            prof_lbl = QLabel("Profile:", self)
            prof_lbl.setStyleSheet("font-weight: 700; color: #94A3B8;")
            top_bar.addWidget(prof_lbl)

            self.profile_combo = QComboBox(self)
            self.profile_combo.addItem("Default Studio Profile", NleProfile.DEFAULT)
            self.profile_combo.addItem("Adobe Premiere Pro", NleProfile.PREMIERE_PRO)
            self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
            top_bar.addWidget(self.profile_combo)

            layout.addLayout(top_bar)

            # Search bar
            search_box = QHBoxLayout()
            self.search_edit = QLineEdit(self)
            self.search_edit.setPlaceholderText("🔍 Filter shortcuts by key or action name…")
            self.search_edit.textChanged.connect(self._filter_shortcuts)
            search_box.addWidget(self.search_edit)
            layout.addLayout(search_box)

            # Table of shortcuts
            self.table = QTableWidget(self)
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Shortcut", "Action Description", "Category"])
            self.table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.verticalHeader().setVisible(False)
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            layout.addWidget(self.table)

            # Close button
            bottom_box = QHBoxLayout()
            bottom_box.addStretch()
            close_btn = QPushButton("Close", self)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #FFF; border: 1px solid #334155; "
                "border-radius: 4px; padding: 6px 18px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #2563EB; border-color: #38BDF8; }"
            )
            close_btn.clicked.connect(self.accept)
            bottom_box.addWidget(close_btn)
            layout.addLayout(bottom_box)

            self._populate_table(DEFAULT_SHORTCUTS)

        def _populate_table(self, shortcuts: list[Any]) -> None:
            # Extended standard studio shortcuts including Timeline and Navigation
            all_items: list[tuple[str, str, str]] = [
                ("Ctrl+O", "Import Source Movie Media", "File & Media"),
                ("Ctrl+Shift+O", "Open Existing .aidub Project Package", "Project Lifecycle"),
                ("Ctrl+S", "Save Project Timeline & Subtitles", "Project Lifecycle"),
                ("Ctrl+N", "Create New Dubbing Project", "Project Lifecycle"),
                ("Ctrl+E", "Export Broadcast Master Video", "Rendering & Export"),
                ("Ctrl+Enter", "Dub Movie (AI Pipeline Stages)", "AI Dubbing"),
                ("Ctrl+B", "Split Clip Under Playhead (Razor)", "Timeline Editing"),
                ("Delete / Backspace", "Delete Selected Timeline Clip", "Timeline Editing"),
                ("Ctrl+Z", "Undo Last Timeline Edit", "History"),
                ("Ctrl+Y", "Redo Last Timeline Edit", "History"),
                ("Space", "Play / Pause Preview", "Playback"),
                ("Left / Right", "Previous / Next Frame", "Playback"),
                ("J / K / L", "Shuttle Reverse / Pause / Forward", "Playback"),
                ("Ctrl+K", "Open Command Palette", "Navigation"),
                ("F11", "Toggle Full Screen Mode", "View"),
                ("Esc", "Cancel Active Dubbing Job", "AI Pipeline"),
            ]

            for s in shortcuts:
                key = str(s.key_sequence)
                desc = str(s.description)
                cat = "NLE Editorial"
                if not any(item[0] == key for item in all_items):
                    all_items.append((key, desc, cat))

            self._all_items = all_items
            self._render_rows(all_items)

        def _render_rows(self, items: list[tuple[str, str, str]]) -> None:
            self.table.setRowCount(len(items))
            for row_idx, (key, desc, cat) in enumerate(items):
                key_item = QTableWidgetItem(f"  {key}  ")
                key_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
                key_item.setForeground(Qt.GlobalColor.cyan)

                desc_item = QTableWidgetItem(desc)
                desc_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

                cat_item = QTableWidgetItem(cat)
                cat_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )

                self.table.setItem(row_idx, 0, key_item)
                self.table.setItem(row_idx, 1, desc_item)
                self.table.setItem(row_idx, 2, cat_item)

        def _on_profile_changed(self) -> None:
            profile: NleProfile = self.profile_combo.currentData()
            shortcuts = (
                PREMIERE_SHORTCUTS if profile == NleProfile.PREMIERE_PRO else DEFAULT_SHORTCUTS
            )
            self._populate_table(shortcuts)

        def _filter_shortcuts(self, text: str) -> None:
            q = text.strip().casefold()
            if not q:
                self._render_rows(self._all_items)
                return
            filtered = [
                item
                for item in self._all_items
                if q in item[0].casefold() or q in item[1].casefold() or q in item[2].casefold()
            ]
            self._render_rows(filtered)

else:

    class KeyboardShortcutsDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PySide6 required for KeyboardShortcutsDialog")


__all__ = ["KeyboardShortcutsDialog"]
