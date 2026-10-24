"""
Split-Screen Lip-Sync Inspector & Viseme Aligner Dialog.

Provides side-by-side visual actor mouth ROI tracking against a synchronized
viseme timeline and audio waveform with interactive slip-and-slide ITU-R BT.1359
calibration controls.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from aidub.media.lipsync_viseme_engine import (
    LipSyncVisemeEngine,
    VisemeCue,
    VisemeGeometry,
    VisemeGroup,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import (
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QProgressBar,
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

    class _ActorMouthRoiWidget(QWidget):
        """
        Interactive visual monitor rendering actor face tracking and mouth kinematics.
        """

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumSize(280, 260)
            self.setStyleSheet("background: #090D14; border: 1px solid #1E293B; border-radius: 6px;")
            self._geometry = VisemeGeometry(openness=0.1, width=0.5, lip_protrusion=0.1, teeth_visible=False)
            self._current_viseme_label = "Rest"
            self._current_viseme_group = VisemeGroup.SILENCE

        def update_kinematics(self, geometry: VisemeGeometry, group: VisemeGroup, label: str) -> None:
            self._geometry = geometry
            self._current_viseme_group = group
            self._current_viseme_label = label
            self.update()

        def paintEvent(self, _event: Any) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            cx = w / 2.0
            cy = h / 2.0

            # 1. Dark Studio Viewport Background with Subtle Grid
            painter.fillRect(0, 0, w, h, QColor("#090D14"))
            painter.setPen(QPen(QColor("#15202E"), 1, Qt.PenStyle.DotLine))
            step = 30
            for x in range(step, w, step):
                painter.drawLine(x, 0, x, h)
            for y in range(step, h, step):
                painter.drawLine(0, y, w, y)

            # 2. Stylized Actor Head / Jaw Contour Wireframe
            head_path = QPainterPath()
            head_rx = min(w, h) * 0.36
            head_ry = min(w, h) * 0.44
            head_path.addEllipse(QPointF(cx, cy - 10), head_rx, head_ry)
            painter.setPen(QPen(QColor("#1E2D42"), 2))
            painter.setBrush(QBrush(QColor("#0E1624")))
            painter.drawPath(head_path)

            # Nose bridge indicator
            painter.setPen(QPen(QColor("#334B68"), 1.5))
            painter.drawLine(QPointF(cx, cy - 25), QPointF(cx - 4, cy - 5))
            painter.drawLine(QPointF(cx - 4, cy - 5), QPointF(cx + 4, cy - 5))

            # 3. Dynamic Mouth Opening & Lip Kinematics
            # Center of mouth is slightly below head center
            mouth_y = cy + 28
            max_width = head_rx * 0.95
            min_width = head_rx * 0.35
            eff_width = min_width + (max_width - min_width) * self._geometry.width

            max_open = 46.0
            min_open = 2.0
            eff_open = min_open + (max_open - min_open) * self._geometry.openness

            mouth_rect = QRectF(cx - eff_width / 2.0, mouth_y - eff_open / 2.0, eff_width, eff_open)

            # If mouth is open, draw inner oral cavity
            if eff_open > 5.0:
                inner_path = QPainterPath()
                inner_path.addEllipse(mouth_rect)
                painter.fillPath(inner_path, QBrush(QColor("#310C16")))

                # Upper teeth if exposed
                if self._geometry.teeth_visible:
                    teeth_rect = QRectF(cx - eff_width * 0.35, mouth_y - eff_open / 2.0, eff_width * 0.70, min(10.0, eff_open * 0.45))
                    painter.fillRect(teeth_rect, QColor("#F1F5F9"))

            # Upper and Lower Lip Curves
            lip_pen = QPen(QColor("#F43F5E"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(lip_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            upper_lip = QPainterPath()
            upper_lip.moveTo(cx - eff_width / 2.0, mouth_y)
            upper_lip.cubicTo(
                cx - eff_width * 0.25, mouth_y - eff_open / 2.0 - 4.0,
                cx + eff_width * 0.25, mouth_y - eff_open / 2.0 - 4.0,
                cx + eff_width / 2.0, mouth_y,
            )
            painter.drawPath(upper_lip)

            lower_lip = QPainterPath()
            lower_lip.moveTo(cx - eff_width / 2.0, mouth_y)
            lower_lip.cubicTo(
                cx - eff_width * 0.25, mouth_y + eff_open / 2.0 + 4.0,
                cx + eff_width * 0.25, mouth_y + eff_open / 2.0 + 4.0,
                cx + eff_width / 2.0, mouth_y,
            )
            painter.drawPath(lower_lip)

            # 4. Computer-Vision Face ROI Tracking Box (Cyan HUD)
            roi_box = QRectF(cx - eff_width * 0.75 - 12, mouth_y - max_open * 0.8 - 12, eff_width * 1.5 + 24, max_open * 1.6 + 24)
            painter.setPen(QPen(QColor("#06B6D4"), 1.5, Qt.PenStyle.DashLine))
            painter.drawRect(roi_box)

            # Tracking corner brackets
            cw = 8.0
            painter.setPen(QPen(QColor("#22D3EE"), 2.0))
            # Top-left
            painter.drawLine(QPointF(roi_box.left(), roi_box.top()), QPointF(roi_box.left() + cw, roi_box.top()))
            painter.drawLine(QPointF(roi_box.left(), roi_box.top()), QPointF(roi_box.left(), roi_box.top() + cw))
            # Bottom-right
            painter.drawLine(QPointF(roi_box.right(), roi_box.bottom()), QPointF(roi_box.right() - cw, roi_box.bottom()))
            painter.drawLine(QPointF(roi_box.right(), roi_box.bottom()), QPointF(roi_box.right(), roi_box.bottom() - cw))

            # HUD Label Badge
            painter.setFont(QFont("Cascadia Code", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#06B6D4"))
            painter.drawText(int(roi_box.left()), int(roi_box.top() - 6), "MOUTH_ROI [TRACKING LOCK]")

            # Current Viseme Overlay Tag
            painter.setFont(QFont("Inter", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#F8FAFC"))
            tag = f"Viseme: {self._current_viseme_label} ({self._current_viseme_group.value.upper()})"
            painter.drawText(12, h - 14, tag)


    class _VisemeTimelineWidget(QWidget):
        """
        Timeline widget rendering color-coded viseme blocks and scrubbing playhead.
        """

        playhead_scrubbed = Signal(float)  # current time in seconds

        # Viseme color palette
        COLOR_MAP: ClassVar[dict[VisemeGroup, str]] = {
            VisemeGroup.SILENCE: "#334155",
            VisemeGroup.BILABIAL: "#EF4444",
            VisemeGroup.LABIODENTAL: "#F59E0B",
            VisemeGroup.DENTAL_ALVEOLAR: "#10B981",
            VisemeGroup.VELAR_PALATAL: "#06B6D4",
            VisemeGroup.OPEN_VOWEL: "#8B5CF6",
            VisemeGroup.ROUNDED_VOWEL: "#EC4899",
            VisemeGroup.SPREAD_VOWEL: "#3B82F6",
        }

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(130)
            self.setStyleSheet("background:#0B0F17; border: 1px solid #1E293B; border-radius: 6px;")
            self._cues: list[VisemeCue] = []
            self._playhead_s: float = 0.0
            self._total_duration_s: float = 1.0
            self._offset_s: float = 0.0

        def set_cues(self, cues: list[VisemeCue], total_dur_s: float, offset_s: float = 0.0) -> None:
            self._cues = cues
            self._total_duration_s = max(0.2, total_dur_s)
            self._offset_s = offset_s
            self.update()

        def set_playhead(self, playhead_s: float) -> None:
            self._playhead_s = max(0.0, min(self._total_duration_s, playhead_s))
            self.update()

        def paintEvent(self, _event: Any) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            dur = self._total_duration_s

            # Background
            painter.fillRect(0, 0, w, h, QColor("#0B0F17"))

            # Track 1: Viseme Blocks
            track_y = 28
            track_h = 44

            for cue in self._cues:
                # Apply audio slip offset to time positions
                start_t = cue.start_s + self._offset_s
                end_t = cue.end_s + self._offset_s
                x1 = (start_t / dur) * w
                x2 = (end_t / dur) * w
                bw = max(2.0, x2 - x1)

                col = QColor(self.COLOR_MAP.get(cue.viseme, "#64748B"))
                painter.fillRect(QRectF(x1, track_y, bw, track_h), col)
                painter.setPen(QPen(col.darker(150), 1))
                painter.drawRect(QRectF(x1, track_y, bw, track_h))

                # Viseme Label
                if bw > 24:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.setFont(QFont("Cascadia Code", 8, QFont.Weight.Bold))
                    painter.drawText(
                        QRectF(x1 + 2, track_y + 12, bw - 4, 20),
                        Qt.AlignmentFlag.AlignCenter,
                        cue.label,
                    )

            # Track 2: Simulated Syllable Energy Envelope
            env_y = track_y + track_h + 8
            env_h = 28
            painter.fillRect(0, env_y, w, env_h, QColor("#0D1522"))
            painter.setPen(QPen(QColor("#2563EB"), 1.5))
            for cue in self._cues:
                start_t = cue.start_s + self._offset_s
                end_t = cue.end_s + self._offset_s
                x1 = (start_t / dur) * w
                x2 = (end_t / dur) * w
                geom = cue.geometry
                peak_h = env_h * (0.2 + 0.75 * geom.openness)
                painter.drawLine(QPointF(x1, env_y + env_h), QPointF((x1 + x2) / 2.0, env_y + env_h - peak_h))
                painter.drawLine(QPointF((x1 + x2) / 2.0, env_y + env_h - peak_h), QPointF(x2, env_y + env_h))

            # Playhead (Red Vertical Bar)
            px = (self._playhead_s / dur) * w
            painter.setPen(QPen(QColor("#EF4444"), 2))
            painter.drawLine(QPointF(px, 0), QPointF(px, h))
            # Top triangle marker
            head_marker = QPainterPath()
            head_marker.moveTo(px - 6, 0)
            head_marker.lineTo(px + 6, 0)
            head_marker.lineTo(px, 8)
            head_marker.closeSubpath()
            painter.fillPath(head_marker, QBrush(QColor("#EF4444")))

            # Time code text
            painter.setFont(QFont("Cascadia Code", 8))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(6, 18, f"00:00.00 | Playhead: {self._playhead_s:0.2f}s | Slip Offset: {self._offset_s * 1000.0:+.1f}ms")

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            self._handle_scrub(event.pos().x())

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._handle_scrub(event.pos().x())

        def _handle_scrub(self, mouse_x: int) -> None:
            w = max(1, self.width())
            frac = max(0.0, min(1.0, mouse_x / float(w)))
            target_time = frac * self._total_duration_s
            self.set_playhead(target_time)
            self.playhead_scrubbed.emit(target_time)


    class LipSyncInspectorDialog(QDialog):
        """
        Production Split-Screen Lip-Sync Inspector & Calibration Studio Dialog.
        """

        offset_applied = Signal(int, float)  # utterance_index, offset_seconds

        def __init__(
            self,
            utterance_index: int,
            dialogue_text: str,
            duration_s: float,
            language: str = "bn",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Split-Screen Lip-Sync Inspector & Viseme Aligner")
            self.resize(880, 560)
            self.setStyleSheet("background: #0B0E14; color: #F1F5F9; font-family: 'Inter', sans-serif;")

            self.utterance_index = utterance_index
            self.dialogue_text = dialogue_text
            self.duration_s = max(0.2, duration_s)
            self.language = language
            self._current_offset_ms: float = 0.0

            # Generate viseme cues
            self.cues = LipSyncVisemeEngine.generate_viseme_timeline(
                dialogue_text,
                start_time_s=0.0,
                duration_s=self.duration_s,
                language=language,
            )

            # Playback timer for scrubbing animation
            self._play_timer = QTimer(self)
            self._play_timer.setInterval(33)  # ~30fps
            self._play_timer.timeout.connect(self._on_playback_tick)
            self._is_playing = False
            self._play_pos_s = 0.0

            self._build_ui()
            self._update_compliance_metrics()

        def _build_ui(self) -> None:
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(16, 16, 16, 16)
            main_layout.setSpacing(12)

            # 1. Header Information Bar
            header_frame = QFrame(self)
            header_frame.setStyleSheet("background: #111722; border: 1px solid #1E293B; border-radius: 6px; padding: 6px;")
            h_lay = QHBoxLayout(header_frame)
            h_lay.setContentsMargins(10, 4, 10, 4)

            lbl_title = QLabel(f"<b>Line #{self.utterance_index + 1} Lip-Sync Studio</b> ({self.language.upper()})", header_frame)
            lbl_title.setStyleSheet("font-size: 13px; color: #38BDF8;")
            h_lay.addWidget(lbl_title)

            h_lay.addStretch()
            lbl_text = QLabel(f"Dialogue: \"{self.dialogue_text[:40]}{'...' if len(self.dialogue_text) > 40 else ''}\"", header_frame)
            lbl_text.setStyleSheet("color: #94A3B8; font-size: 11px;")
            h_lay.addWidget(lbl_text)

            main_layout.addWidget(header_frame)

            # 2. Main Split-Screen Layout (Left: Actor Mouth ROI, Right: Viseme Timeline)
            splitter = QSplitter(Qt.Orientation.Horizontal, self)
            splitter.setStyleSheet("QSplitter::handle{background: #1E293B; width: 4px;}")

            # Left Pane: Actor Mouth ROI
            left_container = QFrame(splitter)
            left_lay = QVBoxLayout(left_container)
            left_lay.setContentsMargins(0, 0, 6, 0)
            left_lbl = QLabel("VISUAL ACTOR MOUTH MONITOR (CV ROI)", left_container)
            left_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
            left_lay.addWidget(left_lbl)
            self.mouth_widget = _ActorMouthRoiWidget(left_container)
            left_lay.addWidget(self.mouth_widget, stretch=1)
            splitter.addWidget(left_container)

            # Right Pane: Viseme Timeline & Calibration
            right_container = QFrame(splitter)
            right_lay = QVBoxLayout(right_container)
            right_lay.setContentsMargins(6, 0, 0, 0)
            right_lay.setSpacing(8)

            right_lbl = QLabel("VISEME CADENCE & ITU-R BT.1359 ALIGNMENT", right_container)
            right_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748B;")
            right_lay.addWidget(right_lbl)

            self.timeline_widget = _VisemeTimelineWidget(right_container)
            self.timeline_widget.set_cues(self.cues, self.duration_s, 0.0)
            self.timeline_widget.playhead_scrubbed.connect(self._on_playhead_scrubbed)
            right_lay.addWidget(self.timeline_widget, stretch=1)

            # Compliance Gauge Card
            gauge_card = QFrame(right_container)
            gauge_card.setStyleSheet("background: #111722; border: 1px solid #1E293B; border-radius: 6px; padding: 8px;")
            g_lay = QVBoxLayout(gauge_card)
            g_lay.setContentsMargins(8, 8, 8, 8)
            g_lay.setSpacing(6)

            top_g_row = QHBoxLayout()
            self.lbl_compliance_title = QLabel("Lip-Sync Compliance Index: 100% (BROADCAST PASS)", gauge_card)
            self.lbl_compliance_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #10B981;")
            top_g_row.addWidget(self.lbl_compliance_title)
            top_g_row.addStretch()
            self.lbl_offset_badge = QLabel("Offset: 0.0 ms (In Sync)", gauge_card)
            self.lbl_offset_badge.setStyleSheet("font-size: 10px; color: #94A3B8;")
            top_g_row.addWidget(self.lbl_offset_badge)
            g_lay.addLayout(top_g_row)

            self.compliance_bar = QProgressBar(gauge_card)
            self.compliance_bar.setRange(0, 100)
            self.compliance_bar.setValue(100)
            self.compliance_bar.setFixedHeight(8)
            self.compliance_bar.setTextVisible(False)
            self.compliance_bar.setStyleSheet(
                "QProgressBar{background: #1E293B; border-radius: 4px;}"
                "QProgressBar::chunk{background: #10B981; border-radius: 4px;}"
            )
            g_lay.addWidget(self.compliance_bar)

            self.lbl_advice = QLabel("", gauge_card)
            self.lbl_advice.setStyleSheet("font-size: 10px; color: #CBD5E1;")
            self.lbl_advice.setWordWrap(True)
            g_lay.addWidget(self.lbl_advice)

            right_lay.addWidget(gauge_card)
            splitter.addWidget(right_container)
            splitter.setStretchFactor(0, 4)
            splitter.setStretchFactor(1, 6)

            main_layout.addWidget(splitter, stretch=1)

            # 3. Slip-and-Slide Interactive Calibration Controls
            ctrl_card = QFrame(self)
            ctrl_card.setStyleSheet("background: #0E131E; border: 1px solid #1E293B; border-radius: 6px; padding: 8px;")
            c_lay = QVBoxLayout(ctrl_card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            c_lay.setSpacing(8)

            slider_row = QHBoxLayout()
            lbl_slip = QLabel("Slip-and-Slide Audio Alignment Offset:", ctrl_card)
            lbl_slip.setStyleSheet("font-size: 11px; font-weight: bold; color: #E2E8F0;")
            slider_row.addWidget(lbl_slip)

            # Slider from -300ms to +300ms
            self.slip_slider = QSlider(Qt.Orientation.Horizontal, ctrl_card)
            self.slip_slider.setRange(-300, 300)
            self.slip_slider.setValue(0)
            self.slip_slider.setStyleSheet(
                "QSlider::groove:horizontal{height: 6px; background: #1E293B; border-radius: 3px;}"
                "QSlider::sub-page:horizontal{background: #2563EB; border-radius: 3px;}"
                "QSlider::handle:horizontal{width: 14px; margin: -5px 0; background: #38BDF8; border-radius: 7px;}"
            )
            self.slip_slider.valueChanged.connect(self._on_slider_changed)
            slider_row.addWidget(self.slip_slider, stretch=1)

            self.lbl_slider_val = QLabel("  0.0 ms (0.0 frames @ 30fps)", ctrl_card)
            self.lbl_slider_val.setStyleSheet("font-family: 'Cascadia Code'; font-size: 11px; color: #38BDF8; min-width: 170px;")
            slider_row.addWidget(self.lbl_slider_val)
            c_lay.addLayout(slider_row)

            # Nudge Buttons Row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)

            self.btn_nudge_left = QPushButton("◀ -1 Frame (-33ms)", ctrl_card)
            self.btn_nudge_left.setStyleSheet("QPushButton{background: #1E293B; color: #CBD5E1; border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; font-size: 10px;}")
            self.btn_nudge_left.clicked.connect(lambda: self.slip_slider.setValue(self.slip_slider.value() - 33))
            btn_row.addWidget(self.btn_nudge_left)

            self.btn_reset_slip = QPushButton("Reset Alignment (0ms)", ctrl_card)
            self.btn_reset_slip.setStyleSheet("QPushButton{background: #1E293B; color: #CBD5E1; border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; font-size: 10px;}")
            self.btn_reset_slip.clicked.connect(lambda: self.slip_slider.setValue(0))
            btn_row.addWidget(self.btn_reset_slip)

            self.btn_nudge_right = QPushButton("+1 Frame (+33ms) ▶", ctrl_card)
            self.btn_nudge_right.setStyleSheet("QPushButton{background: #1E293B; color: #CBD5E1; border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; font-size: 10px;}")
            self.btn_nudge_right.clicked.connect(lambda: self.slip_slider.setValue(self.slip_slider.value() + 33))
            btn_row.addWidget(self.btn_nudge_right)

            btn_row.addStretch()

            self.btn_play_preview = QPushButton("▶ Play Visual Sync Preview", ctrl_card)
            self.btn_play_preview.setStyleSheet(
                "QPushButton{background: #2563EB; color: #FFF; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px;}"
                "QPushButton:hover{background: #1D4ED8;}"
            )
            self.btn_play_preview.clicked.connect(self._toggle_playback)
            btn_row.addWidget(self.btn_play_preview)

            self.btn_apply_offset = QPushButton("✓ Apply Slip Offset to Timeline", ctrl_card)
            self.btn_apply_offset.setStyleSheet(
                "QPushButton{background: #10B981; color: #FFF; font-weight: bold; border: none; padding: 6px 14px; border-radius: 4px; font-size: 11px;}"
                "QPushButton:hover{background: #059669;}"
            )
            self.btn_apply_offset.clicked.connect(self._on_apply_offset)
            btn_row.addWidget(self.btn_apply_offset)

            c_lay.addLayout(btn_row)
            main_layout.addWidget(ctrl_card)

        def _on_slider_changed(self, value: int) -> None:
            self._current_offset_ms = float(value)
            frames = self._current_offset_ms / 33.333
            self.lbl_slider_val.setText(f"{self._current_offset_ms:+6.1f} ms ({frames:+3.1f} frames @ 30fps)")
            self.timeline_widget.set_cues(self.cues, self.duration_s, offset_s=self._current_offset_ms / 1000.0)
            self._update_compliance_metrics()
            # Also update mouth preview at current playhead
            self._on_playhead_scrubbed(self._play_pos_s)

        def _update_compliance_metrics(self) -> None:
            report = LipSyncVisemeEngine.evaluate_lip_sync_compliance(self.cues, self._current_offset_ms)
            pct = int(report.compliance_score * 100)
            self.compliance_bar.setValue(pct)

            if report.is_broadcast_compliant:
                status_color = "#10B981"
                status_text = "BROADCAST PASS"
            else:
                status_color = "#EF4444" if pct < 60 else "#F59E0B"
                status_text = "OUT OF SYNC" if pct < 60 else "SLIGHT DRIFT"

            self.lbl_compliance_title.setText(f"Lip-Sync Compliance Index: {pct}% ({status_text})")
            self.lbl_compliance_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {status_color};")
            self.compliance_bar.setStyleSheet(
                f"QProgressBar{{background: #1E293B; border-radius: 4px;}}"
                f"QProgressBar::chunk{{background: {status_color}; border-radius: 4px;}}"
            )
            self.lbl_offset_badge.setText(f"Offset: {self._current_offset_ms:+.1f} ms ({report.lead_lag_status})")
            self.lbl_advice.setText(report.remediation_advice)

        def _on_playhead_scrubbed(self, playhead_s: float) -> None:
            self._play_pos_s = playhead_s
            # Compute interpolated mouth geometry
            offset_s = self._current_offset_ms / 1000.0
            adjusted_t = max(0.0, playhead_s - offset_s)
            geom = LipSyncVisemeEngine.interpolate_mouth_geometry(self.cues, adjusted_t)

            # Determine active viseme group and label
            active_group = VisemeGroup.SILENCE
            active_label = "Rest"
            for c in self.cues:
                if c.start_s <= adjusted_t <= c.end_s:
                    active_group = c.viseme
                    active_label = c.label
                    break

            self.mouth_widget.update_kinematics(geom, active_group, active_label)

        def _toggle_playback(self) -> None:
            if self._is_playing:
                self._play_timer.stop()
                self._is_playing = False
                self.btn_play_preview.setText("▶ Play Visual Sync Preview")
            else:
                if self._play_pos_s >= self.duration_s:
                    self._play_pos_s = 0.0
                self._play_timer.start()
                self._is_playing = True
                self.btn_play_preview.setText("⏸ Pause Sync Preview")

        def _on_playback_tick(self) -> None:
            self._play_pos_s += 0.033
            if self._play_pos_s > self.duration_s:
                self._play_pos_s = self.duration_s
                self._toggle_playback()
            self.timeline_widget.set_playhead(self._play_pos_s)
            self._on_playhead_scrubbed(self._play_pos_s)

        def _on_apply_offset(self) -> None:
            offset_s = self._current_offset_ms / 1000.0
            logger.info("Applying lip-sync slip offset: utterance #%d, offset=%.4fs", self.utterance_index, offset_s)
            self.offset_applied.emit(self.utterance_index, offset_s)
            self.accept()


__all__ = [
    "LipSyncInspectorDialog",
]
