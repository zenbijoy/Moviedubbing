"""
Cubase Pro Crossfade Studio Dialog & Visual X-Fade Editor.

Features:
  - Interactive crossfade curve visualizer.
  - Equal Power (+3 dB center boost) curve mode for dialogue post-production.
  - S-Curve (logarithmic cubic) anti-pop dialogue boundary splice.
  - Midpoint skew (-50% to +50%) and millisecond precision duration slider.
  - Real-time auditioning of spliced audio transition.
  - 1-Click apply to timeline dialogue clips.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.media.cubase_crossfade import (
    CrossfadeSettings,
    CrossfadeShape,
    CubaseCrossfadeEngine,
)
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPaintEvent, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QRadioButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class _CrossfadeCurveCanvas(QWidget):
        """Draws the Fade Out curve (red/orange) and Fade In curve (green/cyan) intersecting."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(180)
            self.setStyleSheet("background: #090D16; border: 1px solid #1E293B; border-radius: 8px;")
            self.settings = CrossfadeSettings()

        def set_settings(self, settings: CrossfadeSettings) -> None:
            self.settings = settings
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()

            # Center vertical line (splice point)
            mid_x = w / 2.0
            painter.setPen(QPen(QColor("#334155"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(mid_x), 0, int(mid_x), h)

            # Generate curve points
            fade_out, fade_in = CubaseCrossfadeEngine.generate_curves(w, self.settings)

            # Draw Fade Out (Red / Rose)
            painter.setPen(QPen(QColor("#F43F5E"), 2))
            for x in range(w - 1):
                y1 = h - int(fade_out[x] * (h - 20)) - 10
                y2 = h - int(fade_out[x + 1] * (h - 20)) - 10
                painter.drawLine(x, y1, x + 1, y2)

            # Draw Fade In (Sky / Cyan)
            painter.setPen(QPen(QColor("#38BDF8"), 2))
            for x in range(w - 1):
                y1 = h - int(fade_in[x] * (h - 20)) - 10
                y2 = h - int(fade_in[x + 1] * (h - 20)) - 10
                painter.drawLine(x, y1, x + 1, y2)

            # Labels
            painter.setPen(QColor("#F43F5E"))
            painter.drawText(12, 22, "Fade Out (Outgoing Clip)")
            painter.setPen(QColor("#38BDF8"))
            painter.drawText(w - 150, 22, "Fade In (Incoming Clip)")

    class CubaseCrossfadeDialog(QDialog):
        """Cubase Pro Crossfade Studio Dialog."""

        crossfade_applied = Signal(object)  # emits spliced AudioClipData

        def __init__(
            self,
            clip_a: AudioClipData,
            clip_b: AudioClipData,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.clip_a = clip_a
            self.clip_b = clip_b
            self.settings = CrossfadeSettings()
            self.engine = CubaseCrossfadeEngine()

            self.setWindowTitle("Cubase Crossfade Editor — Dialogue Splice Studio")
            self.setMinimumSize(820, 520)
            self.setStyleSheet(
                "QDialog { background: #0B0E17; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #38BDF8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QSlider::groove:horizontal { height: 6px; background: #1E293B; border-radius: 3px; }"
                "QSlider::sub-page:horizontal { background: #0284C7; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #38BDF8; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
                "QPushButton { background: #162032; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 8px 16px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #1E293B; color: #FFF; border-color: #38BDF8; }"
            )

            self._init_ui()

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("🔀 CUBASE CROSSFADE (X-FADE) DIALOG", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #38BDF8;")
            s_lbl = QLabel(
                "Sub-millisecond dialogue splicing with Equal Power, S-Curve, and midpoint skew control.",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            root.addLayout(header)

            # Canvas
            self.canvas = _CrossfadeCurveCanvas(self)
            self.canvas.set_settings(self.settings)
            root.addWidget(self.canvas, 1)

            # Parameters Box
            grp_params = QGroupBox("Crossfade Geometry Parameters", self)
            grid = QGridLayout(grp_params)

            # Shape Selector
            grid.addWidget(QLabel("Crossfade Curve Shape:", grp_params), 0, 0)
            self.shape_combo = QComboBox(grp_params)
            self.shape_combo.addItems([
                "Equal Power (+3 dB Boost - Standard Film Dialogue)",
                "S-Curve (Logarithmic - Smooth Splice)",
                "Equal Gain (Linear)",
                "Exponential (Fast Cut)",
            ])
            self.shape_combo.currentIndexChanged.connect(self._on_shape_changed)
            grid.addWidget(self.shape_combo, 0, 1)

            # Duration Slider
            grid.addWidget(QLabel("Crossfade Duration (ms):", grp_params), 1, 0)
            self.slider_dur = QSlider(Qt.Orientation.Horizontal, grp_params)
            self.slider_dur.setRange(5, 200)
            self.slider_dur.setValue(25)
            self.slider_dur.valueChanged.connect(self._on_dur_changed)
            grid.addWidget(self.slider_dur, 1, 1)
            self.lbl_dur_val = QLabel("25 ms", grp_params)
            grid.addWidget(self.lbl_dur_val, 1, 2)

            # Midpoint Skew Slider
            grid.addWidget(QLabel("Midpoint Gain Skew (-50% to +50%):", grp_params), 2, 0)
            self.slider_skew = QSlider(Qt.Orientation.Horizontal, grp_params)
            self.slider_skew.setRange(-50, 50)
            self.slider_skew.setValue(0)
            self.slider_skew.valueChanged.connect(self._on_skew_changed)
            grid.addWidget(self.slider_skew, 2, 1)
            self.lbl_skew_val = QLabel("0%", grp_params)
            grid.addWidget(self.lbl_skew_val, 2, 2)

            root.addWidget(grp_params)

            # Action Bar
            bot = QHBoxLayout()
            self.audition_btn = QPushButton("🔊 Audition Spliced Transition", self)
            self.audition_btn.setStyleSheet(
                "background: #0284C7; color: #FFF; font-weight: 800; padding: 8px 20px;"
            )
            self.audition_btn.clicked.connect(self._audition_transition)
            bot.addWidget(self.audition_btn)

            bot.addStretch()

            apply_btn = QPushButton("✓ Apply Crossfade to Timeline", self)
            apply_btn.setStyleSheet(
                "background: #10B981; color: #FFF; font-weight: 800; padding: 8px 24px;"
            )
            apply_btn.clicked.connect(self._apply_and_close)
            bot.addWidget(apply_btn)

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.clicked.connect(self.reject)
            bot.addWidget(cancel_btn)

            root.addLayout(bot)

        def _on_shape_changed(self, idx: int) -> None:
            shapes = [
                CrossfadeShape.EQUAL_POWER,
                CrossfadeShape.S_CURVE,
                CrossfadeShape.EQUAL_GAIN,
                CrossfadeShape.EXPONENTIAL,
            ]
            self.settings.shape = shapes[idx]
            self.canvas.set_settings(self.settings)

        def _on_dur_changed(self, val: int) -> None:
            self.settings.duration_ms = float(val)
            self.lbl_dur_val.setText(f"{val} ms")
            self.canvas.set_settings(self.settings)

        def _on_skew_changed(self, val: int) -> None:
            self.settings.midpoint_skew_pct = float(val)
            self.lbl_skew_val.setText(f"{val:+d}%")
            self.canvas.set_settings(self.settings)

        def _audition_transition(self) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.audition_btn.setText("🔊 Audition Spliced Transition")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.audition_btn.setText("🔊 Audition Spliced Transition")
                )

            self.audition_btn.setText("⏹ Stop Audition")
            spliced = self.engine.splice_clips(self.clip_a, self.clip_b, self.settings)
            self._audition.play_clip(spliced)

        def _apply_and_close(self) -> None:
            spliced = self.engine.splice_clips(self.clip_a, self.clip_b, self.settings)
            self.crossfade_applied.emit(spliced)
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.accept()

        def reject(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().reject()

else:

    class CubaseCrossfadeDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def exec(self) -> int:
            return 0


__all__ = ["CubaseCrossfadeDialog"]
