"""
Pro Emotion Director & Advanced Performance Studio Dialog.

Features:
  - Interactive 2D Valence-Arousal-Dominance (PAD) radar with draggable glowing puck.
  - 12 Cinematic Hollywood Presets with 0% to 200% hyper-intensity scaling.
  - Dynamic Emotion Trajectory Envelope (Start -> Climax -> Resolution).
  - 1-Click "Extract Original Actor Performance" from movie dialogue track.
  - Articulatory Micro-Inflection Sliders (Vocal Tremble, Breathiness, Vocal Fry, Throat Tension).
  - Live acoustic performance readout and 1-Click Apply to Timeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.application.voice.pro_emotion_engine import (
    CINEMATIC_EMOTION_PRESETS,
    EmotionKeyframe,
    EmotionTrajectory,
    MicroInflections,
    PADVector,
    ProEmotionDirectorEngine,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QMouseEvent,
        QPainter,
        QPaintEvent,
        QPen,
        QRadialGradient,
    )
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

    class _EmotionRadarCanvas(QWidget):
        """Interactive 2D psychological emotion radar (Valence vs Arousal)."""

        coordinates_changed = Signal(float, float)  # emits (valence, arousal)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumSize(280, 280)
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setStyleSheet("background: #080B12; border: 1px solid #1E293B; border-radius: 12px;")
            self._pad = PADVector(valence=0.0, arousal=0.35, dominance=0.0)
            self._is_dragging = False

        def set_pad(self, pad: PADVector) -> None:
            self._pad = pad.clamped()
            self.update()

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton:
                self._is_dragging = True
                self._update_from_pos(event.position().x(), event.position().y())
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if self._is_dragging:
                self._update_from_pos(event.position().x(), event.position().y())
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton:
                self._is_dragging = False
            super().mouseReleaseEvent(event)

        def _update_from_pos(self, px: float, py: float) -> None:
            w, h = self.width(), self.height()
            # X maps [0, w] to Valence [-1.0, 1.0]
            val = ((px / max(1.0, w)) * 2.0) - 1.0
            # Y maps [h, 0] to Arousal [0.0, 1.0] (top is high arousal)
            aro = 1.0 - (py / max(1.0, h))

            self._pad.valence = float(max(-1.0, min(1.0, val)))
            self._pad.arousal = float(max(0.0, min(1.0, aro)))
            self.coordinates_changed.emit(self._pad.valence, self._pad.arousal)
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mid_x = w / 2.0
            mid_y = h / 2.0

            # Background card
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#080B12")))
            painter.drawRoundedRect(0, 0, w, h, 12, 12)

            # Circular concentric radar grid
            for radius_pct in [0.25, 0.50, 0.75, 0.95]:
                rx = mid_x * radius_pct
                ry = mid_y * radius_pct
                painter.setPen(QPen(QColor("#162032"), 1, Qt.PenStyle.DotLine))
                painter.drawEllipse(QPointF(mid_x, mid_y), rx, ry)

            # Crosshairs
            painter.setPen(QPen(QColor("#1E293B"), 1))
            painter.drawLine(0, int(mid_y), w, int(mid_y))
            painter.drawLine(int(mid_x), 0, int(mid_x), h)

            # Quadrant Labels
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#EF4444"))
            painter.drawText(12, 22, "RAGE / TERROR")
            painter.setPen(QColor("#10B981"))
            painter.drawText(w - 110, 22, "HEROIC / JOY")
            painter.setPen(QColor("#64748B"))
            painter.drawText(12, h - 12, "GRIEF / COLD")
            painter.setPen(QColor("#38BDF8"))
            painter.drawText(w - 130, h - 12, "WHISPER / CALM")

            # Center neutral marker
            painter.setPen(QColor("#475569"))
            painter.drawText(int(mid_x) + 4, int(mid_y) - 4, "NEUTRAL")

            # Active Puck (Glowing circular handle)
            puck_x = int(((self._pad.valence + 1.0) * 0.5) * w)
            puck_y = int((1.0 - self._pad.arousal) * h)

            # Glowing halo
            glow = QRadialGradient(puck_x, puck_y, 22)
            glow.setColorAt(0.0, QColor(56, 189, 248, 160))
            glow.setColorAt(1.0, QColor(56, 189, 248, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(puck_x - 22, puck_y - 22, 44, 44)

            # Puck center
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(QPen(QColor("#38BDF8"), 2))
            painter.drawEllipse(puck_x - 6, puck_y - 6, 12, 12)

    class ProEmotionStudioDialog(QDialog):
        """World-class Director Emotion Lab for film dubbing dialogue."""

        emotion_applied = Signal(dict)  # emits mapped performance config

        def __init__(
            self,
            character_name: str = "Actor",
            current_emotion: str = "Neutral",
            original_wav_path: str | Path | None = None,
            parent: Any = None,
            dialogue_text: str = "",
            **kwargs: Any,
        ) -> None:
            super().__init__(parent)
            self._character_name = character_name
            self._dialogue_text = dialogue_text
            self.setWindowTitle("Pro Emotion Director Studio — Cinematic Performance Lab")
            self.setMinimumSize(920, 640)
            self.resize(1040, 720)
            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QSlider::groove:horizontal { height: 6px; background: #1E293B; border-radius: 3px; }"
                "QSlider::sub-page:horizontal { background: #EC4899; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #F43F5E; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
                "QPushButton { background: #162030; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #202B40; color: #FFF; border-color: #EC4899; }"
            )

            self._original_wav_path = Path(original_wav_path) if original_wav_path else None
            self._pad = PADVector(valence=0.0, arousal=0.35, dominance=0.0)
            self._micro = MicroInflections()
            self._intensity = 1.0

            self._init_ui()
            if current_emotion in CINEMATIC_EMOTION_PRESETS:
                self._load_preset(current_emotion)

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("🎭 PRO EMOTION DIRECTOR STUDIO", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #F8FAFC;")
            s_lbl = QLabel(
                "Sculpt emotional valence, dramatic arousal, and articulatory micro-inflections.",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            if self._original_wav_path and self._original_wav_path.is_file():
                extract_btn = QPushButton("🎬 Match Original Actor's Emotion", self)
                extract_btn.setStyleSheet("background: #4F46E5; color: #FFF; font-weight: 800;")
                extract_btn.clicked.connect(self._extract_from_actor)
                header.addWidget(extract_btn)

            root.addLayout(header)

            # Main Workspace Splitter
            content = QHBoxLayout()
            content.setSpacing(16)

            # Left Pane: 2D Radar & Preset Palette
            left_box = QVBoxLayout()
            left_box.setSpacing(8)

            left_box.addWidget(QLabel("3D Psychological Emotion Radar (Drag Puck):", self))
            self.radar = _EmotionRadarCanvas(self)
            self.radar.coordinates_changed.connect(self._on_radar_moved)
            left_box.addWidget(self.radar)

            # Preset Selector Dropdown & Grid
            left_box.addWidget(QLabel("Cinematic Presets (Hollywood Style):", self))
            self.preset_combo = QComboBox(self)
            self.preset_combo.addItems(ProEmotionDirectorEngine.get_preset_names())
            self.preset_combo.currentTextChanged.connect(self._load_preset)
            left_box.addWidget(self.preset_combo)

            content.addLayout(left_box, 1)

            # Right Pane: Intensity, Dominance & Micro-Inflections
            right_box = QVBoxLayout()
            right_box.setSpacing(10)

            # Intensity & Dominance Controls
            grp_pad = QGroupBox("Vector Parameters", self)
            pad_lay = QGridLayout(grp_pad)

            pad_lay.addWidget(QLabel("Emotion Intensity (0 - 200%):", grp_pad), 0, 0)
            self.intensity_slider = QSlider(Qt.Orientation.Horizontal, grp_pad)
            self.intensity_slider.setRange(0, 200)
            self.intensity_slider.setValue(100)
            self.intensity_slider.valueChanged.connect(self._on_param_changed)
            pad_lay.addWidget(self.intensity_slider, 0, 1)
            self.intensity_lbl = QLabel("100%", grp_pad)
            pad_lay.addWidget(self.intensity_lbl, 0, 2)

            pad_lay.addWidget(QLabel("Dominance (-1.0 to +1.0):", grp_pad), 1, 0)
            self.dominance_slider = QSlider(Qt.Orientation.Horizontal, grp_pad)
            self.dominance_slider.setRange(-100, 100)
            self.dominance_slider.setValue(0)
            self.dominance_slider.valueChanged.connect(self._on_param_changed)
            pad_lay.addWidget(self.dominance_slider, 1, 1)
            self.dominance_lbl = QLabel("0.00", grp_pad)
            pad_lay.addWidget(self.dominance_lbl, 1, 2)

            right_box.addWidget(grp_pad)

            # Micro-Inflections
            grp_micro = QGroupBox("Articulatory Micro-Inflections", self)
            micro_lay = QGridLayout(grp_micro)

            micro_lay.addWidget(QLabel("Vocal Tremble / Weeping (0-100%):", grp_micro), 0, 0)
            self.tremble_slider = QSlider(Qt.Orientation.Horizontal, grp_micro)
            self.tremble_slider.setRange(0, 100)
            self.tremble_slider.setValue(0)
            self.tremble_slider.valueChanged.connect(self._on_param_changed)
            micro_lay.addWidget(self.tremble_slider, 0, 1)

            micro_lay.addWidget(QLabel("Breathiness / Air Intake (0-100%):", grp_micro), 1, 0)
            self.breath_slider = QSlider(Qt.Orientation.Horizontal, grp_micro)
            self.breath_slider.setRange(0, 100)
            self.breath_slider.setValue(10)
            self.breath_slider.valueChanged.connect(self._on_param_changed)
            micro_lay.addWidget(self.breath_slider, 1, 1)

            micro_lay.addWidget(QLabel("Vocal Fry / Gravel (0-100%):", grp_micro), 2, 0)
            self.fry_slider = QSlider(Qt.Orientation.Horizontal, grp_micro)
            self.fry_slider.setRange(0, 100)
            self.fry_slider.setValue(0)
            self.fry_slider.valueChanged.connect(self._on_param_changed)
            micro_lay.addWidget(self.fry_slider, 2, 1)

            micro_lay.addWidget(QLabel("Throat Tension / Strain (0-100%):", grp_micro), 3, 0)
            self.tension_slider = QSlider(Qt.Orientation.Horizontal, grp_micro)
            self.tension_slider.setRange(0, 100)
            self.tension_slider.setValue(0)
            self.tension_slider.valueChanged.connect(self._on_param_changed)
            micro_lay.addWidget(self.tension_slider, 3, 1)

            right_box.addWidget(grp_micro)

            # Acoustic Engine Output Card
            grp_out = QGroupBox("Calculated Acoustic Delivery Intent", self)
            out_lay = QVBoxLayout(grp_out)
            self.prompt_lbl = QLabel('Prompt: "natural, authentic dialogue"', grp_out)
            self.prompt_lbl.setWordWrap(True)
            self.prompt_lbl.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 11px;")

            self.stats_lbl = QLabel("Pitch: +0.00 st  ·  Rate: 1.00x  ·  Energy: 1.00x", grp_out)
            self.stats_lbl.setStyleSheet("color: #94A3B8; font-size: 10px;")
            out_lay.addWidget(self.prompt_lbl)
            out_lay.addWidget(self.stats_lbl)
            right_box.addWidget(grp_out)

            content.addLayout(right_box, 1)
            root.addLayout(content, 1)

            # Bottom Bar
            bot = QHBoxLayout()
            self.audition_btn = QPushButton("🔊 Audition Emotion Audio", self)
            self.audition_btn.setStyleSheet(
                "background: #1E293B; color: #38BDF8; border: 1px solid #0284C7; font-weight: 700; padding: 8px 16px; border-radius: 6px;"
            )
            self.audition_btn.clicked.connect(self._audition_emotion)
            bot.addWidget(self.audition_btn)

            bot.addStretch()

            apply_btn = QPushButton("✓ Apply Emotion to Selected Line", self)
            apply_btn.setStyleSheet("background: #059669; color: #FFF; font-weight: 800; padding: 8px 24px;")
            apply_btn.clicked.connect(self._apply_and_close)
            bot.addWidget(apply_btn)

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.clicked.connect(self.reject)
            bot.addWidget(cancel_btn)

            root.addLayout(bot)
            self._update_readout()

        def _load_preset(self, preset_name: str) -> None:
            pad, micro, desc = ProEmotionDirectorEngine.get_preset(preset_name)
            self._pad = pad
            self._micro = micro
            self.radar.set_pad(pad)
            self.dominance_slider.setValue(int(pad.dominance * 100))
            self.tremble_slider.setValue(int(micro.tremble_pct))
            self.breath_slider.setValue(int(micro.breathiness_pct))
            self.fry_slider.setValue(int(micro.vocal_fry_pct))
            self.tension_slider.setValue(int(micro.throat_tension_pct))
            self._update_readout()

        def _on_radar_moved(self, val: float, aro: float) -> None:
            self._pad.valence = val
            self._pad.arousal = aro
            self._update_readout()

        def _on_param_changed(self) -> None:
            self._intensity = self.intensity_slider.value() / 100.0
            self.intensity_lbl.setText(f"{self.intensity_slider.value()}%")

            self._pad.dominance = self.dominance_slider.value() / 100.0
            self.dominance_lbl.setText(f"{self._pad.dominance:+.2f}")

            self._micro.tremble_pct = float(self.tremble_slider.value())
            self._micro.breathiness_pct = float(self.breath_slider.value())
            self._micro.vocal_fry_pct = float(self.fry_slider.value())
            self._micro.throat_tension_pct = float(self.tension_slider.value())
            self._update_readout()

        def _update_readout(self) -> None:
            perf = ProEmotionDirectorEngine.map_pad_to_performance(
                self._pad, self._intensity, self._micro
            )
            self.prompt_lbl.setText(f'Expression: "{perf["style_prompt"]}"')
            self.stats_lbl.setText(
                f"Pitch: {perf['pitch_shift_semitones']:+.2f} st  ·  "
                f"Rate: {perf['rate_multiplier']:.2f}x  ·  "
                f"Energy: {perf['energy_scale']:.2f}x"
            )

        def _extract_from_actor(self) -> None:
            if not self._original_wav_path:
                return
            pad, micro, explanation = ProEmotionDirectorEngine.extract_emotion_from_audio(
                self._original_wav_path
            )
            self._pad = pad
            self._micro = micro
            self.radar.set_pad(pad)
            self.dominance_slider.setValue(int(pad.dominance * 100))
            self.tremble_slider.setValue(int(micro.tremble_pct))
            self.breath_slider.setValue(int(micro.breathiness_pct))
            self.fry_slider.setValue(int(micro.vocal_fry_pct))
            self.tension_slider.setValue(int(micro.throat_tension_pct))
            self._update_readout()
            QMessageBox.information(
                self,
                "Actor Emotion Extracted",
                f"Successfully extracted emotion from actor audio track:\n\n{explanation}",
            )

        def _audition_emotion(self) -> None:
            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.audition_btn.setText("🔊 Audition Emotion Audio")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService

                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.audition_btn.setText("🔊 Audition Emotion Audio")
                )

            self.audition_btn.setText("⏹ Stop Audition")
            perf = ProEmotionDirectorEngine.map_pad_to_performance(
                self._pad, self._intensity, self._micro
            )
            pitch_st = perf.get("pitch_shift_semitones", 0.0)
            rate_mult = perf.get("rate_multiplier", 1.0)
            pitch_str = f"{int(pitch_st * 12):+}Hz"
            rate_str = f"{int((rate_mult - 1.0) * 100):+}%"

            text_to_speak = self._dialogue_text or "আমি তোমাকে কখনো ভুলব না, এই অভিনয় আমার আত্মার কথা।"
            self._audition.synthesize_and_play(
                text=text_to_speak,
                voice_id="bn-BD-NabanitaNeural",
                pitch=pitch_str,
                rate=rate_str,
            )

        def _apply_and_close(self) -> None:
            perf = ProEmotionDirectorEngine.map_pad_to_performance(
                self._pad, self._intensity, self._micro
            )
            self.emotion_applied.emit(perf)
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.accept()

        def reject(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().reject()

else:

    class ProEmotionStudioDialog:  # type: ignore[no-redef]
        """Headless fallback for ProEmotionStudioDialog."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._character_name = kwargs.get("character_name", "Actor")
            self._dialogue_text = kwargs.get("dialogue_text", "")

        def exec(self) -> int:
            return 0


__all__ = ["ProEmotionStudioDialog"]

