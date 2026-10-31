"""
Command Palette Dialog (Ctrl+K).

Fast spotlight-style command search and execution across all professional
DAW, ADR, LipSync, Bangla, DSP, and Timeline tools.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import (
        QDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class CommandPaletteDialog(QDialog):
        """Spotlight modal palette triggered by Ctrl+K for 1-click execution."""

        def __init__(
            self,
            commands: list[dict[str, str | Callable[[], None]]],
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Command Palette")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.resize(580, 420)
            self.setStyleSheet(
                "QDialog { background-color: #0F172A; border: 2px solid #0284C7; border-radius: 8px; font-family: 'Segoe UI', sans-serif; }"
                "QLineEdit { background: #1E293B; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 10px 12px; font-size: 13px; font-weight: 600; }"
                "QLineEdit:focus { border: 1px solid #38BDF8; }"
                "QListWidget { background: #0F172A; border: none; color: #E2E8F0; font-size: 12px; outline: none; }"
                "QListWidget::item { padding: 8px 12px; border-radius: 4px; margin: 2px 0; }"
                "QListWidget::item:selected { background: #0284C7; color: #FFFFFF; font-weight: 700; }"
                "QListWidget::item:hover:!selected { background: #1E293B; }"
            )

            self.all_commands = commands

            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            # Top input
            self.search_box = QLineEdit(self)
            self.search_box.setPlaceholderText("🔍 Type a command or tool name (e.g., VariAudio, Punch-In, Bangla)...")
            self.search_box.textChanged.connect(self._filter_commands)
            layout.addWidget(self.search_box)

            # Results List
            self.list_widget = QListWidget(self)
            self.list_widget.itemDoubleClicked.connect(self._execute_selected)
            layout.addWidget(self.list_widget)

            # Footer Hint
            footer = QLabel("↑↓ to navigate • ↵ Enter to execute • Esc to close", self)
            footer.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 600;")
            layout.addWidget(footer)

            self._filter_commands("")

        def _filter_commands(self, text: str) -> None:
            self.list_widget.clear()
            query = text.strip().lower()
            for cmd in self.all_commands:
                title = str(cmd.get("title", ""))
                category = str(cmd.get("category", ""))
                hotkey = str(cmd.get("hotkey", ""))

                if (
                    not query
                    or query in title.lower()
                    or query in category.lower()
                    or query in hotkey.lower()
                ):
                    item = QListWidgetItem()
                    display_text = f"[{category}]  {title}"
                    if hotkey:
                        display_text += f"   ({hotkey})"
                    item.setText(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, cmd.get("action"))
                    self.list_widget.addItem(item)

            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)

        def _execute_selected(self) -> None:
            item = self.list_widget.currentItem()
            if item is not None:
                action = item.data(Qt.ItemDataRole.UserRole)
                self.accept()
                if callable(action):
                    action()

        def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
            if event.key() == Qt.Key.Key_Escape:
                self.reject()
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute_selected()
            elif event.key() == Qt.Key.Key_Down:
                cur = self.list_widget.currentRow()
                if cur < self.list_widget.count() - 1:
                    self.list_widget.setCurrentRow(cur + 1)
            elif event.key() == Qt.Key.Key_Up:
                cur = self.list_widget.currentRow()
                if cur > 0:
                    self.list_widget.setCurrentRow(cur - 1)
            else:
                super().keyPressEvent(event)
else:
    class CommandPaletteDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["CommandPaletteDialog"]
