"""
Hollywood-Grade Emotion Studio UI Screen for AI Movie Dubbing.

Provides:
  - 3D Continuous PAD (Valence-Arousal-Dominance) Psychological Coordinates.
  - 12 Cinematic Hollywood Presets with 0% to 200% hyper-intensity scaling.
  - Articulatory micro-inflection sliders (breathiness, throat tension, tremble, vocal fry).
  - Real-time SSML preview and acoustic synthesis parameter mapping.
  - Headless safe for headless CI/test environments.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.emotion.bangla_presets import BanglaEmotionPresets
from aidub.application.emotion.emotion_curve import EmotionCurve, EmotionCurvePoint
from aidub.application.emotion.emotion_editor import EmotionEditorService
from aidub.application.emotion.emotion_transfer import EmotionTransferService
from aidub.application.emotion.intensity_controller import EmotionIntensityController
from aidub.domain.emotion import EmotionSpec

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, Qt, Signal
    from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


if _QT_AVAILABLE:

    class _EmotionCurveWidget(QWidget):
        """Interactive visual keyframe editor for dynamic emotion intensity curves."""

        curve_changed = Signal(object)  # emits EmotionCurve

        def __init__(self, curve: EmotionCurve | None = None, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(110)
            self.setStyleSheet("background: #0B0F19; border: 1px solid #1E293B; border-radius: 6px;")
            self.curve = curve or EmotionCurve(
                [
                    EmotionCurvePoint(0.0, 0.4),
                    EmotionCurvePoint(0.3, 0.8),
                    EmotionCurvePoint(0.7, 1.4),
                    EmotionCurvePoint(1.0, 1.0),
                ]
            )

        def set_curve(self, curve: EmotionCurve) -> None:
            self.curve = curve
            self.update()

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            w = max(10, self.width())
            h = max(10, self.height())
            x = event.position().x() if hasattr(event, "position") else event.x()
            y = event.position().y() if hasattr(event, "position") else event.y()

            t = max(0.0, min(1.0, x / w))
            # intensity mapped 0..2.0 from bottom to top
            intensity = max(0.0, min(2.0, (h - y) / h * 2.0))

            # Add or replace nearest point
            self.curve.points.append(EmotionCurvePoint(round(t, 2), round(intensity, 2)))
            self.curve.points.sort(key=lambda p: p.t)
            self.curve_changed.emit(self.curve)
            self.update()

        def paintEvent(self, _event: Any) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()

            # Background grid
            painter.setPen(QPen(QColor("#1E293B"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, h // 2, w, h // 2)

            # Draw Emotion Curve
            path = QPainterPath()
            n_eval = 64
            pts = []
            for i in range(n_eval):
                t = i / (n_eval - 1)
                val = self.curve.evaluate(t)  # 0..2.0
                px = t * w
                py = h - (val / 2.0 * h)
                pts.append(QPointF(px, py))

            if pts:
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)

            pen = QPen(QColor("#F59E0B"), 2.5)
            painter.setPen(pen)
            painter.drawPath(path)

            # Draw Keyframe Dots
            painter.setPen(QPen(QColor("#F8FAFC"), 1))
            painter.setBrush(QColor("#EF4444"))
            for pt in self.curve.points:
                kx = pt.t * w
                ky = h - (pt.intensity / 2.0 * h)
                painter.drawEllipse(QPointF(kx, ky), 4.5, 4.5)

            # Draw Label
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(8, 16, "EMOTION INTENSITY KEYFRAME TIMELINE (0.0x – 2.0x)")

    class EmotionEditorScreen(QWidget):
        """Interactive Hollywood Emotion Director & Prosody Suite."""

        emotion_changed = Signal(object)  # Emits updated EmotionSpec

        def __init__(
            self,
            initial_text: str = "আমি তোমাকে কখনোই ক্ষমা করব না!",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.dialogue_text: str = initial_text
            self.editor_service: EmotionEditorService = EmotionEditorService()
            self.current_spec: EmotionSpec = self.editor_service.apply_preset("Neutral", 1.0)
            self.emotion_curve = EmotionCurve()

            self.setWindowTitle("Pro Emotion Director Studio")
            self.resize(950, 720)
            self._init_ui()
            self._update_all_displays()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title = QLabel("🎭 Pro Emotion Director & 3D PAD Prosody Suite")
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
            header.addWidget(title)
            header.addStretch()

            preset_lbl = QLabel("Preset:")
            preset_lbl.setStyleSheet("color: #94A3B8; font-weight: bold;")
            header.addWidget(preset_lbl)

            self.combo_presets = QComboBox()
            self.combo_presets.addItems(self.editor_service.list_preset_names())
            for bp in BanglaEmotionPresets.list():
                self.combo_presets.addItem(f"🇧🇩 {bp.capitalize()} (Bangla)", f"bn_{bp}")

            self.combo_presets.setStyleSheet(
                "background: #1E293B; color: #38BDF8; font-weight: bold; padding: 4px 10px; border-radius: 4px;"
            )
            self.combo_presets.currentTextChanged.connect(self._on_preset_changed)
            header.addWidget(self.combo_presets)

            layout.addLayout(header)

            # Intensity Slider
            intensity_box = QHBoxLayout()
            intensity_lbl = QLabel("Dramatic Intensity:")
            intensity_lbl.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            intensity_box.addWidget(intensity_lbl)

            self.slider_intensity = QSlider(Qt.Orientation.Horizontal)
            self.slider_intensity.setRange(0, 200)
            self.slider_intensity.setValue(100)
            self.slider_intensity.valueChanged.connect(self._on_intensity_changed)
            intensity_box.addWidget(self.slider_intensity)

            self.lbl_intensity_val = QLabel("100%")
            self.lbl_intensity_val.setStyleSheet("color: #F59E0B; font-weight: bold; width: 45px;")
            intensity_box.addWidget(self.lbl_intensity_val)
            layout.addLayout(intensity_box)

            # Main Controls Grid (3D PAD on Left, Micro-inflections on Right)
            split_box = QHBoxLayout()

            # 3D PAD Coordinates Group
            pad_group = QGroupBox("3D Psychological Emotion Coordinates (PAD)")
            pad_group.setStyleSheet("QGroupBox{color: #38BDF8; font-weight: bold;}")
            pad_layout = QVBoxLayout(pad_group)

            self.slider_valence = self._create_named_slider(
                "Valence (Agony vs Ecstasy):", -100, 100, 0, pad_layout, self._on_coord_changed
            )
            self.slider_arousal = self._create_named_slider(
                "Arousal (Dormant vs Explosive):", 0, 100, 35, pad_layout, self._on_coord_changed
            )
            self.slider_dominance = self._create_named_slider(
                "Dominance (Submissive vs Commanding):", -100, 100, 0, pad_layout, self._on_coord_changed
            )
            split_box.addWidget(pad_group)

            # Micro-Inflections Group
            inflect_group = QGroupBox("Vocal Articulation & Micro-Inflections")
            inflect_group.setStyleSheet("QGroupBox{color: #A855F7; font-weight: bold;}")
            inflect_layout = QVBoxLayout(inflect_group)

            self.slider_breath = self._create_named_slider(
                "Breathiness / Aspiration:", 0, 100, 10, inflect_layout, self._on_inflect_changed
            )
            self.slider_tension = self._create_named_slider(
                "Throat & Glottal Tension:", 0, 100, 0, inflect_layout, self._on_inflect_changed
            )
            self.slider_tremble = self._create_named_slider(
                "Vocal Cord Tremble (Grief/Fear):", 0, 100, 0, inflect_layout, self._on_inflect_changed
            )
            self.slider_fry = self._create_named_slider(
                "Vocal Fry Rumble:", 0, 100, 0, inflect_layout, self._on_inflect_changed
            )
            split_box.addWidget(inflect_group)

            layout.addLayout(split_box)

            # Interactive Emotion Keyframe Timeline Curve
            self.curve_widget = _EmotionCurveWidget(self.emotion_curve)
            self.curve_widget.curve_changed.connect(self._on_curve_changed)
            layout.addWidget(self.curve_widget)

            # SSML Preview Box
            ssml_group = QGroupBox("Generated Synthesis SSML & Acoustic Metadata")
            ssml_group.setStyleSheet("QGroupBox{color: #10B981; font-weight: bold;}")
            ssml_layout = QVBoxLayout(ssml_group)

            self.txt_ssml = QTextEdit()
            self.txt_ssml.setReadOnly(True)
            self.txt_ssml.setMaximumHeight(140)
            self.txt_ssml.setStyleSheet("background: #0F172A; color: #34D399; font-family: Consolas; font-size: 11px;")
            ssml_layout.addWidget(self.txt_ssml)

            layout.addWidget(ssml_group)

            # Bottom Action Bar
            bottom_bar = QHBoxLayout()
            self.lbl_acoustic_summary = QLabel("")
            self.lbl_acoustic_summary.setStyleSheet("color: #94A3B8; font-size: 11px;")
            bottom_bar.addWidget(self.lbl_acoustic_summary)
            bottom_bar.addStretch()

            self.btn_audition = QPushButton("🔊 Audition Live Speech with Emotion")
            self.btn_audition.setStyleSheet(
                "background: #1E293B; color: #38BDF8; border: 1px solid #0284C7; font-weight: bold; padding: 8px 14px; border-radius: 4px;"
            )
            self.btn_audition.clicked.connect(self._on_audition_clicked)
            bottom_bar.addWidget(self.btn_audition)

            self.btn_apply = QPushButton("✨ Apply Directorial Emotion to Cue")
            self.btn_apply.setStyleSheet(
                "background: #2563EB; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;"
            )
            self.btn_apply.clicked.connect(self._on_apply_clicked)
            bottom_bar.addWidget(self.btn_apply)

            layout.addLayout(bottom_bar)

        def _create_named_slider(
            self, label_text: str, min_val: int, max_val: int, default_val: int, layout: QVBoxLayout, callback: Any
        ) -> QSlider:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #CBD5E1; font-size: 11px;")
            row.addWidget(lbl)
            val_lbl = QLabel(str(default_val))
            val_lbl.setStyleSheet("color: #38BDF8; font-weight: bold; width: 35px;")
            row.addWidget(val_lbl)
            layout.addLayout(row)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default_val)
            slider.valueChanged.connect(lambda v: (val_lbl.setText(str(v)), callback()))
            layout.addWidget(slider)
            return slider

        def _on_preset_changed(self, preset_name: str) -> None:
            intensity = self.slider_intensity.value() / 100.0
            data = self.combo_presets.currentData()
            if data and str(data).startswith("bn_"):
                bn_key = str(data)[3:]
                pad, micro = BanglaEmotionPresets.get(bn_key)
                scaled_pad = EmotionIntensityController.scale_pad(pad, intensity)
                scaled_micro = EmotionIntensityController.scale_micro(micro, intensity)
                self.current_spec = EmotionSpec(
                    primary_emotion=bn_key,
                    intensity=intensity,
                    valence=scaled_pad.valence,
                    arousal=scaled_pad.arousal,
                    dominance=scaled_pad.dominance,
                    breathiness=scaled_micro.breathiness_pct / 100.0,
                    throat_tension=scaled_micro.throat_tension_pct / 100.0,
                    tremble=scaled_micro.tremble_pct / 100.0,
                    vocal_fry=scaled_micro.vocal_fry_pct / 100.0,
                )
            else:
                self.current_spec = self.editor_service.apply_preset(preset_name, intensity)
            self._update_all_displays()

        def _on_intensity_changed(self, value: int) -> None:
            self.lbl_intensity_val.setText(f"{value}%")
            self.current_spec.intensity = value / 100.0
            self._refresh_ssml()

        def _on_coord_changed(self) -> None:
            self.current_spec.valence = self.slider_valence.value() / 100.0
            self.current_spec.arousal = self.slider_arousal.value() / 100.0
            self.current_spec.dominance = self.slider_dominance.value() / 100.0
            self._refresh_ssml()

        def _on_inflect_changed(self) -> None:
            self.current_spec.breathiness = self.slider_breath.value() / 100.0
            self.current_spec.throat_tension = self.slider_tension.value() / 100.0
            self.current_spec.tremble = self.slider_tremble.value() / 100.0
            self.current_spec.vocal_fry = self.slider_fry.value() / 100.0
            self._refresh_ssml()

        def _on_curve_changed(self, curve: EmotionCurve) -> None:
            self.emotion_curve = curve
            mid_val = curve.evaluate(0.5)
            self.current_spec.intensity = round(mid_val, 2)
            self.slider_intensity.blockSignals(True)
            self.slider_intensity.setValue(int(mid_val * 100))
            self.slider_intensity.blockSignals(False)
            self.lbl_intensity_val.setText(f"{int(mid_val * 100)}%")
            self._refresh_ssml()

        def _update_all_displays(self) -> None:
            self.slider_valence.setValue(int(self.current_spec.valence * 100))
            self.slider_arousal.setValue(int(self.current_spec.arousal * 100))
            self.slider_dominance.setValue(int(self.current_spec.dominance * 100))
            self.slider_breath.setValue(int(self.current_spec.breathiness * 100))
            self.slider_tension.setValue(int(self.current_spec.throat_tension * 100))
            self.slider_tremble.setValue(int(self.current_spec.tremble * 100))
            self.slider_fry.setValue(int(self.current_spec.vocal_fry * 100))
            self._refresh_ssml()

        def _refresh_ssml(self) -> None:
            ssml = self.editor_service.generate_ssml(self.dialogue_text, self.current_spec)
            self.txt_ssml.setPlainText(ssml)

            params = self.editor_service.calculate_acoustic_parameters(self.current_spec)
            summary = (
                f"Pitch Scale: {params['pitch_scale']:.2f}x | "
                f"Rate Scale: {params['rate_scale']:.2f}x | "
                f"Volume: {params['volume_db']:+.1f}dB | "
                f"Formant Shift: {params['formant_cents']:+.0f} cents"
            )
            self.lbl_acoustic_summary.setText(summary)

        def _on_audition_clicked(self) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.btn_audition.setText("🔊 Audition Live Speech with Emotion")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.btn_audition.setText("🔊 Audition Live Speech with Emotion")
                )

            self.btn_audition.setText("⏹ Stop Audition")
            params = self.editor_service.calculate_acoustic_parameters(self.current_spec)
            pitch_scale = params.get("pitch_scale", 1.0)
            rate_scale = params.get("rate_scale", 1.0)
            pitch_hz = f"{int((pitch_scale - 1.0) * 100):+}Hz"
            rate_pct = f"{int((rate_scale - 1.0) * 100):+}%"

            self._audition.synthesize_and_play(
                text=self.dialogue_text or "আমি তোমাকে কখনোই ক্ষমা করব না!",
                voice_id="bn-BD-NabanitaNeural",
                pitch=pitch_hz,
                rate=rate_pct,
            )

        def closeEvent(self, event: Any) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().closeEvent(event)

        def _on_apply_clicked(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.emotion_changed.emit(self.current_spec)

else:
    class EmotionEditorScreen:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.editor_service = EmotionEditorService()


__all__ = [
    "EmotionEditorScreen",
]
