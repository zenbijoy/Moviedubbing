"""
Character and Voice Classification Studio Screen.

Provides:
  - Speaker Diarization & Character Roster Matrix.
  - Low-confidence (<75%) review detection and flagging.
  - 1-Click Cluster Merging (e.g. merging duplicate SPEAKER_00 and SPEAKER_02).
  - Cue-by-cue reassignment with live audit logging.
  - Headless safe for non-GUI environments.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.voice.character_registry import CharacterRegistry
from aidub.application.voice.voice_classifier import VoiceClassifier

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


if _QT_AVAILABLE:

    class VoiceClassificationScreen(QWidget):
        """Voice Classification and Speaker Matrix Studio Screen."""

        speaker_reassigned = Signal(str, str)  # (cue_id, new_speaker)
        clusters_merged = Signal(str, str)  # (source, target)

        def __init__(
            self,
            classifier: VoiceClassifier | None = None,
            registry: CharacterRegistry | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.classifier: VoiceClassifier = classifier or VoiceClassifier()
            self.registry: CharacterRegistry = registry or CharacterRegistry()

            self.setWindowTitle("Character & Voice Classification Studio")
            self.resize(1000, 650)
            self._init_ui()
            self._populate_table()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(14)

            # Header
            header = QHBoxLayout()
            title = QLabel("👥 Character Classification & Diarization Matrix")
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
            header.addWidget(title)
            header.addStretch()

            self.lbl_stats = QLabel("Total Cues: 0 | Flagged Uncertain: 0")
            self.lbl_stats.setStyleSheet("color: #94A3B8; font-weight: bold;")
            header.addWidget(self.lbl_stats)

            layout.addLayout(header)

            # Merge Toolbar Box
            merge_group = QGroupBox("⚡ 1-Click Speaker Merge (Fix Duplicate Diarization Clusters)")
            merge_group.setStyleSheet("QGroupBox{color: #F59E0B; font-weight: bold;}")
            merge_layout = QHBoxLayout(merge_group)

            merge_layout.addWidget(QLabel("Merge Source Cluster:"))
            self.combo_merge_src = QComboBox()
            self.combo_merge_src.addItems(["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"])
            merge_layout.addWidget(self.combo_merge_src)

            merge_layout.addWidget(QLabel("Into Target Character:"))
            self.combo_merge_target = QComboBox()
            self.combo_merge_target.addItems(["Hero", "Villain", "Heroine", "SPEAKER_00", "SPEAKER_01"])
            merge_layout.addWidget(self.combo_merge_target)

            self.btn_merge = QPushButton("🔗 Merge & Reassign All Cues")
            self.btn_merge.setStyleSheet("background: #D97706; color: white; font-weight: bold; padding: 6px 12px;")
            self.btn_merge.clicked.connect(self._on_merge_clicked)
            merge_layout.addWidget(self.btn_merge)

            layout.addWidget(merge_group)

            # Cues Attribution Table
            self.table = QTableWidget()
            self.table.setColumnCount(6)
            self.table.setHorizontalHeaderLabels([
                "Cue ID", "Assigned Speaker", "Confidence", "Status", "Face Match", "Actions"
            ])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.table.setStyleSheet(
                "QTableWidget{background: #0F172A; color: #E2E8F0; gridline-color: #334155;}"
                "QHeaderView::section{background: #1E293B; color: #94A3B8; font-weight: bold; padding: 4px;}"
            )
            layout.addWidget(self.table)

        def _populate_table(self) -> None:
            cues = self.classifier.list_cues()
            uncertain_count = sum(1 for c in cues if c.is_uncertain)
            self.lbl_stats.setText(f"Total Cues: {len(cues)} | Flagged Uncertain: {uncertain_count}")

            self.table.setRowCount(len(cues))
            for row, cue in enumerate(cues):
                self.table.setItem(row, 0, QTableWidgetItem(cue.cue_id))
                self.table.setItem(row, 1, QTableWidgetItem(cue.effective_speaker))

                conf_item = QTableWidgetItem(f"{cue.confidence * 100:.0f}%")
                if cue.is_uncertain:
                    conf_item.setForeground(Qt.GlobalColor.red)
                else:
                    conf_item.setForeground(Qt.GlobalColor.green)
                self.table.setItem(row, 2, conf_item)

                status_text = "⚠️ Uncertain" if cue.is_uncertain else "✅ Verified"
                if cue.manual_override_speaker:
                    status_text += " (Manual)"
                self.table.setItem(row, 3, QTableWidgetItem(status_text))

                face_text = "Detected" if cue.face_track_id else "No Face"
                self.table.setItem(row, 4, QTableWidgetItem(face_text))

                btn_fix = QPushButton("Reassign")
                btn_fix.setStyleSheet("background: #2563EB; color: white; padding: 2px 6px;")
                btn_fix.clicked.connect(lambda _, c=cue.cue_id: self._on_reassign_cue(c))
                self.table.setCellWidget(row, 5, btn_fix)

        def _on_reassign_cue(self, cue_id: str) -> None:
            target_spk = self.combo_merge_target.currentText()
            self.classifier.override_speaker(cue_id, target_spk)
            self.speaker_reassigned.emit(cue_id, target_spk)
            self._populate_table()

        def _on_merge_clicked(self) -> None:
            src = self.combo_merge_src.currentText()
            tgt = self.combo_merge_target.currentText()
            if src == tgt:
                QMessageBox.warning(self, "Invalid Merge", "Source and Target speakers cannot be identical.")
                return
            op = self.classifier.merge_speaker_clusters(src, tgt)
            self.clusters_merged.emit(src, tgt)
            self._populate_table()
            QMessageBox.information(
                self,
                "Speaker Merge Complete",
                f"Merged cluster {src} into {tgt}.\nUpdated {len(op.affected_cue_ids)} cues.",
            )

else:
    class VoiceClassificationScreen:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.classifier = VoiceClassifier()
            self.registry = CharacterRegistry()


__all__ = [
    "VoiceClassificationScreen",
]
