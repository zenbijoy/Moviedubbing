"""
Batch Dub Runner Dialog.

Integrates:
  - BatchDubber application service for queue processing.
  - Multi-provider TTS (ElevenLabs, Edge TTS, XTTS, Coqui).
  - Live progress tracking, processed/total counts, and dynamic ETA calculation.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.batch.batch_dubber import (
    BatchDubber,
    BatchProgress,
    DubCue,
    DubResult,
    TtsProvider,
    VoiceCloneProfile,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QProgressBar,
        QPushButton,
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

    class BatchDubRunnerDialog(QDialog):
        """Studio dialog for multi-cue automated batch dubbing with ETA telemetry."""

        batch_completed = Signal(list)  # emits list[DubResult]

        def __init__(
            self,
            cues: list[DubCue] | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Batch Dub Runner & Queue Processor")
            self.resize(800, 560)
            self.setStyleSheet(
                "QDialog { background-color: #0B0F19; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QComboBox { background: #161E2E; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
                "QTableWidget { background: #0F172A; color: #E2E8F0; border: 1px solid #1E293B; gridline-color: #334155; }"
                "QHeaderView::section { background: #1E293B; color: #94A3B8; font-weight: bold; padding: 4px; border: none; }"
                "QProgressBar { background: #161E2E; border: 1px solid #334155; border-radius: 4px; text-align: center; color: white; font-weight: bold; }"
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8); border-radius: 3px; }"
            )

            self.cues: list[DubCue] = cues or [
                DubCue(cue_id="cue_01", text="আমি তোমাকে খুব ভালোবাসি কিন্তু তুমি বুঝলে না।", speaker_id="hero", target_duration_sec=3.2),
                DubCue(cue_id="cue_02", text="তুমি কি আমাকে একা ফেলে চলে যাবে?", speaker_id="heroine", target_duration_sec=2.5),
                DubCue(cue_id="cue_03", text="না, আমি কখনো তোমাকে ছেড়ে যাব না!", speaker_id="hero", target_duration_sec=2.8),
                DubCue(cue_id="cue_04", text="তাহলে চলো আজই আমরা পালিয়ে যাই।", speaker_id="heroine", target_duration_sec=2.4),
                DubCue(cue_id="cue_05", text="সব বাঁধা পেরিয়ে আমাদের জয় হবেই।", speaker_id="hero", target_duration_sec=3.0),
            ]
            self.dubber = BatchDubber()
            self.results: list[DubResult] = []

            layout = QVBoxLayout(self)
            layout.setSpacing(12)

            # Header
            header = QFrame(self)
            header.setStyleSheet("background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 8px;")
            h_lay = QHBoxLayout(header)
            title = QLabel("⚡ Automated Batch Dubbing Engine & Live ETA Monitor")
            title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38BDF8;")
            self.lbl_queue_count = QLabel(f"Queue: {len(self.cues)} Cues")
            self.lbl_queue_count.setStyleSheet("font-size: 11px; color: #94A3B8;")
            h_lay.addWidget(title)
            h_lay.addStretch()
            h_lay.addWidget(self.lbl_queue_count)
            layout.addWidget(header)

            # Settings Row
            settings_row = QHBoxLayout()
            settings_row.addWidget(QLabel("TTS Provider:"))
            self.combo_provider = QComboBox()
            for p in TtsProvider:
                self.combo_provider.addItem(p.value.upper(), p)
            settings_row.addWidget(self.combo_provider)

            settings_row.addWidget(QLabel("Voice Clone Profile:"))
            self.combo_profile = QComboBox()
            self.combo_profile.addItems(["Hero Protagonist (Bangla)", "Heroine (Bangla)", "Narrator (Studio)"])
            settings_row.addWidget(self.combo_profile)

            settings_row.addStretch()
            layout.addLayout(settings_row)

            # Cues Queue Table
            self.table_cues = QTableWidget()
            self.table_cues.setColumnCount(5)
            self.table_cues.setHorizontalHeaderLabels(["Cue ID", "Speaker", "Duration (s)", "Status", "Dialogue Text"])
            self.table_cues.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.table_cues)
            self._refresh_cues_table()

            # Progress & ETA Section
            prog_box = QFrame(self)
            prog_box.setStyleSheet("background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 10px;")
            p_lay = QVBoxLayout(prog_box)

            eta_row = QHBoxLayout()
            self.lbl_progress_text = QLabel("Progress: 0 / 5 cues (0%)")
            self.lbl_progress_text.setStyleSheet("font-weight: bold; color: #E2E8F0;")
            self.lbl_eta = QLabel("Estimated Time Remaining (ETA): --")
            self.lbl_eta.setStyleSheet("font-weight: bold; color: #F59E0B;")
            eta_row.addWidget(self.lbl_progress_text)
            eta_row.addStretch()
            eta_row.addWidget(self.lbl_eta)
            p_lay.addLayout(eta_row)

            self.prog_bar = QProgressBar()
            self.prog_bar.setRange(0, 100)
            self.prog_bar.setValue(0)
            p_lay.addWidget(self.prog_bar)

            layout.addWidget(prog_box)

            # Action Buttons
            btn_row = QHBoxLayout()
            self.btn_run = QPushButton("▶ Run Batch Dubbing Queue")
            self.btn_run.setStyleSheet(
                "QPushButton { background: #0284C7; color: white; font-weight: bold; padding: 9px 18px; }"
                "QPushButton:hover { background: #0369A1; }"
            )
            self.btn_run.clicked.connect(self._run_batch)
            btn_row.addWidget(self.btn_run)

            self.btn_audition_cue = QPushButton("🔊 Audition Selected")
            self.btn_audition_cue.clicked.connect(self._audition_selected_cue)
            btn_row.addWidget(self.btn_audition_cue)

            btn_row.addStretch()

            btn_cancel = QPushButton("Close")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            self.btn_apply = QPushButton("✓ Apply Dubbed Takes to Timeline")
            self.btn_apply.setEnabled(False)
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; padding: 9px 18px; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_apply.clicked.connect(self._apply_to_timeline)
            btn_row.addWidget(self.btn_apply)

            layout.addLayout(btn_row)

        def _refresh_cues_table(self) -> None:
            self.table_cues.setRowCount(len(self.cues))
            for i, c in enumerate(self.cues):
                self.table_cues.setItem(i, 0, QTableWidgetItem(c.cue_id))
                self.table_cues.setItem(i, 1, QTableWidgetItem(c.speaker_id))
                self.table_cues.setItem(i, 2, QTableWidgetItem(f"{c.target_duration_sec:.2f}s"))
                self.table_cues.setItem(i, 3, QTableWidgetItem("Queued"))
                self.table_cues.setItem(i, 4, QTableWidgetItem(c.text))

        def _on_progress_telemetry(self, p: BatchProgress) -> None:
            pct = int(p.percent_complete)
            self.prog_bar.setValue(pct)
            self.lbl_progress_text.setText(f"Progress: {p.processed_cues} / {p.total_cues} cues ({pct}%)")
            self.lbl_eta.setText(f"Estimated Time Remaining (ETA): {p.eta_seconds:.1f}s")
            idx = p.processed_cues - 1
            if 0 <= idx < self.table_cues.rowCount():
                item = QTableWidgetItem("✓ Completed")
                item.setForeground(Qt.GlobalColor.green)
                self.table_cues.setItem(idx, 3, item)

        def _run_batch(self) -> None:
            self.btn_run.setEnabled(False)
            provider = self.combo_provider.currentData()
            profile = VoiceCloneProfile(
                profile_id="clone_batch",
                name=self.combo_profile.currentText(),
                language="bn",
                provider=provider,
            )

            self.results = self.dubber.dub_batch(
                cues=self.cues,
                profile=profile,
                progress_callback=self._on_progress_telemetry,
            )

            self.lbl_eta.setText("Estimated Time Remaining (ETA): Done")
            self.btn_apply.setEnabled(True)

        def _audition_selected_cue(self) -> None:
            row = self.table_cues.currentRow()
            if row < 0 and self.cues:
                row = 0
            if 0 <= row < len(self.cues):
                cue = self.cues[row]
                self.lbl_eta.setText(f"🔊 Auditioning cue {cue.cue_id} ('{cue.text[:25]}...').")

        def _apply_to_timeline(self) -> None:
            if self.results:
                self.batch_completed.emit(self.results)
                self.accept()
else:
    class BatchDubRunnerDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["BatchDubRunnerDialog"]
