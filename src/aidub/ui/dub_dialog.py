"""
Dub Dialog and Error Reporting Dialog for AI Dubbing Studio.

Provides:
- DubDialog: Select target language (Bengali default) and Fast/Quality profile.
- DubbingErrorDialog: Clean operator error presentation with a one-click 'Copy details' button.
"""

from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QRadioButton,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


_LANGUAGES: list[tuple[str, str]] = [
    ("bn", "Bengali (বাংলা) — Default"),
    ("hi", "Hindi (हिन्दी)"),
    ("es", "Spanish (Español)"),
    ("fr", "French (Français)"),
    ("de", "German (Deutsch)"),
    ("ja", "Japanese (日本語)"),
    ("zh", "Mandarin (中文)"),
    ("ar", "Arabic (العربية)"),
    ("en", "English"),
    ("pt", "Portuguese (Português)"),
    ("ru", "Russian (Русский)"),
    ("ko", "Korean (한국어)"),
    ("it", "Italian (Italiano)"),
    ("tr", "Turkish (Türkçe)"),
]


if _QT:

    class DubDialog(QDialog):
        """Dialog for configuring target language and rendering profile before dubbing."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            current_lang: str = "bn",
            current_profile: str = "quality",
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Dub Movie — Settings")
            self.setModal(True)
            self.setMinimumWidth(460)
            self.setStyleSheet(
                "QDialog { background: #0D1118; color: #F7F9FC; }"
                "QLabel { color: #F7F9FC; }"
                "QGroupBox {"
                "  border: 1px solid #283446;"
                "  border-radius: 6px;"
                "  margin-top: 12px;"
                "  padding: 12px 10px 10px 10px;"
                "  font-weight: 700;"
                "  color: #9CA3AF;"
                "}"
                "QGroupBox::title {"
                "  subcontrol-origin: margin;"
                "  subcontrol-position: top left;"
                "  left: 10px;"
                "  padding: 0 4px;"
                "}"
                "QComboBox {"
                "  background: #161D28;"
                "  color: #F7F9FC;"
                "  border: 1px solid #283446;"
                "  border-radius: 4px;"
                "  padding: 6px 10px;"
                "  font-size: 13px;"
                "}"
                "QComboBox QAbstractItemView {"
                "  background: #111722;"
                "  color: #F7F9FC;"
                "  selection-background-color: #2563EB;"
                "  border: 1px solid #283446;"
                "}"
                "QRadioButton {"
                "  color: #E2E8F0;"
                "  font-size: 12px;"
                "  spacing: 8px;"
                "}"
                "QRadioButton::indicator {"
                "  width: 14px;"
                "  height: 14px;"
                "}"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(16)

            # Header Banner
            header = QLabel("🎙 Dub Movie", self)
            header_font = QFont()
            header_font.setPointSize(16)
            header_font.setBold(True)
            header.setFont(header_font)
            header.setStyleSheet("color: #4F8CFF;")
            layout.addWidget(header)

            subtitle = QLabel(
                "Select the localization language and dubbing quality profile.", self
            )
            subtitle.setStyleSheet("color: #9CA3AF; font-size: 12px;")
            layout.addWidget(subtitle)

            # Target Language Section
            lang_group = QGroupBox("Target Language", self)
            lang_lay = QVBoxLayout(lang_group)
            self.lang_combo = QComboBox(lang_group)
            default_index = 0
            for idx, (code, label) in enumerate(_LANGUAGES):
                self.lang_combo.addItem(label, code)
                if code.lower() == current_lang.lower():
                    default_index = idx
            self.lang_combo.setCurrentIndex(default_index)
            lang_lay.addWidget(self.lang_combo)
            layout.addWidget(lang_group)

            # Profile Section
            profile_group = QGroupBox("Dubbing Profile", self)
            prof_lay = QVBoxLayout(profile_group)
            prof_lay.setSpacing(10)

            self.quality_radio = QRadioButton(
                "Quality Profile — Theatrical Master (Diarization, Stems, Multi-Voice)", profile_group
            )
            self.fast_radio = QRadioButton(
                "Fast Profile — Rapid Draft Preview (Single pass, High speed)", profile_group
            )

            self.button_group = QButtonGroup(self)
            self.button_group.addButton(self.quality_radio)
            self.button_group.addButton(self.fast_radio)

            if current_profile.lower() == "fast":
                self.fast_radio.setChecked(True)
            else:
                self.quality_radio.setChecked(True)

            prof_lay.addWidget(self.quality_radio)
            prof_lay.addWidget(self.fast_radio)
            layout.addWidget(profile_group)

            # Advanced Studio & Broadcast Mastering Section
            advanced_group = QGroupBox("Studio & Broadcast Mastering", self)
            adv_lay = QVBoxLayout(advanced_group)
            adv_lay.setSpacing(10)

            self.isometric_chk = QCheckBox(
                "Isometric Lip-Sync Alignment (Match Syllable Count & Jaw Cadence)", advanced_group
            )
            self.isometric_chk.setChecked(True)
            self.isometric_chk.setStyleSheet("color: #E2E8F0; font-size: 12px;")
            adv_lay.addWidget(self.isometric_chk)

            # Acoustic Environment Reverb Matcher
            adv_lay.addWidget(QLabel("Acoustic Environment (Convolution Reverb):", advanced_group))
            self.reverb_combo = QComboBox(advanced_group)
            self.reverb_combo.addItem("None (Clean Dry Studio)", "none")
            self.reverb_combo.addItem("Living Room Interior (RT60: 0.4s)", "living_room")
            self.reverb_combo.addItem("Large Hall / Cathedral (RT60: 1.8s)", "large_hall")
            self.reverb_combo.addItem("Vehicle Cabin Interior (RT60: 0.2s)", "vehicle")
            self.reverb_combo.addItem("Street Exterior Ambience (RT60: 0.25s)", "street_exterior")
            adv_lay.addWidget(self.reverb_combo)

            # Broadcast Delivery Standard
            adv_lay.addWidget(QLabel("Broadcast Delivery Spec (ITU-R BS.1770-4):", advanced_group))
            self.qc_combo = QComboBox(advanced_group)
            self.qc_combo.addItem("Netflix 5.1 Surround (-24 LUFS, TP <= -1.0 dBTP)", "netflix")
            self.qc_combo.addItem("EBU R128 European Broadcast (-23 LUFS, TP <= -1.0 dBTP)", "ebu_r128")
            self.qc_combo.addItem("YouTube / Web 4K UHD (-14 LUFS, High Dynamic Range)", "youtube_web")
            self.qc_combo.addItem("Theatrical Master Archive (-27 LUFS)", "theatrical")
            adv_lay.addWidget(self.qc_combo)

            # C2PA Provenance Credentials
            self.c2pa_chk = QCheckBox(
                "Embed Cryptographic C2PA Content Credentials & AI Provenance", advanced_group
            )
            self.c2pa_chk.setChecked(True)
            self.c2pa_chk.setStyleSheet("color: #E2E8F0; font-size: 12px;")
            adv_lay.addWidget(self.c2pa_chk)

            layout.addWidget(advanced_group)

            # Button Box
            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1C2431; color: #E2E8F0; border: 1px solid #283446;"
                "  border-radius: 4px; padding: 7px 18px; font-weight: 600;"
                "}"
                "QPushButton:hover { background: #283446; }"
            )
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

            self.start_btn = QPushButton("Start Dubbing", self)
            self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.start_btn.setStyleSheet(
                "QPushButton {"
                "  background: #2563EB; color: #FFF; border: none;"
                "  border-radius: 4px; padding: 7px 22px; font-weight: 700;"
                "}"
                "QPushButton:hover { background: #3B82F6; }"
            )
            self.start_btn.clicked.connect(self.accept)
            btn_row.addWidget(self.start_btn)

            layout.addLayout(btn_row)

        def get_settings(self) -> tuple[str, str]:
            """Return (target_lang_code, quality_profile)."""
            target_lang = str(self.lang_combo.currentData() or "bn")
            quality_profile = "fast" if self.fast_radio.isChecked() else "quality"
            return target_lang, quality_profile

        def get_advanced_settings(self) -> dict[str, Any]:
            """Return comprehensive studio configuration dictionary."""
            target_lang, quality_profile = self.get_settings()
            return {
                "target_lang": target_lang,
                "quality_profile": quality_profile,
                "isometric_alignment": self.isometric_chk.isChecked(),
                "acoustic_preset": str(self.reverb_combo.currentData() or "none"),
                "broadcast_spec": str(self.qc_combo.currentData() or "netflix"),
                "embed_c2pa_provenance": self.c2pa_chk.isChecked(),
            }

    class DubbingErrorDialog(QDialog):
        """Readable operator error dialog with one-click 'Copy details'."""

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            title: str = "Dubbing Pipeline Failed",
            message: str = "",
            details: str = "",
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setModal(True)
            self.setMinimumSize(520, 360)
            self.details_text = details or message or "No details provided"

            self.setStyleSheet(
                "QDialog { background: #0D1118; color: #F7F9FC; }"
                "QLabel { color: #F7F9FC; }"
                "QPlainTextEdit {"
                "  background: #080B10; color: #E2E8F0; border: 1px solid #283446;"
                "  border-radius: 4px; font-family: 'Cascadia Mono', Consolas, monospace;"
                "  font-size: 11px; padding: 8px;"
                "}"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(14)

            # Warning Header
            hdr_layout = QHBoxLayout()
            err_icon = QLabel("⚠️", self)
            err_icon.setStyleSheet("font-size: 24px;")
            hdr_layout.addWidget(err_icon)

            hdr_text = QVBoxLayout()
            self.title_lbl = QLabel(title, self)
            self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #EF4444;")
            self.msg_lbl = QLabel(message or "An unexpected pipeline error occurred.", self)
            self.msg_lbl.setWordWrap(True)
            self.msg_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")
            hdr_text.addWidget(self.title_lbl)
            hdr_text.addWidget(self.msg_lbl)
            hdr_layout.addLayout(hdr_text)
            hdr_layout.addStretch()
            layout.addLayout(hdr_layout)

            # Technical Details Box
            det_title = QLabel("Technical Details / Error Trace:", self)
            det_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #8C9BAE;")
            layout.addWidget(det_title)

            self.details_edit = QPlainTextEdit(self)
            self.details_edit.setPlainText(self.details_text)
            self.details_edit.setReadOnly(True)
            layout.addWidget(self.details_edit, stretch=1)

            # Button Row
            btn_row = QHBoxLayout()
            self.copy_btn = QPushButton("Copy details", self)
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1C2431; color: #38BDF8; border: 1px solid #283446;"
                "  border-radius: 4px; padding: 7px 16px; font-weight: 700;"
                "}"
                "QPushButton:hover { background: #283446; color: #7DD3FC; }"
            )
            self.copy_btn.clicked.connect(self._copy_details)
            btn_row.addWidget(self.copy_btn)

            btn_row.addStretch()

            close_btn = QPushButton("Close", self)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton {"
                "  background: #2563EB; color: #FFF; border: none;"
                "  border-radius: 4px; padding: 7px 20px; font-weight: 700;"
                "}"
                "QPushButton:hover { background: #3B82F6; }"
            )
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)

            layout.addLayout(btn_row)

        def _copy_details(self) -> None:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self.details_text)
            self.copy_btn.setText("✓ Copied details")
            self.copy_btn.setStyleSheet(
                "QPushButton {"
                "  background: #064E3B; color: #34D399; border: 1px solid #059669;"
                "  border-radius: 4px; padding: 7px 16px; font-weight: 700;"
                "}"
            )
