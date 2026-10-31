"""
Voice Exchanger & Timbre Morphing Studio Dialog.

Features:
  - 1-Click Character Voice Swapping across single clips, characters, or entire projects.
  - Dual-Voice Timbre Morphing & Blending (creates unique movie character voices).
  - Formant Manipulation (+/- 500 cents) and Pitch Shifting (+/- 12 semitones).
  - Curated neural voice library spanning Bengali, English, Hindi, and custom RVC models.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.application.voice.voice_exchanger_service import (
    CURATED_VOICE_LIBRARY,
    VoiceExchangerService,
    VoiceProfileInfo,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QSlider,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class VoiceExchangerDialog(QDialog):
        """Interactive voice exchanger and timbre morphing studio."""

        voice_exchanged = Signal(dict)  # emits exchange instruction

        def __init__(
            self,
            character_name: str = "Character",
            current_voice_id: str = "bn-BD-PradeepNeural",
            target_language: str = "bn",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Voice Exchanger & Timbre Morphing Studio")
            self.setMinimumSize(920, 640)
            self.resize(1020, 700)
            self.setStyleSheet(
                "QDialog { background: #0B0E14; color: #F8FAFC; }"
                "QGroupBox { font-size: 11px; font-weight: 700; color: #94A3B8; border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px; padding-top: 14px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
                "QTableWidget { background: #0E131E; border: 1px solid #1E293B; border-radius: 6px; gridline-color: #1A2333; color: #F1F5F9; font-size: 11px; }"
                "QHeaderView::section { background: #141B2A; color: #94A3B8; font-weight: 700; font-size: 10px; border: none; padding: 6px; }"
                "QSlider::groove:horizontal { height: 6px; background: #1E293B; border-radius: 3px; }"
                "QSlider::sub-page:horizontal { background: #38BDF8; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #0284C7; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
                "QPushButton { background: #162030; color: #E2E8F0; border: 1px solid #233045; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #202B40; color: #FFF; border-color: #38BDF8; }"
                "QTabWidget::pane { border: 1px solid #1E293B; border-radius: 8px; background: #0F131D; }"
                "QTabBar::tab { background: #141A26; color: #94A3B8; padding: 8px 18px; font-weight: 700; font-size: 11px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }"
                "QTabBar::tab:selected { background: #0284C7; color: #FFF; }"
            )

            self.character_name = character_name
            self.current_voice_id = current_voice_id
            self.target_language = target_language
            self._service = VoiceExchangerService()
            self._selected_voice: VoiceProfileInfo | None = self._service.get_voice(current_voice_id)

            self._init_ui()
            self._populate_voice_table()

        def _init_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            title_col = QVBoxLayout()
            t_lbl = QLabel("🔄 VOICE EXCHANGER & TIMBRE MORPHING", self)
            t_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #F8FAFC;")
            s_lbl = QLabel(
                f"Active Character: {self.character_name} · Current Voice: {self.current_voice_id}",
                self,
            )
            s_lbl.setStyleSheet("font-size: 11px; color: #38BDF8; font-weight: 700;")
            title_col.addWidget(t_lbl)
            title_col.addWidget(s_lbl)
            header.addLayout(title_col, 1)

            root.addLayout(header)

            # Tabs: Tab 1 = Voice Library Swapper, Tab 2 = Timbre Morphing & Pitch
            self.tabs = QTabWidget(self)

            # Tab 1: Library
            tab_lib = QWidget()
            lib_lay = QVBoxLayout(tab_lib)
            lib_lay.setContentsMargins(14, 12, 14, 12)

            # Filter Bar
            filt_bar = QHBoxLayout()
            filt_bar.addWidget(QLabel("Language:", tab_lib))
            self.lang_combo = QComboBox(tab_lib)
            self.lang_combo.addItems(["All", "Bengali (bn)", "English (en)", "Hindi (hi)"])
            if self.target_language.startswith("bn"):
                self.lang_combo.setCurrentIndex(1)
            elif self.target_language.startswith("en"):
                self.lang_combo.setCurrentIndex(2)
            self.lang_combo.currentIndexChanged.connect(self._populate_voice_table)
            filt_bar.addWidget(self.lang_combo)

            filt_bar.addWidget(QLabel("Gender:", tab_lib))
            self.gender_combo = QComboBox(tab_lib)
            self.gender_combo.addItems(["All", "Male", "Female"])
            self.gender_combo.currentIndexChanged.connect(self._populate_voice_table)
            filt_bar.addWidget(self.gender_combo)

            filt_bar.addStretch()
            lib_lay.addLayout(filt_bar)

            # Voice Table
            self.voice_table = QTableWidget(tab_lib)
            self.voice_table.setColumnCount(5)
            self.voice_table.setHorizontalHeaderLabels(["Name / Actor", "Engine", "Gender", "Category", "Voice ID"])
            self.voice_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.voice_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.voice_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.voice_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.voice_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.voice_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.voice_table.itemSelectionChanged.connect(self._on_voice_selected)
            lib_lay.addWidget(self.voice_table, 1)

            self.tabs.addTab(tab_lib, "🎙️ Neural Voice Library")

            # Tab 2: Morphing & Formant Modifiers
            tab_morph = QWidget()
            morph_lay = QGridLayout(tab_morph)
            morph_lay.setContentsMargins(16, 14, 16, 14)
            morph_lay.setSpacing(14)

            morph_lay.addWidget(QLabel("Dual-Voice Timbre Morphing Blend:", tab_morph), 0, 0)
            self.morph_slider = QSlider(Qt.Orientation.Horizontal, tab_morph)
            self.morph_slider.setRange(0, 100)
            self.morph_slider.setValue(0)
            morph_lay.addWidget(self.morph_slider, 0, 1)
            self.morph_val_lbl = QLabel("100% Primary Voice", tab_morph)
            morph_lay.addWidget(self.morph_val_lbl, 0, 2)
            self.morph_slider.valueChanged.connect(
                lambda v: self.morph_val_lbl.setText(f"{100 - v}% Voice A / {v}% Voice B")
            )

            morph_lay.addWidget(QLabel("Formant Shift (-500 to +500 cents):", tab_morph), 1, 0)
            self.formant_slider = QSlider(Qt.Orientation.Horizontal, tab_morph)
            self.formant_slider.setRange(-500, 500)
            self.formant_slider.setValue(0)
            morph_lay.addWidget(self.formant_slider, 1, 1)
            self.formant_val_lbl = QLabel("0 cents (Natural)", tab_morph)
            morph_lay.addWidget(self.formant_val_lbl, 1, 2)
            self.formant_slider.valueChanged.connect(
                lambda v: self.formant_val_lbl.setText(
                    f"{v:+} cents ({'Younger/Brighter' if v > 0 else 'Deeper/Chest' if v < 0 else 'Natural'})"
                )
            )

            morph_lay.addWidget(QLabel("Pitch Shift (-12 to +12 semitones):", tab_morph), 2, 0)
            self.pitch_slider = QSlider(Qt.Orientation.Horizontal, tab_morph)
            self.pitch_slider.setRange(-12, 12)
            self.pitch_slider.setValue(0)
            morph_lay.addWidget(self.pitch_slider, 2, 1)
            self.pitch_val_lbl = QLabel("0 semitones", tab_morph)
            morph_lay.addWidget(self.pitch_val_lbl, 2, 2)
            self.pitch_slider.valueChanged.connect(
                lambda v: self.pitch_val_lbl.setText(f"{v:+} semitones")
            )

            self.tabs.addTab(tab_morph, "🎛️ Timbre Morph & Formant Shifter")
            root.addWidget(self.tabs, 1)

            # Application Scope Selector
            grp_scope = QGroupBox("Exchange Application Scope", self)
            scope_lay = QHBoxLayout(grp_scope)
            self.rad_single = QRadioButton("Current Selected Clip Only", grp_scope)
            self.rad_char = QRadioButton(f"All Clips Assigned to '{self.character_name}'", grp_scope)
            self.rad_char.setChecked(True)
            self.rad_all = QRadioButton("Entire Project (All Characters)", grp_scope)

            scope_lay.addWidget(self.rad_single)
            scope_lay.addWidget(self.rad_char)
            scope_lay.addWidget(self.rad_all)
            scope_lay.addStretch()
            root.addWidget(grp_scope)

            # Bottom Action Bar
            bot = QHBoxLayout()
            self.audition_btn = QPushButton("▶ Audition Sample", self)
            self.audition_btn.clicked.connect(self._audition_voice)
            bot.addWidget(self.audition_btn)

            bot.addStretch()

            apply_btn = QPushButton("✓ Apply Voice Exchange", self)
            apply_btn.setStyleSheet("background: #0284C7; color: #FFF; font-weight: 800; padding: 8px 24px;")
            apply_btn.clicked.connect(self._apply_exchange)
            bot.addWidget(apply_btn)

            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.clicked.connect(self.reject)
            bot.addWidget(cancel_btn)

            root.addLayout(bot)

        def _populate_voice_table(self) -> None:
            lang_idx = self.lang_combo.currentIndex()
            lang_code = None
            if lang_idx == 1:
                lang_code = "bn"
            elif lang_idx == 2:
                lang_code = "en"
            elif lang_idx == 3:
                lang_code = "hi"

            gender_idx = self.gender_combo.currentIndex()
            gender_filter = None
            if gender_idx == 1:
                gender_filter = "male"
            elif gender_idx == 2:
                gender_filter = "female"

            voices = self._service.list_voices(language=lang_code, gender=gender_filter)
            self.voice_table.setRowCount(len(voices))

            for r, v in enumerate(voices):
                self.voice_table.setItem(r, 0, QTableWidgetItem(v.display_name))
                self.voice_table.setItem(r, 1, QTableWidgetItem(v.engine.upper()))
                self.voice_table.setItem(r, 2, QTableWidgetItem(v.gender.capitalize()))
                self.voice_table.setItem(r, 3, QTableWidgetItem(v.age_category.capitalize()))
                self.voice_table.setItem(r, 4, QTableWidgetItem(v.voice_id))

                if v.voice_id == self.current_voice_id:
                    self.voice_table.selectRow(r)

        def _on_voice_selected(self) -> None:
            row = self.voice_table.currentRow()
            if row >= 0:
                item = self.voice_table.item(row, 4)
                if item:
                    vid = item.text()
                    self._selected_voice = self._service.get_voice(vid)

        def _audition_voice(self) -> None:
            if not self._selected_voice:
                return

            if hasattr(self, "_audition") and self._audition.is_playing:
                self._audition.stop()
                self.audition_btn.setText("▶ Audition Sample")
                return

            if not hasattr(self, "_audition"):
                from aidub.media.audition_service import AuditionService
                self._audition = AuditionService(self)
                self._audition.playback_stopped.connect(
                    lambda: self.audition_btn.setText("▶ Audition Sample")
                )

            self.audition_btn.setText("⏹ Stop Audition")
            pitch_semis = self.pitch_slider.value()
            pitch_hz = f"{pitch_semis * 12:+}Hz" if pitch_semis != 0 else "+0Hz"
            
            # Context-sensitive preview line according to language
            lang = self._selected_voice.language.lower()
            if lang.startswith("bn"):
                sample_text = "আমি আপনার সাথে একমত, সিনেমা ডাবিং এখন সম্পূর্ণ নিখুঁত।"
            elif lang.startswith("hi"):
                sample_text = "मैं आपके साथ सहमत हूँ, यह आवाज़ सिनेमा के लिए एकदम सही है।"
            else:
                sample_text = "This is a real-time character voice audition for the movie dialogue."

            self._audition.synthesize_and_play(
                text=sample_text,
                voice_id=self._selected_voice.voice_id,
                pitch=pitch_hz,
            )

        def _apply_exchange(self) -> None:
            if not self._selected_voice:
                QMessageBox.warning(self, "No Voice Selected", "Please select a target voice from the library.")
                return

            scope = "character"
            if self.rad_single.isChecked():
                scope = "single"
            elif self.rad_all.isChecked():
                scope = "all"

            result = {
                "character_name": self.character_name,
                "new_voice_id": self._selected_voice.voice_id,
                "voice_display_name": self._selected_voice.display_name,
                "scope": scope,
                "formant_cents": self.formant_slider.value(),
                "pitch_semitones": self.pitch_slider.value(),
                "morph_blend_ratio": self.morph_slider.value() / 100.0,
            }
            self.voice_exchanged.emit(result)
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            self.accept()

        def reject(self) -> None:
            if hasattr(self, "_audition"):
                self._audition.cleanup()
            super().reject()


__all__ = ["VoiceExchangerDialog"]
