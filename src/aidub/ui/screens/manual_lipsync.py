"""
Manual Lip-Sync Studio Screen for Frame-Accurate Visual Dubbing.

Provides:
  - Lead-lag offset calibration with ITU-R BT.1359 compliance verification.
  - Interactive live Actor Mouth ROI Kinematics Preview (openness, width, teeth, protrusion).
  - Frame nudging: -5 Fr (-165ms), -1 Fr (-33ms), Reset (0ms), +1 Fr (+33ms), +5 Fr (+165ms).
  - Real-time 24fps transport preview (Play / Pause / Scrub).
  - Per-shot quality tier picker (MuseTalk Preview vs LatentSync Cinema).
  - Manual viseme override at current playhead position.
  - 3D Mocap Rig JSON export for DCC tools.
  - Headless safe for headless test runs.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.lipsync.manual_lipsync import ManualLipSyncService
from aidub.domain.viseme import VISEME_GEOMETRIES, VisemeGeometry, VisemeGroup, VisemeKeyframe, VisemeTimeline
from aidub.ui.timeline.viseme_lane import VisemeLaneWidget

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


if _QT_AVAILABLE:

    class _ActorMouthPreviewWidget(QWidget):
        """Interactive visual monitor rendering actor mouth kinematics and viseme aperture."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumSize(240, 180)
            self.setStyleSheet("background: #090D14; border: 1px solid #1E293B; border-radius: 6px;")
            self._geometry = VisemeGeometry(openness=0.1, width=0.5, lip_protrusion=0.1, teeth_visible=False)
            self._viseme_label = "SILENCE"
            self._viseme_group = VisemeGroup.SILENCE

        def set_viseme(self, group: VisemeGroup, geometry: VisemeGeometry | None = None) -> None:
            self._viseme_group = group
            self._geometry = geometry or VISEME_GEOMETRIES.get(group, VISEME_GEOMETRIES[VisemeGroup.SILENCE])
            self._viseme_label = group.value.upper()
            self.update()

        def paintEvent(self, _event: Any) -> None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            cx = w / 2.0
            cy = h / 2.0

            # Dark Background Grid
            painter.fillRect(0, 0, w, h, QColor("#090D14"))
            painter.setPen(QPen(QColor("#15202E"), 1, Qt.PenStyle.DotLine))
            step = 25
            for x in range(step, w, step):
                painter.drawLine(x, 0, x, h)
            for y in range(step, h, step):
                painter.drawLine(0, y, w, y)

            # Stylized Head / Chin Wireframe
            head_path = QPainterPath()
            head_rx = min(w, h) * 0.36
            head_ry = min(w, h) * 0.44
            head_path.addEllipse(QPointF(cx, cy - 8), head_rx, head_ry)
            painter.setPen(QPen(QColor("#1E2D42"), 2))
            painter.setBrush(QBrush(QColor("#0E1624")))
            painter.drawPath(head_path)

            # Dynamic Mouth Opening & Lip Kinematics
            mouth_y = cy + 22
            max_width = head_rx * 0.95
            min_width = head_rx * 0.35
            eff_width = min_width + (max_width - min_width) * self._geometry.width

            max_open = 42.0
            min_open = 2.0
            eff_open = min_open + (max_open - min_open) * self._geometry.openness
            mouth_rect = QRectF(cx - eff_width / 2.0, mouth_y - eff_open / 2.0, eff_width, eff_open)

            # Inner oral cavity
            if eff_open > 4.0:
                inner_path = QPainterPath()
                inner_path.addEllipse(mouth_rect)
                painter.fillPath(inner_path, QBrush(QColor("#310C16")))

                # Upper teeth if exposed
                if self._geometry.teeth_visible:
                    teeth_rect = QRectF(
                        cx - eff_width * 0.35,
                        mouth_y - eff_open / 2.0,
                        eff_width * 0.70,
                        min(8.0, eff_open * 0.45),
                    )
                    painter.fillRect(teeth_rect, QColor("#F1F5F9"))

            # Lip Curves
            lip_pen = QPen(QColor("#F43F5E"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(lip_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            upper_lip = QPainterPath()
            upper_lip.moveTo(cx - eff_width / 2.0, mouth_y)
            upper_lip.cubicTo(
                cx - eff_width * 0.25, mouth_y - eff_open / 2.0 - 3.0,
                cx + eff_width * 0.25, mouth_y - eff_open / 2.0 - 3.0,
                cx + eff_width / 2.0, mouth_y,
            )
            painter.drawPath(upper_lip)

            lower_lip = QPainterPath()
            lower_lip.moveTo(cx - eff_width / 2.0, mouth_y)
            lower_lip.cubicTo(
                cx - eff_width * 0.25, mouth_y + eff_open / 2.0 + 3.0,
                cx + eff_width * 0.25, mouth_y + eff_open / 2.0 + 3.0,
                cx + eff_width / 2.0, mouth_y,
            )
            painter.drawPath(lower_lip)

            # Viseme & Kinematic HUD Label
            painter.setPen(QColor("#38BDF8"))
            painter.setFont(QFont("Cascadia Code", 9, QFont.Weight.Bold))
            painter.drawText(8, 20, f"VISEME: {self._viseme_label}")
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(8, 36, f"Open: {self._geometry.openness:.2f} | Width: {self._geometry.width:.2f}")


    class ManualLipSyncScreen(QWidget):
        """Full Frame-Accurate Manual Lip-Sync Studio Screen."""

        offset_applied = Signal(str, float)  # (utterance_id, offset_ms)

        def __init__(
            self,
            timeline: VisemeTimeline | None = None,
            service: ManualLipSyncService | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.service: ManualLipSyncService = service or ManualLipSyncService()
            self.timeline: VisemeTimeline = timeline or VisemeTimeline(
                utterance_id="utt_sample",
                duration_s=2.5,
                keyframes=[
                    VisemeKeyframe(viseme=VisemeGroup.BILABIAL, start_s=0.0, end_s=0.3),
                    VisemeKeyframe(viseme=VisemeGroup.OPEN_VOWEL, start_s=0.3, end_s=1.0),
                    VisemeKeyframe(viseme=VisemeGroup.LABIODENTAL, start_s=1.0, end_s=1.7),
                    VisemeKeyframe(viseme=VisemeGroup.SILENCE, start_s=1.7, end_s=2.5),
                ],
            )
            self.service.register_timeline(self.timeline)
            self._current_time_s: float = 0.0
            self._playback_timer = QTimer(self)
            self._playback_timer.setInterval(41)  # ~24 fps
            self._playback_timer.timeout.connect(self._on_playback_step)

            self.setWindowTitle("Manual Lip-Sync Studio (ITU-R BT.1359)")
            self.resize(980, 580)
            self._init_ui()
            self._update_status()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title = QLabel("👄 Frame-Accurate Viseme & Lip-Sync Studio")
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
            header.addWidget(title)
            header.addStretch()

            tier_lbl = QLabel("Tier:")
            tier_lbl.setStyleSheet("color: #94A3B8; font-weight: bold;")
            header.addWidget(tier_lbl)

            self.combo_tier = QComboBox()
            self.combo_tier.addItems(["Cinema Tier (LatentSync UNet)", "Preview Tier (MuseTalk Fast)"])
            self.combo_tier.currentTextChanged.connect(self._on_tier_changed)
            header.addWidget(self.combo_tier)
            layout.addLayout(header)

            # Upper Split: Actor Mouth ROI on Left, Viseme Timeline on Right
            mid_split = QHBoxLayout()
            self.mouth_preview = _ActorMouthPreviewWidget(self)
            mid_split.addWidget(self.mouth_preview, stretch=1)

            timeline_box = QVBoxLayout()
            self.viseme_lane = VisemeLaneWidget(self)
            self.viseme_lane.set_timeline(self.timeline)
            self.viseme_lane.playhead_scrubbed.connect(self._on_seek_playhead)
            timeline_box.addWidget(self.viseme_lane)

            # Scrub Transport Controls
            transport_row = QHBoxLayout()
            self.btn_play = QPushButton("▶ Play Animation")
            self.btn_play.setStyleSheet("background: #059669; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            self.btn_play.clicked.connect(self._toggle_playback)
            transport_row.addWidget(self.btn_play)

            self.btn_stop = QPushButton("⏹ Stop")
            self.btn_stop.clicked.connect(self._stop_playback)
            transport_row.addWidget(self.btn_stop)

            self.lbl_timecode = QLabel("00:00:00:00 (Fr 0)")
            self.lbl_timecode.setStyleSheet("color: #38BDF8; font-family: 'Cascadia Code', monospace; font-weight: bold;")
            transport_row.addWidget(self.lbl_timecode)
            transport_row.addStretch()
            timeline_box.addLayout(transport_row)

            # ITU Compliance Status Box
            self.lbl_compliance = QLabel("")
            self.lbl_compliance.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
            timeline_box.addWidget(self.lbl_compliance)

            mid_split.addLayout(timeline_box, stretch=2)
            layout.addLayout(mid_split)

            # Controls Box
            ctrl_group = QGroupBox("Slip-and-Slide Synchronization Nudge (±1 / ±5 Frames)")
            ctrl_group.setStyleSheet("QGroupBox{color: #38BDF8; font-weight: bold;}")
            ctrl_layout = QVBoxLayout(ctrl_group)

            btn_row = QHBoxLayout()
            self.btn_nudge_l5 = QPushButton("⏪ -5 Fr (-165ms)")
            self.btn_nudge_l5.clicked.connect(lambda: self._nudge(-165.0))
            btn_row.addWidget(self.btn_nudge_l5)

            self.btn_nudge_l1 = QPushButton("◀ -1 Fr (-33ms)")
            self.btn_nudge_l1.clicked.connect(lambda: self._nudge(-33.0))
            btn_row.addWidget(self.btn_nudge_l1)

            self.btn_reset = QPushButton("Reset (0ms)")
            self.btn_reset.clicked.connect(self._on_reset)
            btn_row.addWidget(self.btn_reset)

            self.btn_nudge_r1 = QPushButton("+1 Fr (+33ms) ▶")
            self.btn_nudge_r1.clicked.connect(lambda: self._nudge(33.0))
            btn_row.addWidget(self.btn_nudge_r1)

            self.btn_nudge_r5 = QPushButton("+5 Fr (+165ms) ⏩")
            self.btn_nudge_r5.clicked.connect(lambda: self._nudge(165.0))
            btn_row.addWidget(self.btn_nudge_r5)
            ctrl_layout.addLayout(btn_row)

            # Override Row
            override_row = QHBoxLayout()
            override_row.addWidget(QLabel("Override Active Viseme:"))
            self.combo_viseme = QComboBox()
            self.combo_viseme.addItems([vg.value.upper() for vg in VisemeGroup])
            override_row.addWidget(self.combo_viseme)

            self.btn_override = QPushButton("✏️ Set Viseme at Playhead")
            self.btn_override.clicked.connect(self._on_override_viseme)
            override_row.addWidget(self.btn_override)

            override_row.addStretch()

            self.btn_mocap = QPushButton("💾 Export Mocap (.json)")
            self.btn_mocap.clicked.connect(self._on_export_mocap)
            override_row.addWidget(self.btn_mocap)

            ctrl_layout.addLayout(override_row)
            layout.addWidget(ctrl_group)

        def _toggle_playback(self) -> None:
            if self._playback_timer.isActive():
                self._playback_timer.stop()
                self.btn_play.setText("▶ Play Animation")
            else:
                if self._current_time_s >= self.timeline.duration_s:
                    self._current_time_s = 0.0
                self._playback_timer.start()
                self.btn_play.setText("⏸ Pause")

        def _stop_playback(self) -> None:
            self._playback_timer.stop()
            self.btn_play.setText("▶ Play Animation")
            self._on_seek_playhead(0.0)

        def _on_playback_step(self) -> None:
            self._current_time_s += 0.041
            if self._current_time_s > self.timeline.duration_s:
                self._current_time_s = 0.0
            self._update_playhead(self._current_time_s)

        def _on_seek_playhead(self, time_s: float) -> None:
            self._current_time_s = max(0.0, min(self.timeline.duration_s, time_s))
            self._update_playhead(self._current_time_s)

        def _update_playhead(self, time_s: float) -> None:
            self.viseme_lane.set_playhead(time_s)
            kf = self.timeline.get_active_viseme_at(time_s)
            if kf:
                self.mouth_preview.set_viseme(kf.viseme, kf.geometry)

            frame = int(time_s * 24.0)
            sec = int(time_s)
            fr = frame % 24
            self.lbl_timecode.setText(f"00:00:{sec:02d}:{fr:02d} (Fr {frame})")

        def _nudge(self, delta_ms: float) -> None:
            self.service.nudge_offset(self.timeline.utterance_id, delta_ms)
            self.viseme_lane.update()
            self._update_status()

        def _on_reset(self) -> None:
            self.timeline.lead_lag_offset_ms = 0.0
            self.viseme_lane.update()
            self._update_status()

        def _on_tier_changed(self, text: str) -> None:
            tier = "cinema" if "Cinema" in text else "preview"
            self.service.set_quality_tier(self.timeline.utterance_id, tier)

        def _on_override_viseme(self) -> None:
            selected_str = self.combo_viseme.currentText().lower()
            vg = VisemeGroup(selected_str)
            self.service.override_viseme(self.timeline.utterance_id, self._current_time_s, vg)
            self.viseme_lane.update()
            self._update_playhead(self._current_time_s)

        def _update_status(self) -> None:
            compliant, msg, offset = self.service.evaluate_compliance(self.timeline.utterance_id)
            if compliant:
                self.lbl_compliance.setStyleSheet("color: #10B981; font-weight: bold; background: #064E3B; border-radius: 4px; padding: 4px 8px;")
            else:
                self.lbl_compliance.setStyleSheet("color: #F87171; font-weight: bold; background: #7F1D1D; border-radius: 4px; padding: 4px 8px;")
            self.lbl_compliance.setText(f"ITU-R BT.1359 Calibration: {offset:+.1f} ms — {msg}")

        def _on_export_mocap(self) -> None:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Export 3D Viseme Mocap Rig", f"{self.timeline.utterance_id}_mocap.json", "JSON (*.json)"
            )
            if save_path:
                self.service.export_mocap_rig_json(self.timeline.utterance_id, save_path)
                QMessageBox.information(self, "Mocap Exported", f"Successfully exported mocap data to:\n{save_path}")

        def closeEvent(self, event: Any) -> None:
            self._playback_timer.stop()
            super().closeEvent(event)

else:
    class ManualLipSyncScreen:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.service = ManualLipSyncService()


__all__ = [
    "ManualLipSyncScreen",
]
