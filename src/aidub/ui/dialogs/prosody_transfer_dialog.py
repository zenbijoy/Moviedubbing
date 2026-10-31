"""
Prosody Transfer Studio Dialog.

Transfers the natural rhythm, syllable emphasis, and dynamic energy envelope
from the original actor's vocal track onto the synthetic or translated dubbed take.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.application.voice.prosody_matcher import ProsodyMatcher
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class ProsodyTransferDialog(QDialog):
        """Interactive studio for matching dub prosody to original actor delivery."""

        prosody_applied = Signal(object)  # emits AudioClipData

        def __init__(
            self,
            guide_clip: AudioClipData | None = None,
            dub_clip: AudioClipData | None = None,
            cue_id: str = "cue_001",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle(f"Actor Prosody & Rhythm Transfer — {cue_id}")
            self.resize(680, 440)
            self.setStyleSheet(
                "QDialog { background-color: #0B0F19; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QGroupBox { border: 1px solid #1E293B; border-radius: 6px; margin-top: 8px; font-weight: 700; color: #94A3B8; padding-top: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QSlider::groove:horizontal { height: 4px; background: #1E293B; border-radius: 2px; }"
                "QSlider::sub-page:horizontal { background: #8B5CF6; border-radius: 2px; }"
                "QSlider::handle:horizontal { background: #C4B5FD; border: 1px solid #8B5CF6; width: 14px; margin-top: -5px; margin-bottom: -5px; border-radius: 7px; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #8B5CF6; }"
            )

            self.cue_id = cue_id
            self.guide_clip = guide_clip or AudioClipData.synthesize_speech_like(duration=2.5, sample_rate=44100)
            self.dub_clip = dub_clip or AudioClipData.synthesize_tone(frequency=180.0, duration=2.5, sample_rate=44100)
            self.matcher = ProsodyMatcher(sample_rate=self.guide_clip.sample_rate)

            layout = QVBoxLayout(self)
            layout.setSpacing(12)

            # Header
            header = QFrame(self)
            header.setStyleSheet("background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 8px;")
            h_lay = QHBoxLayout(header)
            lbl_title = QLabel("🎭 Original Actor Prosody Transfer Engine")
            lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #A78BFA;")
            lbl_info = QLabel(f"Guide: {self.guide_clip.duration:.2f}s | Dub: {self.dub_clip.duration:.2f}s")
            lbl_info.setStyleSheet("font-size: 11px; color: #94A3B8;")
            h_lay.addWidget(lbl_title)
            h_lay.addStretch()
            h_lay.addWidget(lbl_info)
            layout.addWidget(header)

            # Sliders Group
            param_box = QGroupBox("Transfer Intensity & Rhythm Weighting")
            grid = QGridLayout(param_box)
            grid.setSpacing(10)

            # Energy Dynamics
            grid.addWidget(QLabel("Energy Envelope Dynamics:"), 0, 0)
            self.slider_energy = QSlider(Qt.Orientation.Horizontal)
            self.slider_energy.setRange(0, 100)
            self.slider_energy.setValue(80)
            self.lbl_energy_val = QLabel("80%")
            self.slider_energy.valueChanged.connect(lambda v: self.lbl_energy_val.setText(f"{v}%"))
            grid.addWidget(self.slider_energy, 0, 1)
            grid.addWidget(self.lbl_energy_val, 0, 2)

            # Pitch Alignment Weight
            grid.addWidget(QLabel("Pitch Contour Lock:"), 1, 0)
            self.slider_pitch = QSlider(Qt.Orientation.Horizontal)
            self.slider_pitch.setRange(0, 100)
            self.slider_pitch.setValue(65)
            self.lbl_pitch_val = QLabel("65%")
            self.slider_pitch.valueChanged.connect(lambda v: self.lbl_pitch_val.setText(f"{v}%"))
            grid.addWidget(self.slider_pitch, 1, 1)
            grid.addWidget(self.lbl_pitch_val, 1, 2)

            # Frame Analysis Resolution
            grid.addWidget(QLabel("Analysis Window (ms):"), 2, 0)
            self.spin_window = QDoubleSpinBox()
            self.spin_window.setRange(5.0, 50.0)
            self.spin_window.setValue(20.0)
            self.spin_window.setSingleStep(5.0)
            grid.addWidget(self.spin_window, 2, 1)

            layout.addWidget(param_box)

            # Status / Audition feedback
            self.status_lbl = QLabel("Adjust transfer intensity and click 'Render Prosody Match'.")
            self.status_lbl.setStyleSheet(
                "background: #0F172A; border: 1px solid #1E293B; border-radius: 4px; padding: 6px; color: #A78BFA; font-weight: 600;"
            )
            layout.addWidget(self.status_lbl)

            # Button Row
            btn_row = QHBoxLayout()
            self.btn_render = QPushButton("⚡ Render Prosody Match")
            self.btn_render.setStyleSheet(
                "QPushButton { background: #5B21B6; color: #EDE9FE; font-weight: 700; }"
                "QPushButton:hover { background: #6D28D9; }"
            )
            self.btn_render.clicked.connect(self._render_prosody)
            btn_row.addWidget(self.btn_render)

            btn_row.addStretch()

            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            self.btn_apply = QPushButton("✓ Apply to Timeline")
            self.btn_apply.setEnabled(False)
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_apply.clicked.connect(self._apply_to_timeline)
            btn_row.addWidget(self.btn_apply)

            layout.addLayout(btn_row)

            self._transferred_clip: AudioClipData | None = None

        def _render_prosody(self) -> None:
            energy_val = self.slider_energy.value() / 100.0
            pitch_val = self.slider_pitch.value() / 100.0
            window_ms = self.spin_window.value()

            matched_samples = self.matcher.transfer_prosody(
                guide_samples=self.guide_clip.samples,
                dub_samples=self.dub_clip.samples,
                sample_rate=self.dub_clip.sample_rate,
                energy_strength=energy_val,
                pitch_weight=pitch_val,
                frame_len_ms=window_ms,
            )

            self._transferred_clip = AudioClipData(
                samples=matched_samples,
                sample_rate=self.dub_clip.sample_rate,
                label=f"{self.cue_id}_prosody_matched",
            )
            self.status_lbl.setText(
                f"✓ Prosody transferred: Dynamic Energy {int(energy_val*100)}%, Pitch Lock {int(pitch_val*100)}% ({window_ms:.0f}ms frame)."
            )
            self.btn_apply.setEnabled(True)

        def _apply_to_timeline(self) -> None:
            if self._transferred_clip is not None:
                self.prosody_applied.emit(self._transferred_clip)
                self.accept()
else:
    class ProsodyTransferDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["ProsodyTransferDialog"]
