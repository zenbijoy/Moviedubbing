"""Application Log Viewer Dialog for viewing real runtime logs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.infrastructure.logging import get_default_log_file, get_in_app_log_handler

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    QDialog = object  # type: ignore


if _HAS_QT:
    class LogViewerDialog(QDialog):
        """Clean modal dialog displaying live runtime application logs."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Application Runtime Logs - AI Dubbing Studio")
            self.resize(850, 520)
            self.setStyleSheet(
                "QDialog { background-color: #0E131F; color: #E2E8F0; }"
                "QLabel { color: #CBD5E1; font-size: 12px; }"
                "QLineEdit { background: #161F30; border: 1px solid #2A3850; border-radius: 4px; padding: 4px 8px; color: #FFF; }"
                "QPushButton { background: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 6px 12px; color: #E2E8F0; font-weight: 600; }"
                "QPushButton:hover { background: #2D3D54; }"
                "QPlainTextEdit { background-color: #080C14; border: 1px solid #1E293B; border-radius: 6px; color: #94A3B8; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            # Header & Filter
            top_bar = QHBoxLayout()
            title_lbl = QLabel("📋 <b>Live System & Pipeline Logs</b>")
            title_lbl.setStyleSheet("font-size: 14px; color: #38BDF8;")
            top_bar.addWidget(title_lbl)
            top_bar.addStretch()

            filter_lbl = QLabel("Filter:")
            top_bar.addWidget(filter_lbl)
            self.filter_edit = QLineEdit(self)
            self.filter_edit.setPlaceholderText("Filter lines (e.g. ERROR, Demucs)...")
            self.filter_edit.setFixedWidth(220)
            self.filter_edit.textChanged.connect(self._apply_filter)
            top_bar.addWidget(self.filter_edit)
            layout.addLayout(top_bar)

            # Log text area
            self.text_area = QPlainTextEdit(self)
            self.text_area.setReadOnly(True)
            font = QFont("Consolas", 10)
            font.setStyleHint(QFont.StyleHint.Monospace)
            self.text_area.setFont(font)
            layout.addWidget(self.text_area)

            # Bottom Action Bar
            bot_bar = QHBoxLayout()
            self.log_file_lbl = QLabel(f"Log path: {get_default_log_file()}")
            self.log_file_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            bot_bar.addWidget(self.log_file_lbl)
            bot_bar.addStretch()

            clear_btn = QPushButton("Clear In-App Buffer", self)
            clear_btn.clicked.connect(self._clear_logs)
            bot_bar.addWidget(clear_btn)

            copy_btn = QPushButton("Copy All", self)
            copy_btn.clicked.connect(self._copy_all)
            bot_bar.addWidget(copy_btn)

            open_folder_btn = QPushButton("Open Logs Folder", self)
            open_folder_btn.clicked.connect(self._open_log_folder)
            bot_bar.addWidget(open_folder_btn)

            close_btn = QPushButton("Close", self)
            close_btn.clicked.connect(self.accept)
            bot_bar.addWidget(close_btn)

            layout.addLayout(bot_bar)

            self._handler = get_in_app_log_handler()
            self._handler.add_callback(self._on_log_line)
            self._load_existing_lines()

        def _load_existing_lines(self) -> None:
            lines = self._handler.get_lines()
            self.text_area.setPlainText("\n".join(lines))
            self.text_area.verticalScrollBar().setValue(
                self.text_area.verticalScrollBar().maximum()
            )

        def _on_log_line(self, line: str) -> None:
            filter_text = self.filter_edit.text().strip().lower()
            if not filter_text or filter_text in line.lower():
                self.text_area.appendPlainText(line)

        def _apply_filter(self, text: str) -> None:
            term = text.strip().lower()
            all_lines = self._handler.get_lines()
            if not term:
                filtered = all_lines
            else:
                filtered = [ln for ln in all_lines if term in ln.lower()]
            self.text_area.setPlainText("\n".join(filtered))

        def _clear_logs(self) -> None:
            self._handler.clear()
            self.text_area.clear()

        def _copy_all(self) -> None:
            from PySide6.QtGui import QGuiApplication
            clip = QGuiApplication.clipboard()
            if clip:
                clip.setText(self.text_area.toPlainText())

        def _open_log_folder(self) -> None:
            log_p = get_default_log_file()
            if log_p.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_p.parent)))
            else:
                log_p.parent.mkdir(parents=True, exist_ok=True)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_p.parent)))

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            self._handler.remove_callback(self._on_log_line)
            super().closeEvent(event)
else:
    class LogViewerDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PySide6 required for LogViewerDialog")


__all__ = ["LogViewerDialog"]
