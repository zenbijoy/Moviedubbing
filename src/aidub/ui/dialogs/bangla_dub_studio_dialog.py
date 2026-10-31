"""
Bangla Dubbing & G2P Lip-Sync Studio Dialog.

Comprehensive Bengali Dubbing Suite:
  - Regional Dialect Presets (Dhaka, Chittagong, Sylhet, Barisal, Sadhu).
  - Bengali G2P (Grapheme-to-Phoneme) with 15-class Disney Viseme timeline.
  - Emotion Classifier with 3D PAD vectors & Hollywood SSML emotion tags.
  - Subtitle QC Auditor for broadcast reading speed (CPS), line limits, & Dari punctuation.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.application.bangla.dialect_presets import BanglaDialectManager
from aidub.application.bangla.emotion_classifier import BanglaEmotionClassifier
from aidub.application.bangla.g2p import BanglaG2P
from aidub.application.bangla.subtitle_qc import BanglaSubtitleQC

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class BanglaDubStudioDialog(QDialog):
        """Interactive studio for Bengali dialects, G2P visemes, emotions, and subtitle QC."""

        bangla_dub_applied = Signal(dict)

        def __init__(
            self,
            text: str = "আমি তোমাকে অনেক ভালোবাসি, কিন্তু তুমি আমাকে বুঝলে না।",
            cue_id: str = "cue_001",
            duration_sec: float = 3.2,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle(f"🇧🇩 Bangla Dubbing Studio & G2P Lip-Sync — {cue_id}")
            self.resize(780, 560)
            self.setStyleSheet(
                "QDialog { background-color: #0A0F1D; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; }"
                "QGroupBox { border: 1px solid #1E293B; border-radius: 6px; margin-top: 8px; font-weight: 700; color: #38BDF8; padding-top: 10px; }"
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
                "QLabel { color: #E2E8F0; font-size: 11px; }"
                "QLineEdit, QTextEdit { background: #111827; color: #F8FAFC; border: 1px solid #334155; border-radius: 4px; padding: 6px; }"
                "QComboBox { background: #111827; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-weight: 600; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
            )

            self.cue_id = cue_id
            self.duration_sec = duration_sec
            self.dialect_mgr = BanglaDialectManager()
            self.emotion_clf = BanglaEmotionClassifier()
            self.sub_qc = BanglaSubtitleQC()
            self.g2p = BanglaG2P()

            layout = QVBoxLayout(self)
            layout.setSpacing(10)

            # Dialogue Input Row
            input_box = QGroupBox("Bengali Dialogue Line")
            i_lay = QVBoxLayout(input_box)
            self.txt_dialogue = QLineEdit(text)
            self.txt_dialogue.textChanged.connect(self._recalculate_all)
            i_lay.addWidget(self.txt_dialogue)
            layout.addWidget(input_box)

            # Top 2-Column: Dialect + Emotion
            mid_row = QHBoxLayout()

            # Dialect Box
            dial_box = QGroupBox("Regional Dialect Preset")
            d_lay = QGridLayout(dial_box)
            d_lay.addWidget(QLabel("Dialect:"), 0, 0)
            self.combo_dialect = QComboBox()
            for key, name in [
                ("dhaka_standard", "ঢাকা প্রমিত (Dhaka Standard)"),
                ("chittagong", "চট্টগ্রাম চাটগাঁইয়া (Chittagong)"),
                ("sylhet", "সিলেটি নাগরি (Sylhet)"),
                ("barisal", "বরিশালীয় (Barisal)"),
                ("classic_sadhu", "ঐতিহাসিক সাধু ভাষা (Sadhu Bhasha)"),
            ]:
                self.combo_dialect.addItem(name, key)
            self.combo_dialect.currentIndexChanged.connect(self._on_dialect_changed)
            d_lay.addWidget(self.combo_dialect, 0, 1)

            self.lbl_dial_info = QLabel("Rate: 1.0x | Pitch: +0.0st")
            self.lbl_dial_info.setStyleSheet("color: #94A3B8; font-size: 10px;")
            d_lay.addWidget(self.lbl_dial_info, 1, 0, 1, 2)

            self.txt_adapted = QLineEdit()
            self.txt_adapted.setReadOnly(True)
            self.txt_adapted.setStyleSheet("color: #34D399; font-weight: 600;")
            d_lay.addWidget(QLabel("Dialect Text:"), 2, 0)
            d_lay.addWidget(self.txt_adapted, 2, 1)
            mid_row.addWidget(dial_box)

            # Emotion Analysis Box
            emo_box = QGroupBox("Emotion & PAD Vector")
            e_lay = QGridLayout(emo_box)
            self.lbl_emo_type = QLabel("Detected: —")
            self.lbl_emo_type.setStyleSheet("font-weight: 700; color: #F59E0B;")
            e_lay.addWidget(self.lbl_emo_type, 0, 0, 1, 2)

            self.lbl_pad = QLabel("PAD: Pleasure=0.0, Arousal=0.0, Dominance=0.0")
            self.lbl_pad.setStyleSheet("color: #94A3B8; font-size: 10px;")
            e_lay.addWidget(self.lbl_pad, 1, 0, 1, 2)

            self.lbl_ssml = QLabel("SSML Style: neutral")
            self.lbl_ssml.setStyleSheet("color: #A78BFA; font-weight: 600; font-size: 11px;")
            e_lay.addWidget(self.lbl_ssml, 2, 0, 1, 2)
            mid_row.addWidget(emo_box)

            layout.addLayout(mid_row)

            # Subtitle QC Box
            qc_box = QGroupBox("Broadcast Subtitle Quality Control (QC)")
            qc_lay = QHBoxLayout(qc_box)
            self.lbl_qc_status = QLabel("QC Status: Checking...")
            self.lbl_qc_status.setStyleSheet("font-size: 11px; color: #E2E8F0;")
            qc_lay.addWidget(self.lbl_qc_status)
            qc_lay.addStretch()
            self.btn_fix_qc = QPushButton("✨ Auto-Fix Punctuation & Speed")
            self.btn_fix_qc.setStyleSheet(
                "QPushButton{background:#0369A1;color:#F0F9FF;font-weight:700;}"
                "QPushButton:hover{background:#0284C7;}"
            )
            self.btn_fix_qc.clicked.connect(self._auto_fix_qc)
            qc_lay.addWidget(self.btn_fix_qc)
            layout.addWidget(qc_box)

            # Viseme & G2P Lip-Sync Timeline Box
            vis_box = QGroupBox("Phoneme & Viseme Lip-Sync Timeline (15 Facial Shapes)")
            v_lay = QVBoxLayout(vis_box)
            self.table_visemes = QTableWidget(0, 3)
            self.table_visemes.setHorizontalHeaderLabels(["Start (s)", "End (s)", "Viseme Shape"])
            self.table_visemes.setStyleSheet("background: #090D16; gridline-color: #1E293B; font-size: 10px;")
            v_lay.addWidget(self.table_visemes)
            layout.addWidget(vis_box)

            # Bottom Action Buttons
            btn_row = QHBoxLayout()
            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            btn_row.addStretch()

            self.btn_apply = QPushButton("✓ Apply Bangla Dub & LipSync")
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #065F46; color: #ECFDF5; font-weight: 700; }"
                "QPushButton:hover { background: #059669; }"
            )
            self.btn_apply.clicked.connect(self._apply_all)
            btn_row.addWidget(self.btn_apply)
            layout.addLayout(btn_row)

            self._recalculate_all()

        def _on_dialect_changed(self) -> None:
            dial_key = self.combo_dialect.currentData()
            profile = self.dialect_mgr.get_profile(dial_key)
            self.lbl_dial_info.setText(
                f"Rate: {profile.speaking_rate_scale:.2f}x | Pitch: {profile.pitch_semitones:+.1f}st | {profile.prosody_description}"
            )
            adapted = self.dialect_mgr.adapt_text(self.txt_dialogue.text(), dial_key)
            self.txt_adapted.setText(adapted)

        def _recalculate_all(self) -> None:
            text = self.txt_dialogue.text().strip()
            if not text:
                return

            self._on_dialect_changed()

            # Emotion
            emo_res = self.emotion_clf.classify_text(text)
            self.lbl_emo_type.setText(f"Detected: {emo_res.primary_emotion.upper()} ({emo_res.confidence*100:.0f}%)")
            self.lbl_pad.setText(
                f"PAD: Pleasure={emo_res.pleasure:+.2f}, Arousal={emo_res.arousal:+.2f}, Dominance={emo_res.dominance:+.2f}"
            )
            self.lbl_ssml.setText(f"SSML Style: {emo_res.ssml_style} (intensity: {emo_res.intensity:.2f})")

            # QC
            qc_issues = self.sub_qc.check_line(text, duration_sec=self.duration_sec)
            if not qc_issues:
                self.lbl_qc_status.setText("✓ Pass: Broadcast compliant (Speed, Length, Dari punctuation).")
                self.lbl_qc_status.setStyleSheet("color: #34D399; font-weight: 700;")
                self.btn_fix_qc.setEnabled(False)
            else:
                issue_descs = "; ".join(i.message for i in qc_issues[:2])
                self.lbl_qc_status.setText(f"⚠ {len(qc_issues)} QC Warning(s): {issue_descs}")
                self.lbl_qc_status.setStyleSheet("color: #F87171; font-weight: 700;")
                self.btn_fix_qc.setEnabled(True)

            # Visemes
            timed_visemes = self.g2p.align_sentence_timing(text, total_duration_sec=self.duration_sec)
            self.table_visemes.setRowCount(len(timed_visemes))
            for row, (vis, t_start, t_end) in enumerate(timed_visemes):
                self.table_visemes.setItem(row, 0, QTableWidgetItem(f"{t_start:.3f}"))
                self.table_visemes.setItem(row, 1, QTableWidgetItem(f"{t_end:.3f}"))
                self.table_visemes.setItem(row, 2, QTableWidgetItem(vis))

        def _auto_fix_qc(self) -> None:
            text = self.txt_dialogue.text()
            fixed = self.sub_qc.auto_fix(text)
            self.txt_dialogue.setText(fixed)

        def _apply_all(self) -> None:
            dial_key = self.combo_dialect.currentData()
            profile = self.dialect_mgr.get_profile(dial_key)
            emo_res = self.emotion_clf.classify_text(self.txt_dialogue.text())
            timed_visemes = self.g2p.align_sentence_timing(self.txt_dialogue.text(), total_duration_sec=self.duration_sec)

            data = {
                "cue_id": self.cue_id,
                "bangla_text": self.txt_dialogue.text(),
                "dialect": dial_key,
                "speaking_rate_scale": profile.speaking_rate_scale,
                "pitch_semitones": profile.pitch_semitones,
                "emotion": emo_res.primary_emotion,
                "ssml_style": emo_res.ssml_style,
                "timed_visemes": timed_visemes,
            }
            self.bangla_dub_applied.emit(data)
            self.accept()
else:
    class BanglaDubStudioDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["BanglaDubStudioDialog"]
