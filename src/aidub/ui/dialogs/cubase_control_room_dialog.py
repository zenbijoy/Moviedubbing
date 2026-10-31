"""
Cubase Pro Control Room Studio Dialog & Master Monitoring Matrix.

Features:
  - DAW-grade Control Room separating master mix bus from listening environment.
  - A/B Reference Monitor Switch: 1-Click switch between Dub and Original Actor Guide.
  - Mono Downmix fold-down to check phase cancellation and broadcast mono clarity.
  - Dim Monitor switch (-20 dB).
  - ADR Booth Talkback matrix.
  - Real-time EBU R128 / ITU-R BS.1770 Broadcast Loudness Meter (Integrated LUFS, True Peak).
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.media.cubase_control_room import (
    CubaseControlRoomEngine,
    LoudnessTelemetry,
    MonitorSource,
)
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
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

    class CubaseControlRoomDialog(QDialog):
        """Cubase Pro Control Room Studio Master Monitoring Dialog."""

        def __init__(
            self,
            dub_clip: AudioClipData,
            guide_clip: AudioClipData | None = None,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.dub_clip = dub_clip
            self.guide_clip = guide_clip
            self.engine = CubaseControlRoomEngine()

            self.setWindowTitle("Cubase Control Room — Master Monitoring Matrix & EBU R128 Radar")
            self.setMinimumSize(880, 520)
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
            self._update_telemetry()

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(14)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("🎛️ CUBASE CONTROL ROOM & MONITOR MATRIX", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #38BDF8;")
            s_lbl = QLabel(
                "Dedicated master monitoring environment, A/B reference switching, and EBU R128 compliance.",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            root.addLayout(header)

            # Main Section Split
            mid_split = QHBoxLayout()
            mid_split.setSpacing(14)

            # Left Pane: Monitor Source Selector & Matrix Switches
            grp_matrix = QGroupBox("Monitor Source Matrix", self)
            matrix_lay = QVBoxLayout(grp_matrix)

            self.rad_dub = QRadioButton("Main Dub Dialogue Master", grp_matrix)
            self.rad_dub.setChecked(True)
            self.rad_dub.toggled.connect(
                lambda chk: chk and self._set_source(MonitorSource.MAIN_DUB)
            )
            matrix_lay.addWidget(self.rad_dub)

            self.rad_guide = QRadioButton(
                "Reference Guide Track (Original Actor Film Dialogue)", grp_matrix
            )
            self.rad_guide.toggled.connect(
                lambda chk: chk and self._set_source(MonitorSource.REF_GUIDE)
            )
            matrix_lay.addWidget(self.rad_guide)

            self.rad_diff = QRadioButton(
                "Delta Difference (Dub vs Guide Phase Mismatch)", grp_matrix
            )
            self.rad_diff.toggled.connect(
                lambda chk: chk and self._set_source(MonitorSource.DIFF_DELTA)
            )
            matrix_lay.addWidget(self.rad_diff)

            matrix_lay.addSpacing(10)

            # Switches Row: Dim, Mono, Talkback
            switch_row = QHBoxLayout()
            self.btn_dim = QPushButton("DIM (-20 dB)", grp_matrix)
            self.btn_dim.setCheckable(True)
            self.btn_dim.clicked.connect(self._on_dim_clicked)
            switch_row.addWidget(self.btn_dim)

            self.btn_mono = QPushButton("MONO Check", grp_matrix)
            self.btn_mono.setCheckable(True)
            self.btn_mono.clicked.connect(self._on_mono_clicked)
            switch_row.addWidget(self.btn_mono)

            self.btn_talkback = QPushButton("🎤 Talkback", grp_matrix)
            self.btn_talkback.setCheckable(True)
            self.btn_talkback.clicked.connect(self._on_talkback_clicked)
            switch_row.addWidget(self.btn_talkback)

            matrix_lay.addLayout(switch_row)
            mid_split.addWidget(grp_matrix, 1)

            # Right Pane: Broadcast Loudness Radar
            grp_loud = QGroupBox("EBU R128 Broadcast Loudness Meter", self)
            loud_lay = QGridLayout(grp_loud)

            loud_lay.addWidget(QLabel("Integrated Loudness:", grp_loud), 0, 0)
            self.lbl_lufs = QLabel("-23.0 LUFS", grp_loud)
            self.lbl_lufs.setStyleSheet("font-size: 14px; font-weight: 800; color: #10B981;")
            loud_lay.addWidget(self.lbl_lufs, 0, 1)

            loud_lay.addWidget(QLabel("True Peak Ceiling:", grp_loud), 1, 0)
            self.lbl_peak = QLabel("-1.2 dBTP", grp_loud)
            self.lbl_peak.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8;")
            loud_lay.addWidget(self.lbl_peak, 1, 1)

            loud_lay.addWidget(QLabel("Compliance Status:", grp_loud), 2, 0)
            self.lbl_status = QLabel("Broadcast Compliant", grp_loud)
            self.lbl_status.setStyleSheet("font-weight: 800; color: #10B981;")
            loud_lay.addWidget(self.lbl_status, 2, 1)

            # Volume trim slider
            loud_lay.addWidget(QLabel("Control Room Monitor Level:", grp_loud), 3, 0)
            self.slider_vol = QSlider(Qt.Orientation.Horizontal, grp_loud)
            self.slider_vol.setRange(-24, 6)
            self.slider_vol.setValue(0)
            self.slider_vol.valueChanged.connect(self._on_vol_changed)
            loud_lay.addWidget(self.slider_vol, 3, 1)

            self.lbl_vol_val = QLabel("0.0 dB", grp_loud)
            loud_lay.addWidget(self.lbl_vol_val, 3, 2)

            mid_split.addWidget(grp_loud, 1)
            root.addLayout(mid_split, 1)

            # Action bar
            bot = QHBoxLayout()
            self.audition_btn = QPushButton("🔊 Listen via Control Room", self)
            self.audition_btn.setStyleSheet(
                "background: #0284C7; color: #FFF; font-weight: 800; padding: 8px 24px;"
            )
            self.audition_btn.clicked.connect(self._audition_monitor)
            bot.addWidget(self.audition_btn)

            bot.addStretch()

            btn_close = QPushButton("Close Control Room", self)
            btn_close.clicked.connect(self.accept)
            bot.addWidget(btn_close)

            root.addLayout(bot)

        def _set_source(self, source: MonitorSource) -> None:
            self.engine.set_source(source)
            self._update_telemetry()

        def _on_dim_clicked(self) -> None:
            is_dim = self.engine.toggle_dim()
            self.btn_dim.setChecked(is_dim)
            if is_dim:
                self.btn_dim.setStyleSheet("background: #EF4444; color: #FFF; font-weight: bold;")
            else:
                self.btn_dim.setStyleSheet("")

        def _on_mono_clicked(self) -> None:
            is_mono = self.engine.toggle_mono()
            self.btn_mono.setChecked(is_mono)
            if is_mono:
                self.btn_mono.setStyleSheet("background: #F59E0B; color: #FFF; font-weight: bold;")
            else:
                self.btn_mono.setStyleSheet("")

        def _on_talkback_clicked(self) -> None:
            self.engine.talkback_active = not self.engine.talkback_active
            self.btn_talkback.setChecked(self.engine.talkback_active)
            if self.engine.talkback_active:
                self.btn_talkback.setStyleSheet(
                    "background: #10B981; color: #FFF; font-weight: bold;"
                )
            else:
                self.btn_talkback.setStyleSheet("")

        def _on_vol_changed(self, val: int) -> None:
            self.engine.monitor_level_db = float(val)
            self.lbl_vol_val.setText(f"{val:+d}.0 dB")

        def _update_telemetry(self) -> None:
            tele = self.engine.measure_loudness(self.dub_clip)
            self.lbl_lufs.setText(f"{tele.integrated_lufs:.1f} LUFS")
            self.lbl_peak.setText(f"{tele.true_peak_dbfs:+.1f} dBTP")
            self.lbl_status.setText(tele.status_text)
            color = "#10B981" if tele.is_compliant else "#F59E0B"
            self.lbl_status.setStyleSheet(f"font-weight: 800; color: {color};")

        def _audition_monitor(self) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.audition_btn.setText("🔊 Listen via Control Room")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.audition_btn.setText("🔊 Listen via Control Room")
                )

            self.audition_btn.setText("⏹ Stop Audition")
            routed = self.engine.route_monitor_audio(self.dub_clip, self.guide_clip)
            self._audition.play_clip(routed)

        def closeEvent(self, event: Any) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().closeEvent(event)

else:

    class CubaseControlRoomDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def exec(self) -> int:
            return 0


__all__ = ["CubaseControlRoomDialog"]
