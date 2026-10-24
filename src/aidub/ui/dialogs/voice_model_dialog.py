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
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QFont
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class VoiceModelDialog(QDialog):
        """Interactive dialog to select, configure, and preview AI voice engines."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            current_engine: str = "chatterbox",
            target_language: str = "bn",
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("AI Voice Model Studio — Chatterbox & Neural Engines")
            self.setMinimumSize(540, 460)
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

            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #E2E8F0; }"
                "QLabel { color: #E2E8F0; }"
                "QComboBox, QLineEdit {"
                "  background: #111622; color: #F8FAFC; border: 1px solid #1E293B;"
                "  border-radius: 4px; padding: 6px 10px; font-size: 12px;"
                "}"
                "QComboBox:focus, QLineEdit:focus { border-color: #38BDF8; }"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(14)

            # Header
            hdr = QHBoxLayout()
            icon = QLabel("🎙️", self)
            icon.setStyleSheet("font-size: 28px;")
            hdr.addWidget(icon)

            hdr_text = QVBoxLayout()
            title = QLabel("AI Voice Model Engine", self)
            title.setStyleSheet("font-size: 16px; font-weight: 800; color: #A855F7;")
            sub = QLabel("Select speech synthesis model, configure emotional delivery, and preview.", self)
            sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
            hdr_text.addWidget(title)
            hdr_text.addWidget(sub)
            hdr.addLayout(hdr_text)
            hdr.addStretch()
            layout.addLayout(hdr)

            # Engine Selector Box
            eng_box = QGroupBox("Primary Voice Engine", self)
            eng_box.setStyleSheet(
                "QGroupBox { font-size: 12px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; "
                "border-radius: 6px; margin-top: 10px; padding-top: 15px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
            )
            eng_lay = QVBoxLayout(eng_box)
            eng_lay.setSpacing(8)

            self.engine_combo = QComboBox(self)
            self.engine_combo.addItem("✦ Chatterbox AI (Expressive Emotion & Voice Cloning)", "chatterbox")
            self.engine_combo.addItem("✦ Microsoft Edge-TTS (Fast Neural — Free & High Quality)", "edge_tts")
            self.engine_combo.addItem("✦ ElevenLabs / OpenAI TTS (Studio API)", "elevenlabs")
            self.engine_combo.addItem("✦ Custom RVC Cloned Character Voice", "rvc")

            # Set current index
            idx = 0
            for i in range(self.engine_combo.count()):
                if self.engine_combo.itemData(i) == current_engine:
                    idx = i
                    break
            self.engine_combo.setCurrentIndex(idx)
            eng_lay.addWidget(self.engine_combo)

            # Emotion Delivery Selector
            emo_row = QHBoxLayout()
            emo_row.addWidget(QLabel("Emotion Tone:", self))
            self.emo_combo = QComboBox(self)
            self.emo_combo.addItems(["Neutral", "Angry", "Sad", "Joy", "Whisper", "Shout", "Fear"])
            emo_row.addWidget(self.emo_combo, 1)
            eng_lay.addLayout(emo_row)

            layout.addWidget(eng_box)

            # Test Preview Box
            test_box = QGroupBox("Live Voice Preview", self)
            test_box.setStyleSheet(
                "QGroupBox { font-size: 12px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; "
                "border-radius: 6px; margin-top: 10px; padding-top: 15px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
            )
            test_lay = QVBoxLayout(test_box)
            test_lay.setSpacing(8)

            default_test_line = "আমি এখানে সিনেমা ডাবিং করতে এসেছি।" if target_language == "bn" else "Hello, I am testing the AI voice line."
            self.test_line_edit = QLineEdit(default_test_line, self)
            test_lay.addWidget(self.test_line_edit)

            self.preview_btn = QPushButton("▶  Generate & Play Voice Preview", self)
            self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.preview_btn.setStyleSheet(
                "QPushButton { background: #7C3AED; color: #FFF; border: none; "
                "border-radius: 4px; padding: 8px 16px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background: #8B5CF6; }"
            )
            self.preview_btn.clicked.connect(self._test_voice)
            test_lay.addWidget(self.preview_btn, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(test_box)

            layout.addStretch()

            # Dialog Buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setStyleSheet("QPushButton { background: transparent; color: #94A3B8; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 16px; }")
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

            apply_btn = QPushButton("Apply Voice Model", self)
            apply_btn.setStyleSheet("QPushButton { background: #2563EB; color: #FFF; border: none; border-radius: 4px; padding: 6px 20px; font-weight: 700; }")
            apply_btn.clicked.connect(self.accept)
            btn_row.addWidget(apply_btn)
            layout.addLayout(btn_row)

        def get_selected_engine(self) -> str:
            return str(self.engine_combo.currentData() or "chatterbox")

        def get_selected_emotion(self) -> str:
            return str(self.emo_combo.currentText()).lower()

        def _test_voice(self) -> None:
            text = self.test_line_edit.text().strip()
            if not text:
                return

            self.preview_btn.setEnabled(False)
            self.preview_btn.setText("Generating Preview…")

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
                    mp3_temp = temp_out.with_suffix(".mp3")
                    EdgeTTSAdapter(DEFAULT_BENGALI_VOICE).synthesize_to_file(text, mp3_temp)
                    from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run
                    _run([_ffmpeg_exe(), "-y", "-i", str(mp3_temp), str(temp_out)])
                    mp3_temp.unlink(missing_ok=True)

                if temp_out.is_file() and temp_out.stat().st_size > 0:
                    if self._player is not None:
                        self._player.setSource(QUrl.fromLocalFile(str(temp_out.resolve())))
                        self._player.play()
                    self.preview_btn.setText("✓ Playing Preview")
                else:
                    self.preview_btn.setText("▶ Generate & Play Voice Preview")
            except Exception as exc:
                logger.warning("Voice preview failed: %s", exc)
                self.preview_btn.setText("▶ Preview Error")
            finally:
                self.preview_btn.setEnabled(True)


__all__ = ["VoiceModelDialog"]

