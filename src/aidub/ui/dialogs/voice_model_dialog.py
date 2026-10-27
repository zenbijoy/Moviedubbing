"""
Voice Model and AI Speech Engine Selector Dialog.

Allows configuring and testing voice engines:
- Chatterbox AI (Emotion-Aware & Voice Cloning)
- Microsoft Edge-TTS (Free Neural Voices)
- ElevenLabs / OpenAI TTS
- Custom RVC Voice Models
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QPainter,
        QPaintEvent,
        QPen,
    )
    from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
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

    class _PreviewWaveform(QWidget):
        """Mini dynamic waveform widget for voice test playback."""

        def __init__(self, color: str = "#8B5CF6", parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.color = color
            self.progress = 0.0
            self.setFixedHeight(50)
            import math

            self.peaks = [
                0.15 + 0.85 * abs(math.sin(i * 0.3) * math.cos(i * 0.12)) for i in range(48)
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
                if QMediaDevices.audioOutputs():
                    self._audio_out = QAudioOutput(self)
                    self._player = QMediaPlayer(self)
                    self._player.setAudioOutput(self._audio_out)
                else:
                    self._audio_out = None
                    self._player = None
            except Exception:
                self._audio_out = None
                self._player = None

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
            title.setStyleSheet(
                "font-size: 18px; font-weight: 800; color: #C084FC; letter-spacing: 0.3px;"
            )
            sub = QLabel(
                "Configure emotional delivery, timbre matching, and preview live speech synthesis.",
                self,
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
            eng_lbl.setStyleSheet(
                "font-size:10px;font-weight:700;color:#8B5CF6;letter-spacing:1px;"
            )
            eng_lay.addWidget(eng_lbl)

            self.engine_combo = QComboBox(eng_card)
            self.engine_combo.addItem(
                "✦ Chatterbox AI (Expressive Emotion & Voice Cloning)", "chatterbox"
            )
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
            self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
            eng_lay.addWidget(self.engine_combo)

            # Language & Voice Row
            lang_voice_row = QHBoxLayout()
            lang_voice_row.setSpacing(10)

            # Language
            lang_col = QVBoxLayout()
            lang_col.setSpacing(4)
            lang_lbl = QLabel("TARGET LANGUAGE", eng_card)
            lang_lbl.setStyleSheet(
                "font-size:10px;font-weight:700;color:#94A3B8;letter-spacing:1px;"
            )
            lang_col.addWidget(lang_lbl)

            self.lang_combo = QComboBox(eng_card)
            lang_options = [
                ("Bengali (বাংলা)", "bn"),
                ("English (US)", "en"),
                ("Hindi (हिन्दी)", "hi"),
                ("Spanish (Español)", "es"),
                ("French (Français)", "fr"),
                ("German (Deutsch)", "de"),
                ("Japanese (日本語)", "ja"),
                ("Chinese (中文)", "zh"),
                ("Arabic (العربية)", "ar"),
                ("Portuguese (Português)", "pt"),
                ("Russian (Русский)", "ru"),
                ("Korean (한국어)", "ko"),
                ("Italian (Italiano)", "it"),
                ("Turkish (Türkçe)", "tr"),
            ]
            for name, code in lang_options:
                self.lang_combo.addItem(name, code)
            for i in range(self.lang_combo.count()):
                if self.lang_combo.itemData(i) == self.target_language:
                    self.lang_combo.setCurrentIndex(i)
                    break
            self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
            lang_col.addWidget(self.lang_combo)
            lang_voice_row.addLayout(lang_col, stretch=1)

            # Voice Model
            voice_col = QVBoxLayout()
            voice_col.setSpacing(4)
            voice_lbl = QLabel("VOICE MODEL", eng_card)
            voice_lbl.setStyleSheet(
                "font-size:10px;font-weight:700;color:#94A3B8;letter-spacing:1px;"
            )
            voice_col.addWidget(voice_lbl)

            self.voice_combo = QComboBox(eng_card)
            voice_col.addWidget(self.voice_combo)
            lang_voice_row.addLayout(voice_col, stretch=2)

            eng_lay.addLayout(lang_voice_row)

            # Rate & Pitch Adjustments
            rate_pitch_row = QHBoxLayout()
            rate_pitch_row.setSpacing(12)

            # Speed Rate
            rate_col = QVBoxLayout()
            rate_col.setSpacing(4)
            self.rate_val_lbl = QLabel("Rate: +0%", eng_card)
            self.rate_val_lbl.setStyleSheet("font-size:10px;font-weight:700;color:#CBD5E1;")
            rate_col.addWidget(self.rate_val_lbl)

            self.rate_slider = QSlider(Qt.Orientation.Horizontal, eng_card)
            self.rate_slider.setRange(-50, 50)
            self.rate_slider.setValue(0)
            self.rate_slider.setStyleSheet(
                "QSlider::groove:horizontal{height:4px;background:#1E293B;border-radius:2px;}"
                "QSlider::sub-page:horizontal{background:#8B5CF6;border-radius:2px;}"
                "QSlider::handle:horizontal{background:#E2E8F0;width:12px;height:12px;margin:-4px 0;border-radius:6px;}"
            )
            self.rate_slider.valueChanged.connect(
                lambda v: self.rate_val_lbl.setText(f"Rate: {v:+d}%")
            )
            rate_col.addWidget(self.rate_slider)
            rate_pitch_row.addLayout(rate_col)

            # Pitch
            pitch_col = QVBoxLayout()
            pitch_col.setSpacing(4)
            self.pitch_val_lbl = QLabel("Pitch: +0Hz", eng_card)
            self.pitch_val_lbl.setStyleSheet("font-size:10px;font-weight:700;color:#CBD5E1;")
            pitch_col.addWidget(self.pitch_val_lbl)

            self.pitch_slider = QSlider(Qt.Orientation.Horizontal, eng_card)
            self.pitch_slider.setRange(-50, 50)
            self.pitch_slider.setValue(0)
            self.pitch_slider.setStyleSheet(
                "QSlider::groove:horizontal{height:4px;background:#1E293B;border-radius:2px;}"
                "QSlider::sub-page:horizontal{background:#06B6D4;border-radius:2px;}"
                "QSlider::handle:horizontal{background:#E2E8F0;width:12px;height:12px;margin:-4px 0;border-radius:6px;}"
            )
            self.pitch_slider.valueChanged.connect(
                lambda v: self.pitch_val_lbl.setText(f"Pitch: {v:+d}Hz")
            )
            pitch_col.addWidget(self.pitch_slider)
            rate_pitch_row.addLayout(pitch_col)

            eng_lay.addLayout(rate_pitch_row)

            # Voice Cloning Consent & Authorization Checkbox
            self.chk_cloning_auth = QCheckBox(
                "I confirm I have explicit rights and authorization for voice cloning.",
                eng_card,
            )
            self.chk_cloning_auth.setChecked(True)
            self.chk_cloning_auth.setStyleSheet(
                "QCheckBox{color:#F59E0B;font-size:11px;font-weight:600;} QCheckBox::indicator{width:13px;height:13px;}"
            )
            eng_lay.addWidget(self.chk_cloning_auth)

            # Emotion Delivery Chips
            emo_lbl = QLabel("CINEMATIC EMOTION TONE", eng_card)
            emo_lbl.setStyleSheet(
                "font-size:10px;font-weight:700;color:#94A3B8;letter-spacing:1px;margin-top:4px;"
            )
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
                ebtn.clicked.connect(
                    lambda _c=False, k=emo_key, b=ebtn: self._select_emotion_chip(k, b)
                )
                emo_chips_lay.addWidget(ebtn)
                self._emo_btns.append(ebtn)

            self.emo_combo = QComboBox(eng_card)
            self.emo_combo.addItems(["Neutral", "Joy", "Angry", "Sad", "Whisper", "Shout"])
            self.emo_combo.setVisible(False)
            self.emo_combo.currentTextChanged.connect(self._on_combo_emotion_changed)
            eng_lay.addWidget(self.emo_combo)

            emo_chips_lay.addStretch()
            eng_lay.addLayout(emo_chips_lay)

            self._populate_voices()

            layout.addWidget(eng_card)

            # Live Waveform Preview Card
            prev_card = QFrame(self)
            prev_card.setStyleSheet(
                "QFrame{background:#0F1422;border:1px solid #1E283B;border-radius:10px;padding:14px;}"
            )
            prev_lay = QVBoxLayout(prev_card)
            prev_lay.setSpacing(10)

            prev_hdr = QLabel("LIVE AUDITION & WAVEFORM PREVIEW", prev_card)
            prev_hdr.setStyleSheet(
                "font-size:10px;font-weight:700;color:#22D3EE;letter-spacing:1px;"
            )
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

        def _populate_voices(self) -> None:
            self.voice_combo.clear()
            lang = self.get_selected_language()
            try:
                from aidub.adapters.voice.edge_tts_adapter import available_voices_for_language

                voices = available_voices_for_language(lang)
                for v in voices:
                    self.voice_combo.addItem(v)
            except Exception:
                self.voice_combo.addItem("Default Neural Voice")

        def _on_engine_changed(self, index: int) -> None:
            engine = self.get_selected_engine()
            is_cloning = engine in {"chatterbox", "rvc"}
            self.chk_cloning_auth.setVisible(is_cloning)

        def _on_language_changed(self, index: int) -> None:
            self._populate_voices()
            lang = self.get_selected_language()
            phrases = {
                "bn": "আমি এখানে সিনেমা ডাবিং করতে এসেছি।",
                "en": "Welcome to the AI Movie Dubbing Studio.",
                "hi": "नमस्ते, मैं फिल्म डबिंग के लिए तैयार हूँ।",
                "es": "Bienvenido al estudio de doblaje cinematográfico.",
                "fr": "Bienvenue au studio de doublage de films.",
                "de": "Willkommen im Film-Synchronstudio.",
                "ja": "映画の吹き替えスタジオへようこそ。",
                "zh": "欢迎来到电影配音工作室。",
                "ar": "مرحبًا بكم في استوديو دبلجة الأفلام.",
            }
            if lang in phrases:
                self.test_line_edit.setText(phrases[lang])

        def get_selected_language(self) -> str:
            if hasattr(self, "lang_combo"):
                return str(self.lang_combo.currentData() or self.target_language)
            return self.target_language

        def get_selected_voice(self) -> str:
            if hasattr(self, "voice_combo"):
                return str(self.voice_combo.currentText() or "")
            return ""

        def get_selected_rate(self) -> str:
            if hasattr(self, "rate_slider"):
                return f"{self.rate_slider.value():+d}%"
            return "+0%"

        def get_selected_pitch(self) -> str:
            if hasattr(self, "pitch_slider"):
                return f"{self.pitch_slider.value():+d}Hz"
            return "+0Hz"

        def get_configuration(self) -> dict[str, Any]:
            return {
                "engine": self.get_selected_engine(),
                "language": self.get_selected_language(),
                "voice": self.get_selected_voice(),
                "rate": self.get_selected_rate(),
                "pitch": self.get_selected_pitch(),
                "emotion": self.get_selected_emotion(),
            }

        def accept(self) -> None:
            engine = self.get_selected_engine()
            if engine in {"chatterbox", "rvc"} and not self.chk_cloning_auth.isChecked():
                QMessageBox.warning(
                    self,
                    "Authorization Required",
                    "Voice cloning requires explicit consent and rights authorization for production dubbing.",
                )
                return
            super().accept()

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
            self._selected_emotion = text.split(" ", maxsplit=1)[0].lower()

        def get_selected_engine(self) -> str:
            return str(self.engine_combo.currentData() or "chatterbox")

        def get_selected_emotion(self) -> str:
            if (
                hasattr(self, "emo_combo")
                and self.emo_combo.currentText().lower() not in {"neutral", ""}
                and self._selected_emotion == "neutral"
            ):
                return self.emo_combo.currentText().split(" ", maxsplit=1)[0].lower()
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

            engine = self.get_selected_engine()
            if engine in {"chatterbox", "rvc"} and not self.chk_cloning_auth.isChecked():
                QMessageBox.warning(
                    self,
                    "Authorization Required",
                    "Please check the authorization box to preview cloned voice models.",
                )
                return

            self.preview_btn.setEnabled(False)
            self.preview_btn.setText("Generating Speech…")

            lang = self.get_selected_language()
            voice = self.get_selected_voice()
            rate = self.get_selected_rate()
            pitch = self.get_selected_pitch()
            emotion = self.get_selected_emotion()

            cache_dir = Path("cache/tts")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_key = hashlib.sha256(
                f"{engine}:{lang}:{voice}:{rate}:{pitch}:{emotion}:{text}".encode()
            ).hexdigest()
            cached_wav = cache_dir / f"tts_{cache_key}.wav"

            try:
                if cached_wav.is_file() and cached_wav.stat().st_size > 0:
                    logger.info("Voice preview cache hit: %s", cached_wav)
                    temp_out = cached_wav
                elif engine == "chatterbox":
                    from aidub.adapters.voice.chatterbox_adapter import ChatterboxAdapter

                    ChatterboxAdapter().synthesize_to_file(text, cached_wav, emotion=emotion)
                    temp_out = cached_wav
                else:
                    from aidub.adapters.voice.edge_tts_adapter import (
                        DEFAULT_BENGALI_VOICE,
                        EdgeTTSAdapter,
                    )
                    from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run

                    selected_v = voice or DEFAULT_BENGALI_VOICE
                    mp3_temp = cached_wav.with_suffix(".mp3")
                    EdgeTTSAdapter(selected_v).synthesize_to_file(
                        text, mp3_temp, voice=selected_v, rate=rate, pitch=pitch
                    )
                    _run([_ffmpeg_exe(), "-y", "-i", str(mp3_temp), str(cached_wav)])
                    mp3_temp.unlink(missing_ok=True)
                    temp_out = cached_wav

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
