"""Preferences and Application Settings Dialog."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from aidub.infrastructure.preferences import (
    HardwareOption,
    PrivacyOption,
    ThemeOption,
    UserPreferences,
    load_user_preferences,
    save_user_preferences,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class PreferencesDialog(QDialog):
        """User preferences configuration modal dialog."""

        preferences_saved = Signal(object)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Studio Preferences & Hardware Settings")
            self.setMinimumSize(620, 520)
            self.setModal(True)
            self.setStyleSheet(
                "QDialog { background: #0E131F; color: #F1F5F9; }"
                "QLabel { color: #E2E8F0; font-size: 11px; font-weight: 600; }"
                "QLineEdit, QComboBox, QSpinBox { background: #162032; color: #FFF; border: 1px solid #233045; "
                "border-radius: 4px; padding: 5px 8px; font-size: 11px; min-height: 24px; }"
                "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #38BDF8; }"
                "QTabWidget::pane { border: 1px solid #1E293B; background: #131A29; border-radius: 6px; }"
                "QTabBar::tab { background: #0F172A; color: #94A3B8; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: 600; }"
                "QTabBar::tab:selected { background: #1E293B; color: #38BDF8; border-bottom: 2px solid #38BDF8; }"
            )

            self._prefs = load_user_preferences()

            layout = QVBoxLayout(self)
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setSpacing(12)

            # Header
            header_lbl = QLabel("⚙️ Studio Preferences & Hardware", self)
            header_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8;")
            layout.addWidget(header_lbl)

            desc_lbl = QLabel(
                "Configure FFmpeg, AI runtime devices, ASR model size, speech synthesis, and translation engines.",
                self,
            )
            desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; margin-bottom: 4px;")
            layout.addWidget(desc_lbl)

            tabs = QTabWidget(self)

            # ── Tab 1: AI & Models ──────────────────────────────────────
            ai_tab = QWidget()
            ai_layout = QFormLayout(ai_tab)
            ai_layout.setContentsMargins(14, 14, 14, 14)
            ai_layout.setSpacing(12)
            ai_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            # Compute Device (auto / cuda / cpu / directml)
            self.hw_combo = QComboBox(ai_tab)
            devices = [
                ("Auto-Detect (CUDA with CPU Fallback)", "auto"),
                ("CUDA (NVIDIA GPU Acceleration)", "cuda"),
                ("CPU Only (Safe / Low Memory)", "cpu"),
                ("DirectML (Windows Acceleration)", "directml"),
            ]
            for label, val in devices:
                self.hw_combo.addItem(label, val)
            dev_idx = self.hw_combo.findData(self._prefs.hardware_acceleration or self._prefs.device)
            if dev_idx >= 0:
                self.hw_combo.setCurrentIndex(dev_idx)
            ai_layout.addRow("Compute Device:", self.hw_combo)
            self.device_combo = self.hw_combo

            # ASR Model Size
            self.asr_combo = QComboBox(ai_tab)
            asr_models = [
                ("base (Fastest, ~140 MB)", "base"),
                ("tiny (Ultra-light, ~75 MB)", "tiny"),
                ("small (Balanced, ~460 MB)", "small"),
                ("medium (High accuracy, ~1.5 GB)", "medium"),
                ("large-v3 (Studio master, ~3.0 GB)", "large-v3"),
            ]
            for label, val in asr_models:
                self.asr_combo.addItem(label, val)
            asr_idx = self.asr_combo.findData(self._prefs.asr_model_size)
            if asr_idx >= 0:
                self.asr_combo.setCurrentIndex(asr_idx)
            ai_layout.addRow("ASR Model Size:", self.asr_combo)

            # Translation Engine
            self.trans_combo = QComboBox(ai_tab)
            trans_engines = [
                ("NLLB-200 (Offline distilled 600M)", "nllb-200"),
                ("Google Gemini AI API (Cloud)", "gemini"),
                ("OpenAI / OpenRouter API (Cloud)", "openai"),
            ]
            for label, val in trans_engines:
                self.trans_combo.addItem(label, val)
            trans_idx = self.trans_combo.findData(self._prefs.translation_engine)
            if trans_idx >= 0:
                self.trans_combo.setCurrentIndex(trans_idx)
            ai_layout.addRow("Translation Engine:", self.trans_combo)

            # TTS Voice
            self.tts_voice_combo = QComboBox(ai_tab)
            tts_voices = [
                ("bn-BD-PradeepNeural (Bangla Male)", "bn-BD-PradeepNeural"),
                ("bn-BD-NabanitaNeural (Bangla Female)", "bn-BD-NabanitaNeural"),
                ("bn-IN-BashkarNeural (Bangla Male - India)", "bn-IN-BashkarNeural"),
                ("bn-IN-TanishaaNeural (Bangla Female - India)", "bn-IN-TanishaaNeural"),
                ("facebook/mms-tts-ben (Offline MMS-TTS)", "facebook/mms-tts-ben"),
            ]
            for label, val in tts_voices:
                self.tts_voice_combo.addItem(label, val)
            voice_idx = self.tts_voice_combo.findData(self._prefs.tts_voice)
            if voice_idx >= 0:
                self.tts_voice_combo.setCurrentIndex(voice_idx)
            ai_layout.addRow("Default TTS Voice:", self.tts_voice_combo)

            # Model Cache Directory
            cache_row = QHBoxLayout()
            self.cache_edit = QLineEdit(ai_tab)
            default_cache = os.environ.get(
                "HF_HOME",
                str(Path.home() / ".cache" / "huggingface" / "hub"),
            )
            self.cache_edit.setText(self._prefs.model_cache_dir or default_cache)
            browse_cache_btn = QPushButton("Browse…", ai_tab)
            browse_cache_btn.clicked.connect(self._browse_cache_dir)
            cache_row.addWidget(self.cache_edit)
            cache_row.addWidget(browse_cache_btn)
            ai_layout.addRow("Model Cache Dir:", cache_row)

            tabs.addTab(ai_tab, "🧠 AI & Models")

            # ── Tab 2: Media & System ───────────────────────────────────
            media_tab = QWidget()
            media_layout = QFormLayout(media_tab)
            media_layout.setContentsMargins(14, 14, 14, 14)
            media_layout.setSpacing(12)
            media_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            # FFmpeg Path
            ffmpeg_row = QHBoxLayout()
            self.ffmpeg_edit = QLineEdit(media_tab)
            detected_ffmpeg = self._detect_ffmpeg()
            self.ffmpeg_edit.setText(self._prefs.ffmpeg_path or detected_ffmpeg)
            browse_ffmpeg_btn = QPushButton("Browse…", media_tab)
            browse_ffmpeg_btn.clicked.connect(self._browse_ffmpeg_path)
            auto_ffmpeg_btn = QPushButton("Auto-Detect", media_tab)
            auto_ffmpeg_btn.clicked.connect(self._auto_detect_ffmpeg)
            ffmpeg_row.addWidget(self.ffmpeg_edit)
            ffmpeg_row.addWidget(browse_ffmpeg_btn)
            ffmpeg_row.addWidget(auto_ffmpeg_btn)
            media_layout.addRow("FFmpeg Binary:", ffmpeg_row)

            # Auto-Save Interval
            self.autosave_spin = QSpinBox(media_tab)
            self.autosave_spin.setRange(0, 60)
            self.autosave_spin.setSuffix(" min (0=Off)")
            self.autosave_spin.setValue(self._prefs.auto_save_interval_minutes)
            media_layout.addRow("Auto-Save Interval:", self.autosave_spin)

            # Privacy Policy
            self.privacy_combo = QComboBox(media_tab)
            privacy_options = [
                ("Standard Online (Cloud Providers Allowed)", "online"),
                ("Private Studio Mode (Strictly Offline)", "offline"),
            ]
            for label, val in privacy_options:
                self.privacy_combo.addItem(label, val)
            p_idx = self.privacy_combo.findData(self._prefs.privacy_mode)
            if p_idx >= 0:
                self.privacy_combo.setCurrentIndex(p_idx)
            media_layout.addRow("Privacy Mode:", self.privacy_combo)

            tabs.addTab(media_tab, "🎥 Media & System")

            # ── Tab 3: Appearance ───────────────────────────────────────
            app_tab = QWidget()
            app_layout = QFormLayout(app_tab)
            app_layout.setContentsMargins(14, 14, 14, 14)
            app_layout.setSpacing(12)
            app_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            self.theme_combo = QComboBox(app_tab)
            themes = [
                ("Studio Dark (Default)", "studio_dark"),
                ("Broadcast Gray", "broadcast_gray"),
                ("Cyber Dark", "cyber_dark"),
                ("High Contrast", "high_contrast"),
                ("Light Studio", "light_studio"),
            ]
            for label, val in themes:
                self.theme_combo.addItem(label, val)
            t_idx = self.theme_combo.findData(self._prefs.theme)
            if t_idx >= 0:
                self.theme_combo.setCurrentIndex(t_idx)
            app_layout.addRow("Application Theme:", self.theme_combo)

            self.lang_combo = QComboBox(app_tab)
            languages = [
                ("Bengali (Bangladesh) [bn-BD]", "bn-BD"),
                ("Bengali (India) [bn-IN]", "bn-IN"),
                ("Hindi (India) [hi-IN]", "hi-IN"),
                ("English (US) [en-US]", "en-US"),
            ]
            for label, val in languages:
                self.lang_combo.addItem(label, val)
            l_idx = self.lang_combo.findData(self._prefs.default_target_language)
            if l_idx >= 0:
                self.lang_combo.setCurrentIndex(l_idx)
            app_layout.addRow("Default Target Lang:", self.lang_combo)

            tabs.addTab(app_tab, "🎨 Appearance")

            layout.addWidget(tabs)

            # Button Bar
            btn_box = QHBoxLayout()
            btn_box.setSpacing(10)

            reset_btn = QPushButton("Reset to Defaults", self)
            reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #94A3B8; border: 1px solid #334155; "
                "border-radius: 5px; padding: 7px 14px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #1E293B; color: #FFF; }"
            )
            reset_btn.clicked.connect(self._reset_defaults)
            btn_box.addWidget(reset_btn)

            btn_box.addStretch()

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #E2E8F0; border: 1px solid #334155; "
                "border-radius: 5px; padding: 7px 16px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #2D3D54; }"
            )
            cancel_btn.clicked.connect(self.reject)
            btn_box.addWidget(cancel_btn)

            save_btn = QPushButton("Save Preferences", self)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; "
                "border-radius: 5px; padding: 7px 18px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #1D4ED8; }"
            )
            save_btn.clicked.connect(self._save)
            btn_box.addWidget(save_btn)

            layout.addLayout(btn_box)

        def _detect_ffmpeg(self) -> str:
            which_p = shutil.which("ffmpeg")
            if which_p:
                return which_p
            fallback = Path.home() / ".local" / "bin" / "ffmpeg.exe"
            if fallback.is_file():
                return str(fallback)
            return ""

        def _auto_detect_ffmpeg(self) -> None:
            detected = self._detect_ffmpeg()
            if detected:
                self.ffmpeg_edit.setText(detected)
                QMessageBox.information(self, "FFmpeg Detected", f"Found FFmpeg at:\n{detected}")
            else:
                QMessageBox.warning(self, "Not Found", "Could not automatically locate FFmpeg on this system.")

        def _browse_ffmpeg_path(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select FFmpeg Executable", "", "Executables (*.exe);;All Files (*)"
            )
            if path:
                self.ffmpeg_edit.setText(path)

        def _browse_cache_dir(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "Select Model Cache Directory")
            if path:
                self.cache_edit.setText(path)

        def _reset_defaults(self) -> None:
            defaults = UserPreferences()
            self._prefs = defaults
            self.hw_combo.setCurrentIndex(self.hw_combo.findData(defaults.hardware_acceleration))
            self.asr_combo.setCurrentIndex(self.asr_combo.findData(defaults.asr_model_size))
            self.trans_combo.setCurrentIndex(self.trans_combo.findData(defaults.translation_engine))
            self.tts_voice_combo.setCurrentIndex(self.tts_voice_combo.findData(defaults.tts_voice))
            self.autosave_spin.setValue(defaults.auto_save_interval_minutes)
            self.privacy_combo.setCurrentIndex(self.privacy_combo.findData(defaults.privacy_mode))
            self.theme_combo.setCurrentIndex(self.theme_combo.findData(defaults.theme))
            self.lang_combo.setCurrentIndex(self.lang_combo.findData(defaults.default_target_language))
            self.ffmpeg_edit.setText(self._detect_ffmpeg())

        def _save(self) -> None:
            new_theme: ThemeOption = self.theme_combo.currentData()
            new_hw: HardwareOption = self.hw_combo.currentData()
            new_privacy: PrivacyOption = self.privacy_combo.currentData()

            ffmpeg_val = self.ffmpeg_edit.text().strip()
            cache_val = self.cache_edit.text().strip()

            updated = UserPreferences(
                theme=new_theme,
                default_target_language=str(self.lang_combo.currentData()),
                default_tts_engine=str(self._prefs.default_tts_engine),
                auto_save_interval_minutes=self.autosave_spin.value(),
                hardware_acceleration=new_hw,
                privacy_mode=new_privacy,
                ffmpeg_path=ffmpeg_val,
                model_cache_dir=cache_val,
                asr_model_size=str(self.asr_combo.currentData()),
                translation_engine=str(self.trans_combo.currentData()),
                tts_voice=str(self.tts_voice_combo.currentData()),
                device=str(self.device_combo.currentData()),
                last_project_path=self._prefs.last_project_path,
            )

            # Apply runtime side-effects
            if ffmpeg_val:
                bin_dir = str(Path(ffmpeg_val).parent)
                current_path = os.environ.get("PATH", "")
                if bin_dir not in current_path.split(os.pathsep):
                    os.environ["PATH"] = bin_dir + os.pathsep + current_path
            if cache_val:
                os.environ["HF_HOME"] = cache_val

            success = save_user_preferences(updated)
            if success:
                self._prefs = updated
                self.preferences_saved.emit(updated)
                self.accept()
            else:
                QMessageBox.critical(
                    self, "Save Error", "Failed to save preferences to configuration file."
                )

        def get_preferences(self) -> UserPreferences:
            return self._prefs

else:

    class PreferencesDialog:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PySide6 required for PreferencesDialog")


__all__ = ["PreferencesDialog"]
