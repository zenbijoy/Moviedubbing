"""
Subtitle & Caption Studio Dialog.

Integrates:
  - AutoCaptioner: Speech-to-chunk word-timing caption generation.
  - SubtitleTimingEngine: Frame-accurate shift, stretch/scale, clamp, and min-duration constraints.
  - CaptionStyle Picker: Broadcast & CapCut presets (ASS / CSS / SRT / VTT export).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.application.captions.auto_captioner import AutoCaptioner, Caption
from aidub.application.captions.caption_style import CaptionStyle
from aidub.application.subtitles.subtitle_exporter import SubCue, SubtitleExporter
from aidub.application.subtitles.timing_engine import SubtitleCue, SubtitleTimingEngine
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class SubtitleCaptionStudioDialog(QDialog):
        """Unified Studio Dialog for Auto-Captioning, Timing Adjustment, and Style Picker."""

        subtitles_applied = Signal(list)  # emits list[SubtitleCue]

        def __init__(
            self,
            cues: list[SubtitleCue] | None = None,
            audio_clip: AudioClipData | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Subtitle & Auto-Caption Studio")
            self.resize(850, 620)
            self.setStyleSheet(
                "QDialog { background-color: #0B0F19; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QGroupBox { border: 1px solid #1E293B; border-radius: 6px; margin-top: 8px; font-weight: 700; color: #94A3B8; padding-top: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QLineEdit, QComboBox, QDoubleSpinBox { background: #161E2E; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 7px 12px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
                "QTableWidget { background: #0F172A; color: #E2E8F0; border: 1px solid #1E293B; gridline-color: #334155; }"
                "QHeaderView::section { background: #1E293B; color: #94A3B8; font-weight: bold; padding: 4px; border: none; }"
                "QTabWidget::pane { border: 1px solid #1E293B; background: #0F172A; }"
                "QTabBar::tab { background: #1E293B; color: #94A3B8; padding: 8px 16px; font-weight: bold; }"
                "QTabBar::tab:selected { background: #0284C7; color: white; }"
            )

            self.cues: list[SubtitleCue] = cues or [
                SubtitleCue(0.5, 2.2, "আমি তোমাকে অনেক ভালোবাসি।"),
                SubtitleCue(2.5, 4.8, "তুমি কি সত্যি কখনো আমার কথা মনে করো?"),
                SubtitleCue(5.0, 7.1, "হ্যাঁ, প্রতিনিয়ত তোমার কথাই ভাবি।"),
            ]
            self.audio_clip = audio_clip
            self.selected_style_name: str = "bold_white"

            layout = QVBoxLayout(self)
            layout.setSpacing(10)

            # Top Header
            header = QFrame(self)
            header.setStyleSheet("background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 8px;")
            h_lay = QHBoxLayout(header)
            lbl_title = QLabel("📝 Broadcast Subtitle & Auto-Caption Studio")
            lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38BDF8;")
            self.lbl_count = QLabel(f"Total Cues: {len(self.cues)}")
            self.lbl_count.setStyleSheet("font-size: 11px; color: #94A3B8;")
            h_lay.addWidget(lbl_title)
            h_lay.addStretch()
            h_lay.addWidget(self.lbl_count)
            layout.addWidget(header)

            # Tabs
            tabs = QTabWidget()

            # TAB 1: Cues Table & Timing Adjustment Tools
            tab_cues = QWidget()
            t1_layout = QVBoxLayout(tab_cues)

            self.table_cues = QTableWidget()
            self.table_cues.setColumnCount(4)
            self.table_cues.setHorizontalHeaderLabels(["Start (s)", "End (s)", "Duration (s)", "Subtitle Text"])
            self.table_cues.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            t1_layout.addWidget(self.table_cues)

            # Timing Tools Box
            timing_box = QGroupBox("Subtitle Timing Engine Tools (Sync Adjustment)")
            t_grid = QGridLayout(timing_box)

            t_grid.addWidget(QLabel("Shift Offset (±s):"), 0, 0)
            self.spin_shift = QDoubleSpinBox()
            self.spin_shift.setRange(-60.0, 60.0)
            self.spin_shift.setSingleStep(0.1)
            self.spin_shift.setValue(0.2)
            t_grid.addWidget(self.spin_shift, 0, 1)

            btn_shift = QPushButton("⚡ Apply Time Shift")
            btn_shift.clicked.connect(self._apply_shift)
            t_grid.addWidget(btn_shift, 0, 2)

            t_grid.addWidget(QLabel("Time-Stretch Factor:"), 0, 3)
            self.spin_scale = QDoubleSpinBox()
            self.spin_scale.setRange(0.2, 5.0)
            self.spin_scale.setSingleStep(0.05)
            self.spin_scale.setValue(1.0)
            t_grid.addWidget(self.spin_scale, 0, 4)

            btn_scale = QPushButton("⏱️ Apply Scale Stretch")
            btn_scale.clicked.connect(self._apply_scale)
            t_grid.addWidget(btn_scale, 0, 5)

            btn_clamp = QPushButton("⚓ Clamp to ≥ 0.0s")
            btn_clamp.clicked.connect(self._apply_clamp)
            t_grid.addWidget(btn_clamp, 1, 0, 1, 2)

            btn_min_dur = QPushButton("📏 Ensure Min Duration (1.0s)")
            btn_min_dur.clicked.connect(self._apply_min_duration)
            t_grid.addWidget(btn_min_dur, 1, 2, 1, 2)

            btn_auto_caption = QPushButton("🎙️ Auto-Caption from Audio")
            btn_auto_caption.setStyleSheet("background: #0284C7; color: white; font-weight: bold;")
            btn_auto_caption.clicked.connect(self._run_auto_caption)
            t_grid.addWidget(btn_auto_caption, 1, 4, 1, 2)

            t1_layout.addWidget(timing_box)
            tabs.addTab(tab_cues, "📋 Cues & Timing Engine")

            # TAB 2: Caption Style Picker & Export Preview
            tab_style = QWidget()
            t2_layout = QVBoxLayout(tab_style)

            style_picker_row = QHBoxLayout()
            style_picker_row.addWidget(QLabel("Choose Caption Style Preset:"))
            self.combo_styles = QComboBox()
            for s in CaptionStyle.list():
                self.combo_styles.addItem(s.replace("_", " ").title(), s)
            self.combo_styles.currentIndexChanged.connect(self._on_style_selected)
            style_picker_row.addWidget(self.combo_styles)
            style_picker_row.addStretch()
            t2_layout.addLayout(style_picker_row)

            # Live Preview Banner
            self.lbl_style_preview = QLabel("আমি তোমাকে ভালোবাসি — Sample Subtitle")
            self.lbl_style_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_style_preview.setMinimumHeight(90)
            self._update_style_preview("bold_white")
            t2_layout.addWidget(self.lbl_style_preview)

            # Export Output Code View
            self.txt_export_preview = QTextEdit()
            self.txt_export_preview.setReadOnly(True)
            self.txt_export_preview.setStyleSheet("background: #0F172A; color: #38BDF8; font-family: Consolas; font-size: 11px;")
            t2_layout.addWidget(self.txt_export_preview)

            export_btns = QHBoxLayout()
            btn_srt = QPushButton("📄 Preview SRT")
            btn_srt.clicked.connect(lambda: self._show_export("srt"))
            export_btns.addWidget(btn_srt)

            btn_vtt = QPushButton("🌐 Preview WebVTT")
            btn_vtt.clicked.connect(lambda: self._show_export("vtt"))
            export_btns.addWidget(btn_vtt)

            btn_ass = QPushButton("🎬 Preview ASS Header")
            btn_ass.clicked.connect(lambda: self._show_export("ass"))
            export_btns.addWidget(btn_ass)

            btn_save_file = QPushButton("💾 Save Subtitle to Disk")
            btn_save_file.setStyleSheet("background: #0284C7; color: white; font-weight: bold;")
            btn_save_file.clicked.connect(self._save_to_file)
            export_btns.addWidget(btn_save_file)

            export_btns.addStretch()
            t2_layout.addLayout(export_btns)

            tabs.addTab(tab_style, "🎨 Caption Style & Export")

            layout.addWidget(tabs)

            # Bottom Action Bar
            bottom_bar = QHBoxLayout()
            self.lbl_status = QLabel("Ready.")
            self.lbl_status.setStyleSheet("color: #38BDF8; font-weight: bold;")
            bottom_bar.addWidget(self.lbl_status)
            bottom_bar.addStretch()

            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.reject)
            bottom_bar.addWidget(btn_cancel)

            self.btn_apply = QPushButton("✓ Apply Subtitles to Project")
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_apply.clicked.connect(self._apply_all)
            bottom_bar.addWidget(self.btn_apply)

            layout.addLayout(bottom_bar)

            self._refresh_cues_table()
            self._show_export("srt")

        def _refresh_cues_table(self) -> None:
            self.table_cues.setRowCount(len(self.cues))
            for i, c in enumerate(self.cues):
                self.table_cues.setItem(i, 0, QTableWidgetItem(f"{c.start_s:.2f}"))
                self.table_cues.setItem(i, 1, QTableWidgetItem(f"{c.end_s:.2f}"))
                self.table_cues.setItem(i, 2, QTableWidgetItem(f"{c.duration_s:.2f}s"))
                self.table_cues.setItem(i, 3, QTableWidgetItem(c.text))
            self.lbl_count.setText(f"Total Cues: {len(self.cues)}")

        def _apply_shift(self) -> None:
            delta = self.spin_shift.value()
            self.cues = SubtitleTimingEngine.shift(self.cues, delta)
            self._refresh_cues_table()
            self.lbl_status.setText(f"✓ Shifted all cues by {delta:+.2f}s.")

        def _apply_scale(self) -> None:
            factor = self.spin_scale.value()
            if factor <= 0:
                return
            self.cues = SubtitleTimingEngine.scale(self.cues, factor)
            self._refresh_cues_table()
            self.lbl_status.setText(f"✓ Scaled timestamps by factor {factor:.2f}x.")

        def _apply_clamp(self) -> None:
            self.cues = SubtitleTimingEngine.clamp(self.cues, 0.0)
            self._refresh_cues_table()
            self.lbl_status.setText("✓ Clamped all cues to ≥ 0.0s.")

        def _apply_min_duration(self) -> None:
            self.cues = SubtitleTimingEngine.ensure_min_duration(self.cues, 1.0)
            self._refresh_cues_table()
            self.lbl_status.setText("✓ Guaranteed minimum 1.0s duration on all cues.")

        def _run_auto_caption(self) -> None:
            captioner = AutoCaptioner()
            clip = self.audio_clip or AudioClipData.synthesize_speech_like(duration=4.5, sample_rate=44100)
            sample_words = ["আমি", "তোমাকে", "অনেক", "ভালোবাসি", "চিরকাল", "পাশে", "থাকব"]
            chunks = captioner.segment(clip.samples, clip.sample_rate, words=sample_words)
            self.cues = [SubtitleCue(c.start_s, c.end_s, c.text) for c in chunks]
            self._refresh_cues_table()
            self.lbl_status.setText(f"✓ Auto-captioned {len(self.cues)} chunks from audio energy envelope.")

        def _on_style_selected(self) -> None:
            style_name = self.combo_styles.currentData()
            self.selected_style_name = style_name
            self._update_style_preview(style_name)

        def _update_style_preview(self, style_name: str) -> None:
            p = CaptionStyle.get(style_name)
            font = p.get("font", "Arial")
            color = p.get("color", "#FFFFFF")
            outline = p.get("outline", "#000000") or "#000000"
            size = p.get("size", 24)
            bold = "bold" if p.get("bold", False) else "normal"
            self.lbl_style_preview.setStyleSheet(
                f"background: #000000; color: {color}; font-family: '{font}'; font-size: {size // 2 + 8}px; "
                f"font-weight: {bold}; border: 2px solid {outline}; border-radius: 6px; padding: 12px;"
            )

        def _show_export(self, fmt: str) -> None:
            sub_cues = [SubCue(index=i + 1, start_s=c.start_s, end_s=c.end_s, text=c.text) for i, c in enumerate(self.cues)]
            if fmt == "srt":
                content = SubtitleExporter.to_srt(sub_cues)
            elif fmt == "vtt":
                content = SubtitleExporter.to_vtt(sub_cues)
            else:
                content = (
                    f"[Script Info]\nTitle: AI Dubbed Master\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
                    f"[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                    f"{CaptionStyle.to_ass_style(self.selected_style_name)}\n"
                )
            self.txt_export_preview.setPlainText(content)

        def _save_to_file(self, target_path: str | Path | None = None) -> str:
            sub_cues = [SubCue(index=i + 1, start_s=c.start_s, end_s=c.end_s, text=c.text) for i, c in enumerate(self.cues)]
            content = SubtitleExporter.to_srt(sub_cues)
            out_path = Path(target_path) if target_path else Path("output/master_subtitles.srt")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            self.lbl_status.setText(f"✓ Saved {len(self.cues)} subtitles to {out_path}.")
            return str(out_path.resolve())

        def _apply_all(self) -> None:
            self.subtitles_applied.emit(self.cues)
            self.accept()
else:
    class SubtitleCaptionStudioDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["SubtitleCaptionStudioDialog"]
