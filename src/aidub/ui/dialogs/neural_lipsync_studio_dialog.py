"""
Neural AI Lip-Sync Studio Dialog.

Integrates:
  - NeuralLipSyncEngine (Wav2Lip / MuseTalk / LatentSync models).
  - Side-by-side comparison of original video frame vs. neural dubbed mouth flap.
  - Multi-tier resolution (96p, 256p, 512p), feathering, and temporal smoothing sliders.
  - Live frame rendering progress bar, FPS counter, and dynamic ETA telemetry.
  - Direct timeline integration to commit dubbed video onto Track V1.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from aidub.application.lipsync.neural_lipsync_engine import NeuralLipSyncEngine
from aidub.domain.neural_lipsync import (
    FaceBBox,
    LipSyncConfig,
    LipSyncRenderProgress,
    LipSyncResult,
    NeuralModelType,
)
from aidub.media.pro_audio_editor import AudioClipData

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class _FramePreviewBox(QFrame):
        """Displays an RGB image frame or title placeholder."""

        def __init__(self, title: str, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.title = title
            self.setMinimumSize(240, 180)
            self.setStyleSheet(
                "QFrame { background-color: #070A11; border: 1px solid #1E293B; border-radius: 6px; }"
            )
            self.pixmap: QPixmap | None = None

        def set_image_array(self, rgb_array: np.ndarray) -> None:
            h, w, ch = rgb_array.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.pixmap = QPixmap.fromImage(q_img)
            self.update()

        def paintEvent(self, _event: Any) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()

            if self.pixmap and not self.pixmap.isNull():
                scaled = self.pixmap.scaled(
                    w - 8,
                    h - 28,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (w - scaled.width()) // 2
                y = 24 + (h - 28 - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            else:
                painter.setPen(QColor("#475569"))
                painter.drawText(
                    0,
                    24,
                    w,
                    h - 24,
                    Qt.AlignmentFlag.AlignCenter,
                    "No Frame Loaded",
                )

            # Draw Title Bar
            painter.setPen(QColor("#0284C7"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(8, 18, self.title)


    class NeuralLipSyncStudioDialog(QDialog):
        """Studio dialog for Neural AI Lip-Sync Video Synthesis."""

        lipsync_applied = Signal(object)  # emits LipSyncResult

        def __init__(
            self,
            audio_clip: AudioClipData | None = None,
            video_frames: list[np.ndarray] | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("🧠 Neural AI Lip-Sync & Face Synthesis Studio (Wav2Lip / MuseTalk)")
            self.resize(840, 640)
            self.setStyleSheet(
                "QDialog { background-color: #0B0F19; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QGroupBox { border: 1px solid #1E293B; border-radius: 6px; margin-top: 8px; font-weight: 700; color: #94A3B8; padding-top: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QComboBox, QSpinBox, QDoubleSpinBox { background: #161E2E; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
                "QProgressBar { background: #111827; border: 1px solid #1E293B; border-radius: 4px; text-align: center; color: white; font-weight: bold; }"
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #10B981); }"
            )

            self.audio_clip = audio_clip or AudioClipData.synthesize_speech_like(duration=2.0, sample_rate=16000)
            self.frames = video_frames or self._generate_synthetic_test_video(num_frames=25)
            self.config = LipSyncConfig(fps=25.0)
            self.engine = NeuralLipSyncEngine(config=self.config)
            self.result: LipSyncResult | None = None

            self._init_ui()
            self._update_preview_frames()

        def _generate_synthetic_test_video(self, num_frames: int = 25) -> list[np.ndarray]:
            """Generates test video sequence of an actor's face."""
            frames: list[np.ndarray] = []
            h, w = 180, 240
            for i in range(num_frames):
                frame = np.full((h, w, 3), 25, dtype=np.uint8)
                # Draw head
                y, x = np.ogrid[:h, :w]
                head_mask = ((x - 120) / 50) ** 2 + ((y - 90) / 65) ** 2 <= 1.0
                frame[head_mask] = [215, 175, 145]  # Skin tone
                # Draw lips
                lip_mask = ((x - 120) / 18) ** 2 + ((y - 120) / 7) ** 2 <= 1.0
                frame[lip_mask] = [170, 75, 75]
                frames.append(frame)
            return frames

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title = QLabel("🧠 Neural AI Lip-Sync & Face Synthesis Studio")
            title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38BDF8;")
            header.addWidget(title)
            header.addStretch()

            self.lbl_badge = QLabel("Engine: Wav2Lip-ONNX Ready")
            self.lbl_badge.setStyleSheet(
                "background: #065F46; color: #34D399; font-weight: bold; padding: 4px 10px; border-radius: 4px;"
            )
            header.addWidget(self.lbl_badge)
            layout.addLayout(header)

            # Split Preview Windows (Original vs. Neural Lip-Synced)
            preview_row = QHBoxLayout()
            self.preview_orig = _FramePreviewBox("Original Video Face (Actor Reference)", self)
            self.preview_synced = _FramePreviewBox("Neural Dubbed Face (AI Synthesized)", self)
            preview_row.addWidget(self.preview_orig, stretch=1)
            preview_row.addWidget(self.preview_synced, stretch=1)
            layout.addLayout(preview_row)

            # Model Configuration & Hyperparameters Box
            cfg_box = QGroupBox("Model Architecture & Synthesis Hyperparameters")
            cfg_grid = QGridLayout(cfg_box)

            cfg_grid.addWidget(QLabel("Neural Model Pipeline:"), 0, 0)
            self.combo_model = QComboBox()
            self.combo_model.addItem("⚡ Wav2Lip-ONNX (Fast 96p - Production Standard)", NeuralModelType.WAV2LIP)
            self.combo_model.addItem("🎨 MuseTalk-HD (256p - Latent Feature Diffusion)", NeuralModelType.MUSETALK)
            self.combo_model.addItem("🎬 LatentSync Broadcast (512p - Cinema Master)", NeuralModelType.LATENTSYNC)
            self.combo_model.currentIndexChanged.connect(self._on_model_changed)
            cfg_grid.addWidget(self.combo_model, 0, 1)

            cfg_grid.addWidget(QLabel("Aperture Boost:"), 0, 2)
            self.spin_aperture = QDoubleSpinBox()
            self.spin_aperture.setRange(0.4, 2.0)
            self.spin_aperture.setSingleStep(0.05)
            self.spin_aperture.setValue(1.0)
            cfg_grid.addWidget(self.spin_aperture, 0, 3)

            cfg_grid.addWidget(QLabel("Mask Feather Radius:"), 1, 0)
            self.slider_feather = QSlider(Qt.Orientation.Horizontal)
            self.slider_feather.setRange(4, 32)
            self.slider_feather.setValue(12)
            self.lbl_feather_val = QLabel("12 px")
            self.slider_feather.valueChanged.connect(lambda v: self.lbl_feather_val.setText(f"{v} px"))
            f_row = QHBoxLayout()
            f_row.addWidget(self.slider_feather)
            f_row.addWidget(self.lbl_feather_val)
            cfg_grid.addLayout(f_row, 1, 1)

            cfg_grid.addWidget(QLabel("Temporal Smoothing:"), 1, 2)
            self.slider_smooth = QSlider(Qt.Orientation.Horizontal)
            self.slider_smooth.setRange(5, 95)
            self.slider_smooth.setValue(35)
            self.lbl_smooth_val = QLabel("35%")
            self.slider_smooth.valueChanged.connect(lambda v: self.lbl_smooth_val.setText(f"{v}%"))
            s_row = QHBoxLayout()
            s_row.addWidget(self.slider_smooth)
            s_row.addWidget(self.lbl_smooth_val)
            cfg_grid.addLayout(s_row, 1, 3)

            layout.addWidget(cfg_box)

            # Progress & Telemetry Section
            prog_box = QGroupBox("Neural Synthesis Render Progress")
            p_lay = QVBoxLayout(prog_box)

            telemetry_row = QHBoxLayout()
            self.lbl_status = QLabel("Ready for lip-sync synthesis.")
            self.lbl_status.setStyleSheet("font-weight: bold; color: #E2E8F0;")
            self.lbl_fps_eta = QLabel("Speed: -- fps | ETA: --")
            self.lbl_fps_eta.setStyleSheet("font-weight: bold; color: #F59E0B;")
            telemetry_row.addWidget(self.lbl_status)
            telemetry_row.addStretch()
            telemetry_row.addWidget(self.lbl_fps_eta)
            p_lay.addLayout(telemetry_row)

            self.prog_bar = QProgressBar()
            self.prog_bar.setRange(0, 100)
            self.prog_bar.setValue(0)
            p_lay.addWidget(self.prog_bar)
            layout.addWidget(prog_box)

            # Bottom Actions Bar
            btn_row = QHBoxLayout()
            self.btn_render = QPushButton("▶ Start Neural Lip-Sync Render")
            self.btn_render.setStyleSheet(
                "QPushButton { background: #0284C7; color: white; font-weight: bold; padding: 9px 18px; }"
                "QPushButton:hover { background: #0369A1; }"
            )
            self.btn_render.clicked.connect(self._run_render)
            btn_row.addWidget(self.btn_render)

            self.btn_audition = QPushButton("🔊 Audition Audio")
            self.btn_audition.clicked.connect(self._audition_audio)
            btn_row.addWidget(self.btn_audition)

            btn_row.addStretch()

            btn_cancel = QPushButton("Close")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            self.btn_apply = QPushButton("✓ Apply Lip-Sync to Timeline (V1)")
            self.btn_apply.setEnabled(False)
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; padding: 9px 18px; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_apply.clicked.connect(self._apply_to_timeline)
            btn_row.addWidget(self.btn_apply)

            layout.addLayout(btn_row)

        def _update_preview_frames(self) -> None:
            if self.frames:
                self.preview_orig.set_image_array(self.frames[0])
                self.preview_synced.set_image_array(self.frames[0])

        def _on_model_changed(self) -> None:
            model = self.combo_model.currentData()
            self.config.model_type = model
            if model == NeuralModelType.MUSETALK:
                self.config.crop_size = 256
                self.lbl_badge.setText("Engine: MuseTalk-HD (256p)")
            elif model == NeuralModelType.LATENTSYNC:
                self.config.crop_size = 512
                self.lbl_badge.setText("Engine: LatentSync Broadcast (512p)")
            else:
                self.config.crop_size = 96
                self.lbl_badge.setText("Engine: Wav2Lip-ONNX (96p)")

        def _on_progress_telemetry(self, p: LipSyncRenderProgress) -> None:
            pct = int(p.percent_complete)
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(p.status_message)
            self.lbl_fps_eta.setText(f"Speed: {p.fps_rendered:.1f} fps | ETA: {p.eta_seconds:.1f}s")

        def _run_render(self) -> None:
            self.btn_render.setEnabled(False)
            self.config.aperture_scale = self.spin_aperture.value()
            self.config.feather_radius_px = self.slider_feather.value()
            self.config.temporal_smoothing_factor = self.slider_smooth.value() / 100.0

            self.engine = NeuralLipSyncEngine(config=self.config)
            self.result = self.engine.render_sequence(
                frames=self.frames,
                audio_clip=self.audio_clip,
                progress_callback=self._on_progress_telemetry,
            )

            # Update preview with rendered result
            if self.result and self.result.output_path.exists():
                data = np.load(self.result.output_path)
                rendered_frames = data["frames"]
                if len(rendered_frames) > 0:
                    mid_idx = len(rendered_frames) // 2
                    self.preview_orig.set_image_array(self.frames[mid_idx])
                    self.preview_synced.set_image_array(rendered_frames[mid_idx])

            self.lbl_status.setText(
                f"✓ Lip-Sync complete! (LSE-Confidence: {self.result.average_lse_c:.1f}, LSE-Distance: {self.result.average_lse_d:.1f})"
            )
            self.lbl_fps_eta.setText("Render Status: Complete")
            self.btn_apply.setEnabled(True)
            self.btn_render.setEnabled(True)

        def _audition_audio(self) -> None:
            out_wav = Path("output/lipsync_audition.wav")
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            self.audio_clip.save_wav(out_wav)
            self.lbl_status.setText(
                f"🔊 Auditioning dubbed speech ({self.audio_clip.duration_s:.2f}s, Peak: {self.audio_clip.peak_dbfs} dBFS)"
            )

        def _apply_to_timeline(self) -> None:
            if self.result is not None:
                self.lipsync_applied.emit(self.result)
                self.accept()
else:
    class NeuralLipSyncStudioDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["NeuralLipSyncStudioDialog"]
