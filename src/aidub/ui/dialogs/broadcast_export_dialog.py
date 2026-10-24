"""
Broadcast Master Delivery Export Dialog for AIDub Studio.

Provides professional mastering export options:
- Netflix 5.1 Surround Spec (EBU R128 -23 LUFS / -1.0 dBTP)
- YouTube / Web 4K Preset (-14 LUFS, Faststart)
- Theatrical Master Archive
- Subtitle Embedding & Hard Burn-in controls
- Multi-threaded background export rendering with progress indicator
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.media.broadcast_exporter import (
    PRESET_CONFIGS,
    BroadcastMasterExporter,
    BroadcastPreset,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QThread, Qt, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class _ExportWorker(QThread):
        progress_signal = Signal(int, str)
        completed_signal = Signal(str)
        failed_signal = Signal(str)

        def __init__(
            self,
            *,
            video_path: str,
            audio_path: str,
            output_path: str,
            preset: str,
            subtitle_path: str | None = None,
            burn_subtitles: bool = False,
            music_path: str | None = None,
        ) -> None:
            super().__init__()
            self.video_path = video_path
            self.audio_path = audio_path
            self.output_path = output_path
            self.preset = preset
            self.subtitle_path = subtitle_path
            self.burn_subtitles = burn_subtitles
            self.music_path = music_path

        def run(self) -> None:
            try:
                def progress_cb(pct: int, msg: str) -> None:
                    self.progress_signal.emit(pct, msg)

                if self.music_path and Path(self.music_path).is_file():
                    out = BroadcastMasterExporter.export_cinematic_surround_master(
                        video_path=self.video_path,
                        dialogue_path=self.audio_path,
                        music_path=self.music_path,
                        output_path=self.output_path,
                        preset=self.preset,
                        subtitle_path=self.subtitle_path,
                        burn_subtitles=self.burn_subtitles,
                        progress_cb=progress_cb,
                    )
                else:
                    out = BroadcastMasterExporter.export(
                        video_path=self.video_path,
                        audio_path=self.audio_path,
                        output_path=self.output_path,
                        preset=self.preset,
                        subtitle_path=self.subtitle_path,
                        burn_subtitles=self.burn_subtitles,
                        progress_cb=progress_cb,
                    )
                self.completed_signal.emit(str(out))
            except Exception as exc:
                logger.exception("Broadcast export failed: %s", exc)
                self.failed_signal.emit(str(exc))

    class BroadcastExportDialog(QDialog):
        """Professional Broadcast Master Delivery & Exporter Dialog."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            video_path: str = "",
            audio_path: str = "",
            music_path: str = "",
            subtitle_path: str = "",
            default_output_name: str = "broadcast_master.mp4",
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Broadcast Master Delivery Exporter — Netflix / YouTube / 5.1 Surround")
            self.setMinimumSize(640, 520)
            self.video_path = video_path
            self.audio_path = audio_path
            self.music_path = music_path
            self.subtitle_path = subtitle_path
            self._worker: _ExportWorker | None = None

            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #E2E8F0; }"
                "QLabel { color: #E2E8F0; }"
                "QLineEdit, QComboBox {"
                "  background: #111622; color: #F8FAFC; border: 1px solid #1E293B;"
                "  border-radius: 4px; padding: 6px 10px; font-size: 12px;"
                "}"
                "QComboBox::drop-down { border: none; width: 20px; }"
                "QGroupBox {"
                "  font-size: 11px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B;"
                "  border-radius: 6px; margin-top: 10px; padding-top: 14px;"
                "}"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(22, 18, 22, 18)
            layout.setSpacing(14)

            # Header
            hdr = QHBoxLayout()
            icon = QLabel("📡", self)
            icon.setStyleSheet("font-size: 28px;")
            hdr.addWidget(icon)

            hdr_text = QVBoxLayout()
            title = QLabel("Broadcast Master Delivery Exporter", self)
            title.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8;")
            sub = QLabel(
                "Master and export deliverables compliant with global broadcast & streaming standards.",
                self,
            )
            sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
            hdr_text.addWidget(title)
            hdr_text.addWidget(sub)
            hdr.addLayout(hdr_text)
            hdr.addStretch()
            layout.addLayout(hdr)

            # Preset Selection
            preset_group = QGroupBox("Delivery Profile Preset", self)
            pg_lay = QVBoxLayout(preset_group)

            self.preset_combo = QComboBox(self)
            self.preset_combo.addItem("YouTube / Web 4K UHD (-14 LUFS, AAC 384k, Faststart)", BroadcastPreset.YOUTUBE_4K)
            self.preset_combo.addItem("Netflix Specification (5.1 Surround, EBU R128 -23 LUFS, AC3 640k)", BroadcastPreset.NETFLIX_51)
            self.preset_combo.addItem("Theatrical Master Archive (High Bitrate 5.1 E-AC3 768k)", BroadcastPreset.THEATRICAL_MASTER)
            self.preset_combo.addItem("Mobile / Social Stream (1080p, AAC 192k)", BroadcastPreset.MOBILE_STREAM)
            self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
            pg_lay.addWidget(self.preset_combo)

            self.spec_card = QLabel(self)
            self.spec_card.setStyleSheet("background: #0F172A; border: 1px solid #1E293B; border-radius: 4px; padding: 8px; font-size: 11px; color: #94A3B8;")
            pg_lay.addWidget(self.spec_card)
            layout.addWidget(preset_group)

            # Subtitle & Surround Options
            opt_group = QGroupBox("Mastering Options", self)
            og_lay = QVBoxLayout(opt_group)
            og_lay.setSpacing(8)

            self.surround_chk = QCheckBox("Enable 5.1 Discrete Surround Remixer (Center Voice Isolation)", self)
            self.surround_chk.setChecked(bool(self.music_path and Path(self.music_path).is_file()))
            og_lay.addWidget(self.surround_chk)

            sub_row = QHBoxLayout()
            sub_row.addWidget(QLabel("Subtitles:", self))
            self.sub_mode_combo = QComboBox(self)
            self.sub_mode_combo.addItem("Embed Soft Subtitles (Timed Text)", "embed")
            self.sub_mode_combo.addItem("Burn Hard Subtitles (Rendered onto Video)", "burn")
            self.sub_mode_combo.addItem("None (Clean Master)", "none")
            sub_row.addWidget(self.sub_mode_combo, 1)
            og_lay.addLayout(sub_row)

            layout.addWidget(opt_group)

            # Destination Path Selector
            dest_group = QGroupBox("Output Destination", self)
            dg_lay = QHBoxLayout(dest_group)

            self.dest_edit = QLineEdit(str(Path(video_path).parent / default_output_name if video_path else Path.cwd() / default_output_name), self)
            dg_lay.addWidget(self.dest_edit, 1)

            browse_btn = QPushButton("Browse...", self)
            browse_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #E2E8F0; border: 1px solid #334155; "
                "border-radius: 4px; padding: 6px 14px; font-size: 11px; }"
                "QPushButton:hover { background: #334155; }"
            )
            browse_btn.clicked.connect(self._browse_dest)
            dg_lay.addWidget(browse_btn)

            layout.addWidget(dest_group)

            # Progress Indicator
            self.prog_bar = QProgressBar(self)
            self.prog_bar.setRange(0, 100)
            self.prog_bar.setValue(0)
            self.prog_bar.setTextVisible(True)
            self.prog_bar.setStyleSheet(
                "QProgressBar { background: #0F172A; border: 1px solid #1E293B; border-radius: 4px; height: 16px; text-align: center; color: #FFF; font-size: 10px; font-weight: 700; }"
                "QProgressBar::chunk { background: #2563EB; border-radius: 3px; }"
            )
            self.prog_bar.setVisible(False)
            layout.addWidget(self.prog_bar)

            self.status_lbl = QLabel("", self)
            self.status_lbl.setStyleSheet("font-size: 11px; color: #38BDF8; font-weight: 600;")
            self.status_lbl.setVisible(False)
            layout.addWidget(self.status_lbl)

            # Action Buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            self.cancel_btn = QPushButton("Cancel", self)
            self.cancel_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #94A3B8; border: 1px solid #1E293B; "
                "border-radius: 4px; padding: 7px 18px; }"
                "QPushButton:hover { background: #1E293B; color: #FFF; }"
            )
            self.cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(self.cancel_btn)

            self.export_btn = QPushButton("🚀  Render Broadcast Master", self)
            self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.export_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; "
                "border-radius: 4px; padding: 8px 24px; font-weight: 800; font-size: 12px; }"
                "QPushButton:hover { background: #3B82F6; }"
            )
            self.export_btn.clicked.connect(self._start_export)
            btn_row.addWidget(self.export_btn)

            layout.addLayout(btn_row)

            self._update_spec_display()

        def _on_preset_changed(self) -> None:
            self._update_spec_display()

        def _update_spec_display(self) -> None:
            preset_enum = self.preset_combo.currentData()
            cfg = PRESET_CONFIGS.get(preset_enum, PRESET_CONFIGS[BroadcastPreset.YOUTUBE_4K])
            text = (
                f"<b>Profile:</b> {cfg.description}<br>"
                f"<b>Video:</b> {cfg.video_codec.upper()} (CRF {cfg.crf}) &nbsp;|&nbsp; "
                f"<b>Audio:</b> {cfg.audio_codec.upper()} {cfg.audio_bitrate} ({cfg.channels} Channels @ {cfg.sample_rate}Hz)<br>"
                f"<b>Target Loudness:</b> {cfg.loudness_lufs} LUFS &nbsp;|&nbsp; "
                f"<b>True Peak Limit:</b> {cfg.true_peak_db} dBTP &nbsp;|&nbsp; "
                f"<b>Faststart:</b> Yes"
            )
            self.spec_card.setText(text)

        def _browse_dest(self) -> None:
            cur = self.dest_edit.text()
            chosen, _ = QFileDialog.getSaveFileName(
                self,
                "Select Master Destination",
                cur,
                "MP4 Video (*.mp4);;MKV Video (*.mkv);;MOV Master (*.mov);;All Files (*)",
            )
            if chosen:
                self.dest_edit.setText(chosen)

        def _start_export(self) -> None:
            dest = self.dest_edit.text().strip()
            if not dest:
                QMessageBox.warning(self, "Invalid Output", "Please choose an output destination file.")
                return

            preset_enum = self.preset_combo.currentData()
            sub_mode = self.sub_mode_combo.currentData()
            burn_sub = (sub_mode == "burn")
            sub_file = self.subtitle_path if sub_mode != "none" else None
            use_surround = self.surround_chk.isChecked()

            self.prog_bar.setVisible(True)
            self.prog_bar.setValue(5)
            self.status_lbl.setVisible(True)
            self.status_lbl.setText("Initializing broadcast export pipeline...")
            self.export_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)

            self._worker = _ExportWorker(
                video_path=self.video_path,
                audio_path=self.audio_path,
                output_path=dest,
                preset=preset_enum,
                subtitle_path=sub_file,
                burn_subtitles=burn_sub,
                music_path=self.music_path if use_surround else None,
            )
            self._worker.progress_signal.connect(self._on_worker_progress)
            self._worker.completed_signal.connect(self._on_worker_completed)
            self._worker.failed_signal.connect(self._on_worker_failed)
            self._worker.start()

        def _on_worker_progress(self, pct: int, msg: str) -> None:
            self.prog_bar.setValue(pct)
            self.status_lbl.setText(msg)

        def _on_worker_completed(self, out_file: str) -> None:
            self.prog_bar.setValue(100)
            self.status_lbl.setText(f"✓ Master Complete: {Path(out_file).name}")
            self.export_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            QMessageBox.information(
                self,
                "Master Delivery Exported",
                f"✓ Broadcast master successfully rendered to:\n{out_file}\n\nCompliant with EBU R128 & target distribution standards.",
            )
            self.accept()

        def _on_worker_failed(self, error_msg: str) -> None:
            self.status_lbl.setText(f"Export Error: {error_msg}")
            self.export_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            QMessageBox.critical(self, "Export Failed", f"Broadcast mastering error:\n{error_msg}")


__all__ = ["BroadcastExportDialog"]
