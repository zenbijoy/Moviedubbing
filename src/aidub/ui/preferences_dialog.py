"""Preferences and Application Settings Dialog."""

from __future__ import annotations

import logging
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
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QSpinBox,
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
            self.setMinimumSize(520, 420)
            self.setModal(True)
            self.setStyleSheet(
                "QDialog { background: #0E131F; color: #F1F5F9; }"
                "QLabel { color: #E2E8F0; font-size: 11px; font-weight: 600; }"
                "QComboBox, QSpinBox { background: #162032; color: #FFF; border: 1px solid #233045; "
                "border-radius: 4px; padding: 5px 8px; font-size: 11px; min-height: 24px; }"
                "QComboBox:focus, QSpinBox:focus { border-color: #38BDF8; }"
            )

            self._prefs = load_user_preferences()

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(14)

            # Header
            header_lbl = QLabel("⚙️ Studio Preferences", self)
            header_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8;")
            layout.addWidget(header_lbl)

            desc_lbl = QLabel(
                "Configure default languages, AI runtime preferences, auto-save, and privacy settings.",
                self,
            )
            desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; margin-bottom: 4px;")
            layout.addWidget(desc_lbl)

            form_frame = QFrame(self)
            form_frame.setStyleSheet(
                "QFrame { background: #131A29; border: 1px solid #1E293B; border-radius: 8px; padding: 12px; }"
            )
            form_layout = QFormLayout(form_frame)
            form_layout.setContentsMargins(12, 12, 12, 12)
            form_layout.setSpacing(12)
            form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            # 1. Theme
            self.theme_combo = QComboBox(form_frame)
            themes = [
                ("Studio Dark (Default)", "studio_dark"),
                ("Broadcast Gray", "broadcast_gray"),
                ("Cyber Dark", "cyber_dark"),
                ("High Contrast", "high_contrast"),
                ("Light Studio", "light_studio"),
            ]
            for label, val in themes:
                self.theme_combo.addItem(label, val)
            idx = self.theme_combo.findData(self._prefs.theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            form_layout.addRow("Application Theme:", self.theme_combo)

            # 2. Default Target Language
            self.lang_combo = QComboBox(form_frame)
            languages = [
                ("Bengali (Bangladesh) [bn-BD]", "bn-BD"),
                ("Bengali (India) [bn-IN]", "bn-IN"),
                ("Hindi (India) [hi-IN]", "hi-IN"),
                ("English (US) [en-US]", "en-US"),
                ("Spanish (Spain) [es-ES]", "es-ES"),
                ("French (France) [fr-FR]", "fr-FR"),
                ("German (Germany) [de-DE]", "de-DE"),
                ("Japanese (Japan) [ja-JP]", "ja-JP"),
            ]
            for label, val in languages:
                self.lang_combo.addItem(label, val)
            idx = self.lang_combo.findData(self._prefs.default_target_language)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
            form_layout.addRow("Default Target Language:", self.lang_combo)

            # 3. Default TTS Engine
            self.tts_combo = QComboBox(form_frame)
            engines = [
                ("Microsoft Edge-TTS (Free Neural)", "edge-tts"),
                ("Chatterbox AI (Emotion-Aware)", "chatterbox"),
                ("OpenAI TTS", "openai"),
                ("ElevenLabs", "elevenlabs"),
            ]
            for label, val in engines:
                self.tts_combo.addItem(label, val)
            idx = self.tts_combo.findData(self._prefs.default_tts_engine)
            if idx >= 0:
                self.tts_combo.setCurrentIndex(idx)
            form_layout.addRow("Default Speech Engine:", self.tts_combo)

            # 4. Auto-Save Interval
            self.autosave_spin = QSpinBox(form_frame)
            self.autosave_spin.setRange(0, 60)
            self.autosave_spin.setSuffix(" min (0=Off)")
            self.autosave_spin.setValue(self._prefs.auto_save_interval_minutes)
            form_layout.addRow("Auto-Save Interval:", self.autosave_spin)

            # 5. Hardware Acceleration
            self.hw_combo = QComboBox(form_frame)
            hw_options = [
                ("Auto-Detect (CUDA / DirectML / CPU)", "auto"),
                ("Force CPU Only (Safe Fallback)", "cpu"),
                ("NVIDIA CUDA", "cuda"),
                ("DirectML (AMD / Intel / Windows)", "directml"),
            ]
            for label, val in hw_options:
                self.hw_combo.addItem(label, val)
            idx = self.hw_combo.findData(self._prefs.hardware_acceleration)
            if idx >= 0:
                self.hw_combo.setCurrentIndex(idx)
            form_layout.addRow("Hardware Acceleration:", self.hw_combo)

            # 6. Privacy Policy
            self.privacy_combo = QComboBox(form_frame)
            privacy_options = [
                ("Standard Online (Cloud Providers Allowed)", "online"),
                ("Private Studio Mode (Strictly Offline)", "offline"),
            ]
            for label, val in privacy_options:
                self.privacy_combo.addItem(label, val)
            idx = self.privacy_combo.findData(self._prefs.privacy_mode)
            if idx >= 0:
                self.privacy_combo.setCurrentIndex(idx)
            form_layout.addRow("Privacy & Network:", self.privacy_combo)

            layout.addWidget(form_frame)

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

        def _reset_defaults(self) -> None:
            defaults = UserPreferences()
            idx = self.theme_combo.findData(defaults.theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            idx = self.lang_combo.findData(defaults.default_target_language)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
            idx = self.tts_combo.findData(defaults.default_tts_engine)
            if idx >= 0:
                self.tts_combo.setCurrentIndex(idx)
            self.autosave_spin.setValue(defaults.auto_save_interval_minutes)
            idx = self.hw_combo.findData(defaults.hardware_acceleration)
            if idx >= 0:
                self.hw_combo.setCurrentIndex(idx)
            idx = self.privacy_combo.findData(defaults.privacy_mode)
            if idx >= 0:
                self.privacy_combo.setCurrentIndex(idx)

        def _save(self) -> None:
            new_theme: ThemeOption = self.theme_combo.currentData()
            new_hw: HardwareOption = self.hw_combo.currentData()
            new_privacy: PrivacyOption = self.privacy_combo.currentData()

            updated = UserPreferences(
                theme=new_theme,
                default_target_language=str(self.lang_combo.currentData()),
                default_tts_engine=str(self.tts_combo.currentData()),
                auto_save_interval_minutes=self.autosave_spin.value(),
                hardware_acceleration=new_hw,
                privacy_mode=new_privacy,
            )

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
