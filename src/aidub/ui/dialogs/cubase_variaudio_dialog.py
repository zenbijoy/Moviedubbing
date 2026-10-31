"""
Cubase Pro VariAudio 3 Studio Dialog — Syllable Micro-Pitch & Formant Intonation Editor.

Features:
  - Interactive piano-roll canvas displaying speech syllable pitch blocks.
  - Drag-to-pitch and micro-pitch slider (-100 to +100 cents).
  - Formant shift slider (-12 to +12 st) without altering pitch or speed.
  - Natural Spoken Speech Intonation Quantization.
  - Real-time live auditioning with phase coherence.
  - 1-Click apply to dialogue take on the master timeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.media.cubase_variaudio import CubaseVariAudioEngine, VariAudioSegment
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
    from PySide6.QtWidgets import (
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QSlider,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class _VariAudioCanvas(QWidget):
        """Interactive pitch grid displaying syllable pitch blocks."""

        segment_selected = Signal(int)  # emits selected segment index

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(240)
            self.setStyleSheet("background: #090D16; border: 1px solid #1E293B; border-radius: 8px;")
            self.segments: list[VariAudioSegment] = []
            self.selected_idx: int = 0
            self.duration_s: float = 3.0

        def set_segments(self, segs: list[VariAudioSegment], duration_s: float) -> None:
            self.segments = segs
            self.duration_s = max(0.1, duration_s)
            self.selected_idx = 0 if segs else -1
            self.update()

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self.segments:
                w = self.width()
                click_t = (event.position().x() / max(1.0, w)) * self.duration_s
                # Find matching segment
                for i, seg in enumerate(self.segments):
                    if seg.start_s <= click_t <= seg.end_s:
                        self.selected_idx = i
                        self.segment_selected.emit(i)
                        self.update()
                        break
            super().mousePressEvent(event)

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()

            # 1. Background grid (Semitone lines)
            painter.setPen(QPen(QColor("#162032"), 1))
            n_lanes = 12
            for i in range(n_lanes):
                y = int((i / n_lanes) * h)
                painter.drawLine(0, y, w, y)

            if not self.segments:
                painter.setPen(QColor("#64748B"))
                painter.drawText(
                    self.rect(), Qt.AlignmentFlag.AlignCenter, "No speech segments detected."
                )
                return

            # 2. Render Syllable Pitch Blocks
            min_midi = 45.0
            max_midi = 80.0
            midi_range = max_midi - min_midi

            for i, seg in enumerate(self.segments):
                x = int((seg.start_s / self.duration_s) * w)
                bw = max(14, int((seg.duration_s / self.duration_s) * w))

                # Pitch Y mapping (higher pitch = higher up on canvas)
                effective_midi = seg.pitch_midi + (seg.pitch_cents / 100.0)
                norm_y = 1.0 - ((effective_midi - min_midi) / midi_range)
                y = int(np.clip(norm_y * (h - 30), 10, h - 30))

                is_sel = i == self.selected_idx
                block_rect = QRectF(x, y, bw - 2, 22)

                # Syllable block styling
                if is_sel:
                    painter.setBrush(QBrush(QColor("#38BDF8")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 2))
                else:
                    painter.setBrush(QBrush(QColor("#0284C7")))
                    painter.setPen(QPen(QColor("#0369A1"), 1))

                painter.drawRoundedRect(block_rect, 4, 4)

                # Segment label
                painter.setPen(QColor("#FFFFFF" if is_sel else "#E2E8F0"))
                font = painter.font()
                font.setPointSize(9)
                font.setBold(is_sel)
                painter.setFont(font)

                cents_str = f"{seg.pitch_cents:+.0f}c" if abs(seg.pitch_cents) > 1 else ""
                lbl = f"{seg.segment_id} ({seg.pitch_hz:.0f}Hz {cents_str})"
                painter.drawText(
                    block_rect, Qt.AlignmentFlag.AlignCenter, lbl[: max(4, int(bw / 7))]
                )

    class CubaseVariAudioDialog(QDialog):
        """Cubase Pro VariAudio 3 Dialogue Micro-Pitch & Formant Studio."""

        variaudio_applied = Signal(object)  # emits modified AudioClipData

        def __init__(
            self,
            clip: AudioClipData,
            character_name: str = "Actor",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.original_clip = clip
            self.current_clip = clip.clone()
            self.character_name = character_name
            self.engine = CubaseVariAudioEngine(clip.sample_rate)
            self.segments: list[VariAudioSegment] = self.engine.detect_segments(clip)

            self.setWindowTitle(f"Cubase VariAudio 3 — Intonation Editor [{character_name}]")
            self.setMinimumSize(960, 600)
            self.setStyleSheet(
                "QDialog { background: #0B0E17; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #38BDF8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QSlider::groove:horizontal { height: 6px; background: #1E293B; border-radius: 3px; }"
                "QSlider::sub-page:horizontal { background: #0284C7; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #38BDF8; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
                "QPushButton { background: #162032; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 7px 16px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #1E293B; color: #FFF; border-color: #38BDF8; }"
            )

            self._init_ui()
            self.canvas.set_segments(self.segments, self.original_clip.duration_s)
            self._update_controls_for_selected()

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("🎚️ CUBASE VARIAUDIO 3 — VOCAL INTONATION STUDIO", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #38BDF8;")
            s_lbl = QLabel(
                "DAW-Grade Micro-Pitch, Formant Shifter, and Speech Intonation Sculpting.", self
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            btn_quantize = QPushButton("🪄 Quantize Natural Intonation", self)
            btn_quantize.setStyleSheet(
                "background: #4F46E5; color: #FFF; font-weight: 800; border-color: #6366F1;"
            )
            btn_quantize.clicked.connect(self._on_quantize_intonation)
            header.addWidget(btn_quantize)

            root.addLayout(header)

            # Canvas
            root.addWidget(
                QLabel("Interactive Pitch Canvas (Click Syllable Block to Edit):", self)
            )
            self.canvas = _VariAudioCanvas(self)
            self.canvas.segment_selected.connect(self._on_segment_selected)
            root.addWidget(self.canvas, 1)

            # Smart Controls Box
            grp_ctrl = QGroupBox("VariAudio Smart Controls for Selected Syllable", self)
            grid = QGridLayout(grp_ctrl)

            # 1. Micro-pitch slider (cents)
            grid.addWidget(QLabel("Micro-Pitch (-100 to +100 Cents):", grp_ctrl), 0, 0)
            self.slider_cents = QSlider(Qt.Orientation.Horizontal, grp_ctrl)
            self.slider_cents.setRange(-100, 100)
            self.slider_cents.setValue(0)
            self.slider_cents.valueChanged.connect(self._on_cents_changed)
            grid.addWidget(self.slider_cents, 0, 1)
            self.lbl_cents_val = QLabel("0 cents", grp_ctrl)
            grid.addWidget(self.lbl_cents_val, 0, 2)

            # 2. Formant Shift slider
            grid.addWidget(QLabel("Formant Shift (-12 to +12 Semitones):", grp_ctrl), 1, 0)
            self.slider_formant = QSlider(Qt.Orientation.Horizontal, grp_ctrl)
            self.slider_formant.setRange(-12, 12)
            self.slider_formant.setValue(0)
            self.slider_formant.valueChanged.connect(self._on_formant_changed)
            grid.addWidget(self.slider_formant, 1, 1)
            self.lbl_formant_val = QLabel("0 st", grp_ctrl)
            grid.addWidget(self.lbl_formant_val, 1, 2)

            # 3. Volume Trim slider
            grid.addWidget(QLabel("Syllable Gain (-12 to +6 dB):", grp_ctrl), 2, 0)
            self.slider_gain = QSlider(Qt.Orientation.Horizontal, grp_ctrl)
            self.slider_gain.setRange(-12, 6)
            self.slider_gain.setValue(0)
            self.slider_gain.valueChanged.connect(self._on_gain_changed)
            grid.addWidget(self.slider_gain, 2, 1)
            self.lbl_gain_val = QLabel("0.0 dB", grp_ctrl)
            grid.addWidget(self.lbl_gain_val, 2, 2)

            root.addWidget(grp_ctrl)

            # Action Bar
            bot = QHBoxLayout()
            self.audition_btn = QPushButton("🔊 Audition VariAudio Take", self)
            self.audition_btn.setStyleSheet(
                "background: #0284C7; color: #FFF; font-weight: 800; padding: 8px 18px;"
            )
            self.audition_btn.clicked.connect(self._audition_take)
            bot.addWidget(self.audition_btn)

            bot.addStretch()

            btn_reset = QPushButton("Reset All Segments", self)
            btn_reset.clicked.connect(self._reset_segments)
            bot.addWidget(btn_reset)

            apply_btn = QPushButton("✓ Apply to Dialogue Take", self)
            apply_btn.setStyleSheet(
                "background: #10B981; color: #FFF; font-weight: 800; padding: 8px 24px;"
            )
            apply_btn.clicked.connect(self._apply_and_close)
            bot.addWidget(apply_btn)

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.clicked.connect(self.reject)
            bot.addWidget(cancel_btn)

            root.addLayout(bot)

        def _on_segment_selected(self, idx: int) -> None:
            self._update_controls_for_selected()

        def _update_controls_for_selected(self) -> None:
            if 0 <= self.canvas.selected_idx < len(self.segments):
                seg = self.segments[self.canvas.selected_idx]
                self.slider_cents.blockSignals(True)
                self.slider_formant.blockSignals(True)
                self.slider_gain.blockSignals(True)

                self.slider_cents.setValue(int(seg.pitch_cents))
                self.lbl_cents_val.setText(f"{seg.pitch_cents:+.0f} cents")

                self.slider_formant.setValue(int(seg.formant_shift_semitones))
                self.lbl_formant_val.setText(f"{seg.formant_shift_semitones:+.0f} st")

                self.slider_gain.setValue(int(seg.gain_db))
                self.lbl_gain_val.setText(f"{seg.gain_db:+.1f} dB")

                self.slider_cents.blockSignals(False)
                self.slider_formant.blockSignals(False)
                self.slider_gain.blockSignals(False)

        def _on_cents_changed(self, val: int) -> None:
            if 0 <= self.canvas.selected_idx < len(self.segments):
                self.segments[self.canvas.selected_idx].pitch_cents = float(val)
                self.lbl_cents_val.setText(f"{val:+d} cents")
                self.canvas.update()

        def _on_formant_changed(self, val: int) -> None:
            if 0 <= self.canvas.selected_idx < len(self.segments):
                self.segments[self.canvas.selected_idx].formant_shift_semitones = float(val)
                self.lbl_formant_val.setText(f"{val:+d} st")

        def _on_gain_changed(self, val: int) -> None:
            if 0 <= self.canvas.selected_idx < len(self.segments):
                self.segments[self.canvas.selected_idx].gain_db = float(val)
                self.lbl_gain_val.setText(f"{val:+d}.0 dB")

        def _on_quantize_intonation(self) -> None:
            self.segments = self.engine.quantize_pitch_to_speech_intonation(
                self.segments, strength=0.8
            )
            self.canvas.update()
            self._update_controls_for_selected()
            QMessageBox.information(
                self,
                "Intonation Quantized",
                "Successfully shaped pitch contour to natural conversational speech declination.",
            )

        def _reset_segments(self) -> None:
            self.segments = self.engine.detect_segments(self.original_clip)
            self.canvas.set_segments(self.segments, self.original_clip.duration_s)
            self._update_controls_for_selected()

        def _audition_take(self) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.audition_btn.setText("🔊 Audition VariAudio Take")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.audition_btn.setText("🔊 Audition VariAudio Take")
                )

            self.audition_btn.setText("⏹ Stop Audition")
            rendered = self.engine.apply_segment_edits(self.original_clip, self.segments)
            self._audition.play_clip(rendered)

        def _apply_and_close(self) -> None:
            rendered = self.engine.apply_segment_edits(self.original_clip, self.segments)
            self.variaudio_applied.emit(rendered)
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.accept()

        def reject(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().reject()

else:

    class CubaseVariAudioDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def exec(self) -> int:
            return 0


__all__ = ["CubaseVariAudioDialog"]
