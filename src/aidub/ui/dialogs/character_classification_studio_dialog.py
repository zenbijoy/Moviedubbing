"""
Interactive Character & Voice Classification Studio Dialog.

Features:
  - Interactive Speaker Diarization & Character Roster Matrix.
  - Low-confidence (<75%) error detection filter for immediate human correction.
  - 1-Click Speaker Merging (e.g. merge multiple false diarization clusters).
  - Cue-by-cue character re-assignment with live timeline propagation.
  - Face-to-Voice association indicator (confirms speaking actor in video frame).
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.character_classification_service import (
    CharacterClassificationRecord,
    CharacterClassificationService,
    CueClassificationItem,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class CharacterClassificationStudioDialog(QDialog):
        """Studio desk for reviewing, merging, and correcting speaker & character classifications."""

        classification_updated = Signal(dict)  # emits {clip_id: new_speaker}

        def __init__(
            self,
            clips: list[Any] | None = None,
            clip_characters: dict[str, str] | None = None,
            character_voices: dict[str, str] | None = None,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Character & Voice Classification Studio — Accuracy Desk")
            self.setMinimumSize(1040, 680)
            self.resize(1180, 760)
            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QTableWidget { background: #0E131E; border: 1px solid #1E293B; border-radius: 6px; gridline-color: #1A2333; color: #F1F5F9; font-size: 11px; }"
                "QHeaderView::section { background: #141B2A; color: #94A3B8; font-weight: 700; font-size: 10px; border: none; padding: 6px; }"
                "QPushButton { background: #162030; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #202B40; color: #FFF; border-color: #38BDF8; }"
            )

            self._service = CharacterClassificationService()
            if clips:
                self._service.load_from_timeline_clips(clips, clip_characters, character_voices)

            self._init_ui()
            self._refresh_roster_table()
            self._refresh_cues_table()

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("👥 CHARACTER & VOICE CLASSIFICATION ACCURACY STUDIO", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #F8FAFC;")
            s_lbl = QLabel(
                "Inspect AI speaker diarization, resolve low-confidence attributions, and merge fragmented speakers.",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            merge_btn = QPushButton("🔗 Merge Two Speakers", self)
            merge_btn.setStyleSheet("background: #4F46E5; color: #FFF; font-weight: 800;")
            merge_btn.clicked.connect(self._prompt_merge_speakers)
            header.addWidget(merge_btn)

            rename_btn = QPushButton("✏️ Rename Character", self)
            rename_btn.clicked.connect(self._prompt_rename_character)
            header.addWidget(rename_btn)

            root.addLayout(header)

            # Main Splitter: Left = Roster, Right = Cues
            splitter = QSplitter(Qt.Orientation.Horizontal, self)

            # Left Pane: Character Roster
            left_pane = QWidget(splitter)
            left_lay = QVBoxLayout(left_pane)
            left_lay.setContentsMargins(0, 0, 8, 0)
            left_lay.addWidget(QLabel("Movie Character Roster & Diarization Clusters:", left_pane))

            self.roster_table = QTableWidget(left_pane)
            self.roster_table.setColumnCount(5)
            self.roster_table.setHorizontalHeaderLabels(["Character Name", "Lines", "Duration", "Confidence", "Status"])
            self.roster_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.roster_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.roster_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.roster_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.roster_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.roster_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            left_lay.addWidget(self.roster_table, 1)

            splitter.addWidget(left_pane)

            # Right Pane: Cue Review & Correction Desk
            right_pane = QWidget(splitter)
            right_lay = QVBoxLayout(right_pane)
            right_lay.setContentsMargins(8, 0, 0, 0)

            cue_top = QHBoxLayout()
            cue_top.addWidget(QLabel("Dialogue Line Attributions:", right_pane))
            cue_top.addStretch()

            self.filter_uncertain_check = QCheckBox("⚠️ Show Low-Confidence Only (< 75%)", right_pane)
            self.filter_uncertain_check.setStyleSheet("color: #F59E0B; font-weight: 700; font-size: 11px;")
            self.filter_uncertain_check.toggled.connect(self._refresh_cues_table)
            cue_top.addWidget(self.filter_uncertain_check)

            right_lay.addLayout(cue_top)

            self.cues_table = QTableWidget(right_pane)
            self.cues_table.setColumnCount(5)
            self.cues_table.setHorizontalHeaderLabels(["#", "Time", "Dialogue Text", "Assigned Speaker", "Confidence"])
            self.cues_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.cues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.cues_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.cues_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.cues_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.cues_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.cues_table.cellDoubleClicked.connect(self._reassign_selected_cue)
            right_lay.addWidget(self.cues_table, 1)

            # Reassign Toolbar below table
            reassign_row = QHBoxLayout()
            reassign_row.addWidget(QLabel("Reassign Selected Line to:", right_pane))
            self.reassign_combo = QComboBox(right_pane)
            reassign_row.addWidget(self.reassign_combo, 1)
            reassign_btn = QPushButton("Apply to Line", right_pane)
            reassign_btn.setStyleSheet("background: #0284C7; color: #FFF; font-weight: 800;")
            reassign_btn.clicked.connect(self._apply_reassign_btn)
            reassign_row.addWidget(reassign_btn)

            right_lay.addLayout(reassign_row)
            splitter.addWidget(right_pane)
            splitter.setSizes([460, 680])
            root.addWidget(splitter, 1)

            # Bottom Action Bar
            bot = QHBoxLayout()
            self.summary_badge = QLabel("Total: 0 Characters · 0 Cues", self)
            self.summary_badge.setStyleSheet("color: #94A3B8; font-weight: 700; font-size: 11px;")
            bot.addWidget(self.summary_badge)

            bot.addStretch()

            apply_sync_btn = QPushButton("✓ Apply & Sync Timeline", self)
            apply_sync_btn.setStyleSheet("background: #059669; color: #FFF; font-weight: 800; padding: 8px 24px;")
            apply_sync_btn.clicked.connect(self._apply_and_sync)
            bot.addWidget(apply_sync_btn)

            close_btn = QPushButton("Close", self)
            close_btn.clicked.connect(self.accept)
            bot.addWidget(close_btn)

            root.addLayout(bot)

        def _refresh_roster_table(self) -> None:
            roster = self._service.get_character_roster()
            self.roster_table.setRowCount(len(roster))

            self.reassign_combo.clear()
            for r, c in enumerate(roster):
                self.reassign_combo.addItem(c.character_name)

                name_item = QTableWidgetItem(c.character_name)
                name_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                name_item.setForeground(QColor(c.color_hex))
                self.roster_table.setItem(r, 0, name_item)

                self.roster_table.setItem(r, 1, QTableWidgetItem(f"{c.line_count} lines"))
                self.roster_table.setItem(r, 2, QTableWidgetItem(f"{c.total_duration_s:.1f}s"))

                conf_item = QTableWidgetItem(f"{int(c.confidence_score * 100)}%")
                if c.confidence_score < 0.75:
                    conf_item.setForeground(QColor("#F59E0B"))
                else:
                    conf_item.setForeground(QColor("#10B981"))
                self.roster_table.setItem(r, 3, conf_item)

                status_item = QTableWidgetItem("⚠️ Review" if c.is_flagged_uncertain else "✓ Verified")
                status_item.setForeground(QColor("#F59E0B" if c.is_flagged_uncertain else "#10B981"))
                self.roster_table.setItem(r, 4, status_item)

            self.summary_badge.setText(
                f"Total: {len(roster)} Characters · {len(self._service.cues)} Dialogue Lines"
            )

        def _refresh_cues_table(self) -> None:
            show_uncertain_only = self.filter_uncertain_check.isChecked()
            cues = self._service.get_uncertain_cues() if show_uncertain_only else self._service.cues

            self.cues_table.setRowCount(len(cues))
            for r, cue in enumerate(cues):
                self.cues_table.setItem(r, 0, QTableWidgetItem(f"#{cue.cue_index + 1}"))

                start_s = cue.start_ms / 1000.0
                end_s = cue.end_ms / 1000.0
                time_str = f"{int(start_s // 60):02d}:{start_s % 60:04.1f} - {int(end_s // 60):02d}:{end_s % 60:04.1f}"
                self.cues_table.setItem(r, 1, QTableWidgetItem(time_str))

                face_tag = " [👤 Face]" if cue.face_detected else ""
                self.cues_table.setItem(r, 2, QTableWidgetItem(f"{cue.dialogue_text[:65]}{face_tag}"))

                spk_item = QTableWidgetItem(cue.assigned_speaker)
                spk_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                self.cues_table.setItem(r, 3, spk_item)

                conf_pct = int(cue.confidence * 100)
                conf_item = QTableWidgetItem(f"{conf_pct}%")
                if cue.is_uncertain:
                    conf_item.setForeground(QColor("#EF4444"))
                    conf_item.setText(f"{conf_pct}% (⚠️ Low)")
                else:
                    conf_item.setForeground(QColor("#10B981"))
                self.cues_table.setItem(r, 4, conf_item)

        def _reassign_selected_cue(self, row: int, col: int) -> None:
            self._apply_reassign_to_row(row)

        def _apply_reassign_btn(self) -> None:
            row = self.cues_table.currentRow()
            if row >= 0:
                self._apply_reassign_to_row(row)

        def _apply_reassign_to_row(self, row: int) -> None:
            idx_item = self.cues_table.item(row, 0)
            if not idx_item:
                return
            cue_num = int(idx_item.text().replace("#", "")) - 1
            new_speaker = self.reassign_combo.currentText()
            if new_speaker:
                self._service.reassign_cue(cue_num, new_speaker)
                self._refresh_roster_table()
                self._refresh_cues_table()

        def _prompt_merge_speakers(self) -> None:
            roster = self._service.get_character_roster()
            if len(roster) < 2:
                QMessageBox.information(self, "Merge Speakers", "At least two characters are needed to merge.")
                return

            names = [c.character_name for c in roster]
            source, ok1 = QInputDialog.getItem(
                self, "Merge Speakers — Step 1", "Select speaker to MERGE FROM (will be removed):", names, 0, False
            )
            if not ok1 or not source:
                return

            remaining = [n for n in names if n != source]
            target, ok2 = QInputDialog.getItem(
                self, "Merge Speakers — Step 2", f"Merge '{source}' INTO target character:", remaining, 0, False
            )
            if not ok2 or not target:
                return

            count = self._service.merge_speakers(source, target)
            self._refresh_roster_table()
            self._refresh_cues_table()
            QMessageBox.information(
                self,
                "Speakers Merged",
                f"Successfully merged {count} dialogue lines from '{source}' into '{target}'.",
            )

        def _prompt_rename_character(self) -> None:
            roster = self._service.get_character_roster()
            if not roster:
                return
            names = [c.character_name for c in roster]
            target, ok1 = QInputDialog.getItem(
                self, "Rename Character", "Select character to rename:", names, 0, False
            )
            if not ok1 or not target:
                return

            new_name, ok2 = QInputDialog.getText(
                self, "New Name", f"Enter new character name for '{target}':", text=target
            )
            if ok2 and new_name.strip() and new_name.strip() != target:
                count = self._service.rename_character(target, new_name.strip())
                self._refresh_roster_table()
                self._refresh_cues_table()
                QMessageBox.information(
                    self,
                    "Character Renamed",
                    f"Renamed '{target}' to '{new_name.strip()}' across {count} dialogue lines.",
                )

        def _apply_and_sync(self) -> None:
            mapping = self._service.export_classification_map()
            self.classification_updated.emit(mapping)
            self.accept()


__all__ = ["CharacterClassificationStudioDialog"]
