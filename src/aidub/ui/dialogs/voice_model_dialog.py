"""
Voice Model and AI Speech Engine Selector Dialog.

Allows configuring and testing voice engines:
- Chatterbox AI (Emotion-Aware & Voice Cloning)
- Microsoft Edge-TTS (Free Neural Voices)
- ElevenLabs / OpenAI TTS
- Custom RVC Voice Models
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QPainter,
        QPaintEvent,
        QPen,
    )
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class _PreviewWaveform(QWidget):
        """Mini dynamic waveform widget for voice test playback."""

        def __init__(self, color: str = "#8B5CF6", parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.color = color
            self.progress = 0.0
            self.setFixedHeight(50)
            import math

            self.peaks = [
                0.15 + 0.85 * abs(math.sin(i * 0.3) * math.cos(i * 0.12))
                for i in range(48)
            ]

        def set_progress(self, p: float) -> None:
            self.progress = max(0.0, min(1.0, p))
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mid_y = h / 2.0
            n = len(self.peaks)
            bar_w = max(2.0, (w - (n * 2.0)) / max(1, n))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#080D16")))
            painter.drawRoundedRect(0, 0, w, h, 6, 6)

            base = QColor(self.color)
            for i, pk in enumerate(self.peaks):
                x = i * (bar_w + 2.0)
                bh = max(3.0, pk * (h * 0.78))
                y = mid_y - (bh / 2.0)
                if (x / max(1.0, w)) <= self.progress:
                    painter.setBrush(QBrush(base))
                else:
                    dimmed = QColor(base)
                    dimmed.setAlpha(60)
                    painter.setBrush(QBrush(dimmed))
                painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bh), 1, 1)

            px = int(self.progress * w)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(px, 0, px, h)

    class VoiceModelDialog(QDialog):
        """Interactive studio dialog to configure and audition AI voice engines."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            current_engine: str = "chatterbox",
            target_language: str = "bn",
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("AI Voice Model Studio — Chatterbox & Neural Engines")
            self.setMinimumSize(580, 520)
            self.current_engine = current_engine
            self.target_language = target_language
            self._player: QMediaPlayer | None = None
            self._audio_out: QAudioOutput | None = None

            try:
                self._audio_out = QAudioOutput(self)
                self._player = QMediaPlayer(self)
                self._player.setAudioOutput(self._audio_out)
            except Exception:
                pass

            self._wave_timer = QTimer(self)
            self._wave_timer.setInterval(60)
            self._wave_prog = 0.0
            self._wave_timer.timeout.connect(self._on_wave_tick)

            self.setStyleSheet(
                "QDialog { background: #0A0E17; color: #F8FAFC; }"
                "QLabel { color: #F8FAFC; }"
                "QComboBox, QLineEdit {"
                "  background: #111827; color: #F8FAFC; border: 1px solid #1F2937;"
                "  border-radius: 6px; padding: 7px 12px; font-size: 12px;"
                "}"
                "QComboBox:focus, QLineEdit:focus { border-color: #8B5CF6; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)

            # Header Banner
            hdr = QHBoxLayout()
            icon = QLabel("🎙️", self)
            icon.setStyleSheet("font-size: 32px;")
            hdr.addWidget(icon)

            hdr_text = QVBoxLayout()
            title = QLabel("AI Voice Model Studio", self)
            title.setStyleSheet("font-size: 18px; font-weight: 800; color: #C084FC; letter-spacing: 0.3px;")
            sub = QLabel(
                "Configure emotional delivery, timbre matching, and preview live speech synthesis.", self
            )
            sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
            hdr_text.addWidget(title)
            hdr_text.addWidget(sub)
            hdr.addLayout(hdr_text)
            hdr.addStretch()
            layout.addLayout(hdr)

            # Engine Selector Card
            eng_card = QFrame(self)
            eng_card.setStyleSheet(
                "QFrame{background:#0F1422;border:1px solid #1E283B;border-radius:10px;padding:14px;}"
            )
            eng_lay = QVBoxLayout(eng_card)
            eng_lay.setSpacing(10)

            eng_lbl = QLabel("PRIMARY VOICE ENGINE", eng_card)
            eng_lbl.setStyleSheet("font-size:10px;font-weight:700;color:#8B5CF6;letter-spacing:1px;")
            eng_lay.addWidget(eng_lbl)

            self.engine_combo = QComboBox(eng_card)
            self.engine_combo.addItem("✦ Chatterbox AI (Expressive Emotion & Voice Cloning)", "chatterbox")
            self.engine_combo.addItem("✦ Microsoft Edge-TTS (Ultra-Fast Neural — Free)", "edge_tts")
            self.engine_combo.addItem("✦ Two-Stage Character RVC v2 (Actor Timbre Transfer)", "rvc")
            self.engine_combo.addItem("✦ ElevenLabs / Studio Cloud TTS", "elevenlabs")

            # Set current index
            idx = 0
            for i in range(self.engine_combo.count()):
                if self.engine_combo.itemData(i) == current_engine:
                    idx = i
                    break
            self.engine_combo.setCurrentIndex(idx)
            eng_lay.addWidget(self.engine_combo)

            # Emotion Delivery Chips
            emo_lbl = QLabel("CINEMATIC EMOTION TONE", eng_card)
            emo_lbl.setStyleSheet("font-size:10px;font-weight:700;color:#94A3B8;letter-spacing:1px;margin-top:4px;")
            eng_lay.addWidget(emo_lbl)

            emo_chips_lay = QHBoxLayout()
            emo_chips_lay.setSpacing(6)
            self._emo_btns: list[QPushButton] = []
            self._selected_emotion = "neutral"

            for emo_name, emo_key in (
                ("Neutral", "neutral"),
                ("Joy / Confident", "joy"),
                ("Angry / Dramatic", "angry"),
                ("Sad / Soft", "sad"),
                ("Whisper", "whisper"),
                ("Shout", "shout"),
            ):
                ebtn = QPushButton(emo_name, eng_card)
                ebtn.setCursor(Qt.CursorShape.PointingHandCursor)
                ebtn.setFixedHeight(26)
                if emo_key == "neutral":
                    ebtn.setStyleSheet(
                        "background:#8B5CF6;color:#FFF;border:none;border-radius:13px;padding:0 12px;font-size:11px;font-weight:700;"
                    )
                else:
                    ebtn.setStyleSheet(
                        "background:#162032;color:#94A3B8;border:1px solid #233045;border-radius:13px;padding:0 12px;font-size:11px;"
                        "QPushButton:hover{color:#FFF;background:#202B40;}"
                    )
                ebtn.clicked.connect(lambda _c=False, k=emo_key, b=ebtn: self._select_emotion_chip(k, b))
                emo_chips_lay.addWidget(ebtn)
                self._emo_btns.append(ebtn)

            self.emo_combo = QComboBox(eng_card)
            self.emo_combo.addItems(["Neutral", "Joy", "Angry", "Sad", "Whisper", "Shout"])
            self.emo_combo.setVisible(False)
            self.emo_combo.currentTextChanged.connect(self._on_combo_emotion_changed)
            eng_lay.addWidget(self.emo_combo)

            emo_chips_lay.addStretch()
            eng_lay.addLayout(emo_chips_lay)

            layout.addWidget(eng_card)

            # Live Waveform Preview Card
            prev_card = QFrame(self)
            prev_card.setStyleSheet(
                "QFrame{background:#0F1422;border:1px solid #1E283B;border-radius:10px;padding:14px;}"
            )
            prev_lay = QVBoxLayout(prev_card)
            prev_lay.setSpacing(10)

            prev_hdr = QLabel("LIVE AUDITION & WAVEFORM PREVIEW", prev_card)
            prev_hdr.setStyleSheet("font-size:10px;font-weight:700;color:#22D3EE;letter-spacing:1px;")
            prev_lay.addWidget(prev_hdr)

            default_test_line = (
                "আমি এখানে সিনেমা ডাবিং করতে এসেছি।"
                if target_language == "bn"
                else "Welcome to the AI Movie Dubbing Studio."
            )
            self.test_line_edit = QLineEdit(default_test_line, prev_card)
            prev_lay.addWidget(self.test_line_edit)

            self.waveform_widget = _PreviewWaveform(color="#8B5CF6", parent=prev_card)
            prev_lay.addWidget(self.waveform_widget)

            # Audition Action Button Row
            aud_row = QHBoxLayout()
            aud_row.addStretch()

            self.preview_btn = QPushButton("▶  Generate & Play Audition", prev_card)
            self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.preview_btn.setFixedHeight(34)
            self.preview_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #8B5CF6); "
                "color: #FFF; border: none; border-radius: 6px; padding: 0 18px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #9333EA; }"
            )
            self.preview_btn.clicked.connect(self._test_voice)
            aud_row.addWidget(self.preview_btn)
            prev_lay.addLayout(aud_row)

            layout.addWidget(prev_card)
            layout.addStretch()

            # Dialog Bottom Buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton { background: #162030; color: #94A3B8; border: 1px solid #233045; "
                "border-radius: 6px; padding: 8px 18px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background: #202B40; color: #FFF; }"
            )
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

            apply_btn = QPushButton("Apply Voice Model", self)
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; "
                "border-radius: 6px; padding: 8px 22px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #3B82F6; }"
            )
            apply_btn.clicked.connect(self.accept)
            btn_row.addWidget(apply_btn)

            layout.addLayout(btn_row)

        def _select_emotion_chip(self, key: str, btn: QPushButton) -> None:
            self._selected_emotion = key
            for b in self._emo_btns:
                if b == btn:
                    b.setStyleSheet(
                        "background:#8B5CF6;color:#FFF;border:none;border-radius:13px;padding:0 12px;font-size:11px;font-weight:700;"
                    )
                else:
                    b.setStyleSheet(
                        "background:#162032;color:#94A3B8;border:1px solid #233045;border-radius:13px;padding:0 12px;font-size:11px;"
                        "QPushButton:hover{color:#FFF;background:#202B40;}"
                    )

        def _on_combo_emotion_changed(self, text: str) -> None:
            self._selected_emotion = text.split(" ")[0].lower()

        def get_selected_engine(self) -> str:
            return str(self.engine_combo.currentData() or "chatterbox")

        def get_selected_emotion(self) -> str:
            if hasattr(self, "emo_combo") and self.emo_combo.currentText().lower() not in {"neutral", ""} and self._selected_emotion == "neutral":
                return self.emo_combo.currentText().split(" ")[0].lower()
            return self._selected_emotion

        def _on_wave_tick(self) -> None:
            self._wave_prog += 0.03
            if self._wave_prog > 1.0:
                self._wave_prog = 0.0
                self._wave_timer.stop()
            self.waveform_widget.set_progress(self._wave_prog)

        def _test_voice(self) -> None:
            text = self.test_line_edit.text().strip()
            if not text:
                return

            self.preview_btn.setEnabled(False)
            self.preview_btn.setText("Generating Speech…")

            import tempfile
            temp_out = Path(tempfile.gettempdir()) / "voice_preview.wav"

            try:
                engine = self.get_selected_engine()
                emotion = self.get_selected_emotion()

                if engine == "chatterbox":
                    from aidub.adapters.voice.chatterbox_adapter import ChatterboxAdapter

                    ChatterboxAdapter().synthesize_to_file(text, temp_out, emotion=emotion)
                else:
                    from aidub.adapters.voice.edge_tts_adapter import DEFAULT_BENGALI_VOICE, EdgeTTSAdapter
                    from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run

                    mp3_temp = temp_out.with_suffix(".mp3")
                    EdgeTTSAdapter(DEFAULT_BENGALI_VOICE).synthesize_to_file(text, mp3_temp)
                    _run([_ffmpeg_exe(), "-y", "-i", str(mp3_temp), str(temp_out)])
                    mp3_temp.unlink(missing_ok=True)

                if temp_out.is_file() and temp_out.stat().st_size > 0:
                    if self._player is not None:
                        self._player.setSource(QUrl.fromLocalFile(str(temp_out.resolve())))
                        self._player.play()
                    self._wave_prog = 0.0
                    self._wave_timer.start()
                    self.preview_btn.setText("✓ Playing Preview")
                else:
                    self.preview_btn.setText("▶ Generate & Play Audition")
            except Exception as exc:
                logger.warning("Voice preview failed: %s", exc)
                self.preview_btn.setText("▶ Preview Error")
            finally:
                self.preview_btn.setEnabled(True)


__all__ = ["VoiceModelDialog"]


