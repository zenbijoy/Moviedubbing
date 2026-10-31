"""
Cubase Pro Audio Alignment Panel Dialog (VocAlign Pro Equivalent).

Features:
  - Visual dual-waveform display: Guide (Original Actor) vs Target (Dubbed Line).
  - Real-time Dynamic Time Warping alignment with pitch preservation.
  - 3 Tolerance Modes (Tight, Standard, Loose).
  - Telemetry HUD showing correlation improvement and millisecond drift metrics.
  - A/B auditioning (Aligned Dub vs Original Actor Guide).
  - 1-Click apply to master timeline take.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.media.cubase_audio_align import (
    AlignmentReport,
    AlignmentTolerance,
    CubaseAudioAlignmentEngine,
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
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class _DualAlignmentWaveformCanvas(QWidget):
        """Displays Guide audio (top) and Target/Aligned audio (bottom) side-by-side."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(200)
            self.setStyleSheet("background: #090D16; border: 1px solid #1E293B; border-radius: 8px;")
            self.guide_clip: AudioClipData | None = None
            self.target_clip: AudioClipData | None = None

        def set_clips(
            self, guide: AudioClipData | None, target: AudioClipData | None
        ) -> None:
            self.guide_clip = guide
            self.target_clip = target
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()
            half_h = h / 2.0

            # Divider line
            painter.setPen(QPen(QColor("#1E293B"), 1))
            painter.drawLine(0, int(half_h), w, int(half_h))

            # 1. Guide Waveform (Gold / Amber)
            if self.guide_clip and self.guide_clip.samples.size > 0:
                painter.setPen(QColor("#F59E0B"))
                painter.drawText(10, 16, "ORIGINAL ACTOR GUIDE (REFERENCE)")
                self._render_half_waveform(painter, self.guide_clip.samples, 0, half_h, QColor("#F59E0B"))

            # 2. Target Waveform (Cyan / Sky)
            if self.target_clip and self.target_clip.samples.size > 0:
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(10, int(half_h) + 16, "DUBBED TAKE (TARGET / ALIGNED)")
                self._render_half_waveform(
                    painter, self.target_clip.samples, half_h, half_h, QColor("#38BDF8")
                )

        def _render_half_waveform(
            self,
            painter: QPainter,
            samples: Any,
            y_offset: float,
            track_h: float,
            color: QColor,
        ) -> None:
            w = self.width()
            mid_y = y_offset + (track_h / 2.0)
            step = max(1, samples.size // w)

            painter.setPen(QPen(color, 1))
            for x in range(w):
                s = x * step
                e = s + step
                sub = samples[s:e]
                if sub.size > 0:
                    min_val = float(sub.min())
                    max_val = float(sub.max())
                    y1 = mid_y - (max_val * (track_h * 0.42))
                    y2 = mid_y - (min_val * (track_h * 0.42))
                    painter.drawLine(x, int(y1), x, int(y2))

    class CubaseAudioAlignmentDialog(QDialog):
        """Cubase Pro Audio Alignment Panel Dialog."""

        alignment_applied = Signal(object)  # emits aligned AudioClipData

        def __init__(
            self,
            guide_clip: AudioClipData,
            target_clip: AudioClipData,
            cue_id: str = "cue_001",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.guide_clip = guide_clip
            self.target_clip = target_clip
            self.aligned_clip = target_clip.clone()
            self.cue_id = cue_id
            self.engine = CubaseAudioAlignmentEngine()

            self.setWindowTitle(f"Cubase Audio Alignment Panel — Timing Synchronizer [{cue_id}]")
            self.setMinimumSize(920, 580)
            self.setStyleSheet(
                "QDialog { background: #0B0E17; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #38BDF8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QComboBox { background: #162032; color: #F8FAFC; border: 1px solid #233045; border-radius: 6px; padding: 6px; }"
                "QPushButton { background: #162032; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 7px 16px; font-size: 11px; font-weight: 700; }"
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
            t_lbl = QLabel("📐 CUBASE AUDIO ALIGNMENT PANEL (VOCALIGN PRO CLONE)", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #38BDF8;")
            s_lbl = QLabel(
                "Synchronize syllable attack, vowel length, and timing to original film dialogue.",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            btn_align = QPushButton("⚡ Align Dialogue Take", self)
            btn_align.setStyleSheet(
                "background: #2563EB; color: #FFF; font-weight: 800; font-size: 12px; padding: 8px 18px;"
            )
            btn_align.clicked.connect(self._run_alignment)
            header.addWidget(btn_align)

            root.addLayout(header)

            # Waveform canvas
            self.canvas = _DualAlignmentWaveformCanvas(self)
            self.canvas.set_clips(self.guide_clip, self.target_clip)
            root.addWidget(self.canvas, 1)

            # Settings and Telemetry Box
            mid_row = QHBoxLayout()

            grp_settings = QGroupBox("Alignment Settings", self)
            set_lay = QVBoxLayout(grp_settings)
            set_lay.addWidget(QLabel("Matching Tolerance Mode:", grp_settings))
            self.tolerance_combo = QComboBox(grp_settings)
            self.tolerance_combo.addItems([
                "Standard (85% - Natural Dubbing Cadence)",
                "Tight (100% - Precision Lip-Sync Lock)",
                "Loose (65% - Phrasing Freedom)",
            ])
            set_lay.addWidget(self.tolerance_combo)
            mid_row.addWidget(grp_settings, 1)

            grp_stats = QGroupBox("Alignment Telemetry HUD", self)
            stats_lay = QGridLayout(grp_stats)
            self.lbl_corr = QLabel("Correlation: Unanalyzed", grp_stats)
            self.lbl_drift = QLabel("Max Drift: -- ms", grp_stats)
            self.lbl_improvement = QLabel("Sync Improvement: --%", grp_stats)
            stats_lay.addWidget(self.lbl_corr, 0, 0)
            stats_lay.addWidget(self.lbl_drift, 0, 1)
            stats_lay.addWidget(self.lbl_improvement, 1, 0, 1, 2)
            mid_row.addWidget(grp_stats, 1)

            root.addLayout(mid_row)

            # Action bar
            bot = QHBoxLayout()
            self.btn_audition_aligned = QPushButton("🔊 Audition Aligned Dub", self)
            self.btn_audition_aligned.clicked.connect(self._audition_aligned)
            bot.addWidget(self.btn_audition_aligned)

            self.btn_audition_guide = QPushButton("🎬 Audition Actor Guide", self)
            self.btn_audition_guide.clicked.connect(self._audition_guide)
            bot.addWidget(self.btn_audition_guide)

            bot.addStretch()

            apply_btn = QPushButton("✓ Apply Aligned Dialogue to Timeline", self)
            apply_btn.setStyleSheet(
                "background: #10B981; color: #FFF; font-weight: 800; padding: 8px 22px;"
            )
            apply_btn.clicked.connect(self._apply_and_close)
            bot.addWidget(apply_btn)

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.clicked.connect(self.reject)
            bot.addWidget(cancel_btn)

            root.addLayout(bot)

        def _run_alignment(self) -> None:
            tol_idx = self.tolerance_combo.currentIndex()
            tol = (
                AlignmentTolerance.STANDARD
                if tol_idx == 0
                else (AlignmentTolerance.TIGHT if tol_idx == 1 else AlignmentTolerance.LOOSE)
            )

            aligned, report = self.engine.align_dialogue(
                self.guide_clip, self.target_clip, tolerance=tol
            )
            self.aligned_clip = aligned
            self.canvas.set_clips(self.guide_clip, self.aligned_clip)

            self.lbl_corr.setText(
                f"Correlation: {report.initial_correlation:.2f} ➔ {report.aligned_correlation:.2f}"
            )
            self.lbl_drift.setText(f"Max Drift: {report.max_drift_ms:.1f}ms")
            self.lbl_improvement.setText(
                f"Sync Improvement: +{report.correlation_improvement_pct:.1f}% ({report.tolerance_mode.value.upper()} mode)"
            )

            QMessageBox.information(
                self,
                "Dialogue Aligned",
                f"Audio Alignment complete!\n\nCorrelation: {report.initial_correlation:.2f} ➔ {report.aligned_correlation:.2f}\n"
                f"Sync Improvement: +{report.correlation_improvement_pct:.1f}%\n"
                f"Max Timing Drift: {report.max_drift_ms:.1f} ms",
            )

        def _audition_aligned(self) -> None:
            self._play_clip(self.aligned_clip, self.btn_audition_aligned, "🔊 Audition Aligned Dub")

        def _audition_guide(self) -> None:
            self._play_clip(self.guide_clip, self.btn_audition_guide, "🎬 Audition Actor Guide")

        def _play_clip(self, clip: AudioClipData, btn: QPushButton, default_text: str) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                btn.setText(default_text)
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(lambda: btn.setText(default_text))

            btn.setText("⏹ Stop")
            self._audition.play_clip(clip)

        def _apply_and_close(self) -> None:
            self.alignment_applied.emit(self.aligned_clip)
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.accept()

        def reject(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().reject()

else:

    class CubaseAudioAlignmentDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def exec(self) -> int:
            return 0


__all__ = ["CubaseAudioAlignmentDialog"]
