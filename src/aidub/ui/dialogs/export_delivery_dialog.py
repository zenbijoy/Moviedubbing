"""
Export Delivery Preset Selector Dialog.

Integrates:
  - ExportPresetManager with industry presets (Netflix, YouTube, Theatrical, Broadcast).
  - Target Loudness LUFS compliance verification.
  - Video and Audio codec specs with container selection.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.export.preset_manager import ExportPreset, ExportPresetManager

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class ExportDeliveryDialog(QDialog):
        """Studio dialog for selecting and configuring broadcast delivery presets."""

        export_confirmed = Signal(object)  # emits ExportPreset

        def __init__(
            self,
            preset_manager: ExportPresetManager | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Export Delivery Preset Selector")
            self.resize(650, 480)
            self.setStyleSheet(
                "QDialog { background-color: #0B0F19; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QGroupBox { border: 1px solid #1E293B; border-radius: 6px; margin-top: 8px; font-weight: 700; color: #94A3B8; padding-top: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: #161E2E; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 5px 8px; font-weight: bold; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
            )

            self.manager = preset_manager or ExportPresetManager()
            self.selected_key = "netflix"

            layout = QVBoxLayout(self)
            layout.setSpacing(12)

            # Header
            header = QFrame(self)
            header.setStyleSheet("background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 8px;")
            h_lay = QHBoxLayout(header)
            title = QLabel("📦 Broadcast Delivery Master Specification")
            title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38BDF8;")
            self.lbl_lufs_badge = QLabel("Target: -24.0 LUFS")
            self.lbl_lufs_badge.setStyleSheet(
                "background: #065F46; color: #34D399; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            h_lay.addWidget(title)
            h_lay.addStretch()
            h_lay.addWidget(self.lbl_lufs_badge)
            layout.addWidget(header)

            # Preset Selection
            preset_row = QHBoxLayout()
            preset_row.addWidget(QLabel("Delivery Preset:"))
            self.combo_presets = QComboBox()
            for k in self.manager.list_keys():
                p = self.manager.get(k)
                self.combo_presets.addItem(f"{p.name} ({p.container.upper()}, {p.loudness_target_lufs} LUFS)", k)
            self.combo_presets.currentIndexChanged.connect(self._on_preset_changed)
            preset_row.addWidget(self.combo_presets)
            layout.addLayout(preset_row)

            # Specification Grid
            spec_group = QGroupBox("Master Deliverable Technical Specifications")
            grid = QGridLayout(spec_group)
            grid.setSpacing(10)

            grid.addWidget(QLabel("Container Format:"), 0, 0)
            self.txt_container = QLineEdit("mkv")
            grid.addWidget(self.txt_container, 0, 1)

            grid.addWidget(QLabel("Loudness Target (LUFS):"), 0, 2)
            self.spin_lufs = QDoubleSpinBox()
            self.spin_lufs.setRange(-40.0, 0.0)
            self.spin_lufs.setValue(-24.0)
            grid.addWidget(self.spin_lufs, 0, 3)

            grid.addWidget(QLabel("Video Codec:"), 1, 0)
            self.txt_vcodec = QLineEdit("h264")
            grid.addWidget(self.txt_vcodec, 1, 1)

            grid.addWidget(QLabel("Audio Codec:"), 1, 2)
            self.txt_acodec = QLineEdit("aac")
            grid.addWidget(self.txt_acodec, 1, 3)

            grid.addWidget(QLabel("Audio Bitrate (kbps):"), 2, 0)
            self.spin_bitrate = QSpinBox()
            self.spin_bitrate.setRange(64, 3072)
            self.spin_bitrate.setValue(320)
            grid.addWidget(self.spin_bitrate, 2, 1)

            grid.addWidget(QLabel("Sample Rate (Hz):"), 2, 2)
            self.spin_sr = QSpinBox()
            self.spin_sr.setRange(44100, 96000)
            self.spin_sr.setValue(48000)
            grid.addWidget(self.spin_sr, 2, 3)

            layout.addWidget(spec_group)

            # Loudness Query Box
            query_box = QHBoxLayout()
            query_box.addWidget(QLabel("Find Presets by Target LUFS:"))
            self.spin_search_lufs = QDoubleSpinBox()
            self.spin_search_lufs.setRange(-40.0, 0.0)
            self.spin_search_lufs.setValue(-14.0)
            query_box.addWidget(self.spin_search_lufs)

            btn_search = QPushButton("🔍 Find Matching Standards")
            btn_search.clicked.connect(self._find_by_loudness)
            query_box.addWidget(btn_search)
            query_box.addStretch()
            layout.addLayout(query_box)

            # Status HUD
            self.lbl_status = QLabel("Ready to export master.")
            self.lbl_status.setStyleSheet("background: #0F172A; padding: 8px; border-radius: 4px; color: #38BDF8;")
            layout.addWidget(self.lbl_status)

            # Bottom Actions
            btn_row = QHBoxLayout()
            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)
            btn_row.addStretch()

            self.btn_confirm = QPushButton("📦 Confirm & Queue Delivery Export")
            self.btn_confirm.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; padding: 9px 18px; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_confirm.clicked.connect(self._confirm_export)
            btn_row.addWidget(self.btn_confirm)

            layout.addLayout(btn_row)

            self._update_fields_from_current()

        def _on_preset_changed(self) -> None:
            self.selected_key = self.combo_presets.currentData()
            self._update_fields_from_current()

        def _update_fields_from_current(self) -> None:
            if not self.selected_key:
                return
            p = self.manager.get(self.selected_key)
            self.txt_container.setText(p.container)
            self.spin_lufs.setValue(p.loudness_target_lufs)
            self.txt_vcodec.setText(p.video_codec)
            self.txt_acodec.setText(p.audio_codec)
            self.spin_bitrate.setValue(p.audio_bitrate_kbps)
            self.spin_sr.setValue(p.sample_rate)
            self.lbl_lufs_badge.setText(f"Target: {p.loudness_target_lufs:.1f} LUFS")
            self.lbl_status.setText(f"Loaded specification: {p.name} ({p.container.upper()}).")

        def _find_by_loudness(self) -> None:
            target = self.spin_search_lufs.value()
            matches = self.manager.for_loudness(target)
            if matches:
                names = ", ".join(m.name for m in matches)
                self.lbl_status.setText(f"✓ Found {len(matches)} matching presets for {target:.1f} LUFS: {names}")
            else:
                self.lbl_status.setText(f"ℹ️ No default preset exactly at {target:.1f} LUFS. You can set it manually.")

        def _confirm_export(self) -> None:
            preset = ExportPreset(
                name=self.selected_key.title(),
                container=self.txt_container.text().strip() or "mp4",
                video_codec=self.txt_vcodec.text().strip() or "h264",
                audio_codec=self.txt_acodec.text().strip() or "aac",
                audio_bitrate_kbps=self.spin_bitrate.value(),
                sample_rate=self.spin_sr.value(),
                loudness_target_lufs=self.spin_lufs.value(),
            )
            self.export_confirmed.emit(preset)
            self.accept()
else:
    class ExportDeliveryDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["ExportDeliveryDialog"]
