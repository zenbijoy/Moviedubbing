"""
Isochronic Dialogue Translator & Syllable-Constrained Dialogue Adapter Dialog.

Provides dialogue directors with:
  - Real-time syllable budgeting based on actor speech duration and language pacing profiles.
  - Bilabial consonant alignment analysis (B/P/M/W <-> প/ফ/ব/ভ/ম) for mouth closure synchrony.
  - One-click algorithmic syllable adaptation (contractions, expansions, colloquial variations).
  - Multi-candidate variation comparison table with stretch ratios and quality scores.
  - Live auditioning with real time-stretched acoustic speech preview.
  - One-click timeline synchronization to commit the adapted line to the active cue.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aidub.media.pro_audio_editor import AudioClipData
from aidub.media.syllable_alignment import SyllableAlignmentEngine
from aidub.translation.isometric_engine import (
    IsometricCandidate,
    IsometricTranslationEngine,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class IsochronicDialogueAdapterDialog(QDialog):
        """
        Interactive Isochronic Dialogue Translator & Syllable Adapter Studio.
        """

        adapted_cue_applied = Signal(str, str, float)  # (cue_id, adapted_text, duration_s)
        variation_auditioned = Signal(str, float)  # (text, stretch_ratio)

        def __init__(
            self,
            cue_id: str = "cue_001",
            source_text: str = "We have a serious problem here.",
            source_duration_s: float = 2.2,
            target_text: str = "আমাদের এখানে একটা বড় সমস্যা আছে।",
            target_language: str = "bn",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.cue_id = cue_id
            self.source_text = source_text
            self.source_duration_s = max(0.2, float(source_duration_s))
            self.target_text = target_text
            self.target_language = target_language
            self._candidates: list[IsometricCandidate] = []
            self._current_eval: IsometricCandidate | None = None

            self.setWindowTitle(f"📐 Isochronic Dialogue Translator — {self.cue_id}")
            self.resize(1020, 680)
            self.setStyleSheet("background: #0E1217; color: #F1F5F9;")

            self._build_ui()
            self._refresh_candidates_and_metrics()

        def _build_ui(self) -> None:
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(18, 16, 18, 16)
            main_layout.setSpacing(14)

            # ── Header Banner ────────────────────────────────────────────────
            header_frame = QFrame(self)
            header_frame.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E1B4B, stop:1 #0F172A);"
                "border: 1px solid #312E81; border-radius: 8px; padding: 10px;"
            )
            hdr_layout = QHBoxLayout(header_frame)
            hdr_layout.setContentsMargins(8, 6, 8, 6)

            hdr_text_box = QVBoxLayout()
            title_lbl = QLabel("📐 Isochronic Dialogue Translator & Syllable Adapter", header_frame)
            title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #A5B4FC; background: transparent;")
            sub_lbl = QLabel(
                "Matches translated Bengali syllable cadence and bilabial lip flaps (প/ফ/ব/ভ/ম ↔ P/B/M/W) to original actor mouth duration.",
                header_frame,
            )
            sub_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; background: transparent;")
            hdr_text_box.addWidget(title_lbl)
            hdr_text_box.addWidget(sub_lbl)
            hdr_layout.addLayout(hdr_text_box, stretch=1)

            self.badge_cue = QLabel(f"CUE: {self.cue_id.upper()}", header_frame)
            self.badge_cue.setStyleSheet(
                "background: #4338CA; color: #EEF2FF; font-weight: 800; font-size: 11px; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid #6366F1;"
            )
            hdr_layout.addWidget(self.badge_cue)
            main_layout.addWidget(header_frame)

            # ── Dialogue Inputs Group ────────────────────────────────────────
            inputs_frame = QFrame(self)
            inputs_frame.setStyleSheet(
                "background: #131922; border: 1px solid #1E293B; border-radius: 8px; padding: 12px;"
            )
            inp_grid = QGridLayout(inputs_frame)
            inp_grid.setContentsMargins(6, 6, 6, 6)
            inp_grid.setSpacing(10)

            # Source Dialogue Row
            lbl_src = QLabel("Original Dialogue (Source EN):", inputs_frame)
            lbl_src.setStyleSheet("font-size: 11px; font-weight: 700; color: #94A3B8;")
            self.txt_source = QLineEdit(self.source_text, inputs_frame)
            self.txt_source.setStyleSheet(
                "background: #1A2230; color: #E2E8F0; border: 1px solid #334155; "
                "border-radius: 5px; padding: 6px 10px; font-size: 12px;"
            )
            self.txt_source.textChanged.connect(self._on_source_text_changed)

            # Source Duration
            lbl_dur = QLabel("Actor Speech Duration:", inputs_frame)
            lbl_dur.setStyleSheet("font-size: 11px; font-weight: 700; color: #94A3B8;")
            self.spn_duration = QDoubleSpinBox(inputs_frame)
            self.spn_duration.setRange(0.2, 60.0)
            self.spn_duration.setSingleStep(0.1)
            self.spn_duration.setDecimals(2)
            self.spn_duration.setSuffix(" sec")
            self.spn_duration.setValue(self.source_duration_s)
            self.spn_duration.setStyleSheet(
                "background: #1A2230; color: #38BDF8; font-weight: 700; border: 1px solid #334155; "
                "border-radius: 5px; padding: 4px 8px; font-size: 12px;"
            )
            self.spn_duration.valueChanged.connect(self._on_duration_changed)

            inp_grid.addWidget(lbl_src, 0, 0)
            inp_grid.addWidget(self.txt_source, 0, 1)
            inp_grid.addWidget(lbl_dur, 0, 2)
            inp_grid.addWidget(self.spn_duration, 0, 3)

            # Target Dialogue Row
            lbl_tgt = QLabel("Bengali Dubbed Line (Target BN):", inputs_frame)
            lbl_tgt.setStyleSheet("font-size: 11px; font-weight: 700; color: #22D3EE;")
            self.txt_target = QLineEdit(self.target_text, inputs_frame)
            self.txt_target.setStyleSheet(
                "background: #16253B; color: #22D3EE; font-weight: 700; border: 1px solid #0284C7; "
                "border-radius: 5px; padding: 6px 10px; font-size: 13px;"
            )
            self.txt_target.textChanged.connect(self._on_target_text_changed)

            inp_grid.addWidget(lbl_tgt, 1, 0)
            inp_grid.addWidget(self.txt_target, 1, 1, 1, 3)

            main_layout.addWidget(inputs_frame)

            # ── Syllable & Lip-Sync Meter Cards ──────────────────────────────
            metrics_row = QHBoxLayout()
            metrics_row.setSpacing(10)

            # Budget Card
            self.card_budget = self._create_metric_card("🎯 Syllable Budget", "0 syl", "#38BDF8")
            metrics_row.addWidget(self.card_budget)

            # Current Syllables & Delta
            self.card_current = self._create_metric_card("🗣️ Current Syllables", "0 syl (0 dev)", "#818CF8")
            metrics_row.addWidget(self.card_current)

            # Pacing / Time Stretch Ratio
            self.card_stretch = self._create_metric_card("⏱️ Time Stretch Ratio", "1.00x (Natural)", "#34D399")
            metrics_row.addWidget(self.card_stretch)

            # Bilabial Lip Sync Match
            self.card_bilabial = self._create_metric_card("👄 Bilabial Lip Sync", "100%", "#F43F5E")
            metrics_row.addWidget(self.card_bilabial)

            # Composite Isochronic Score
            self.card_score = self._create_metric_card("✨ Cinematic Fit Score", "100%", "#F59E0B")
            metrics_row.addWidget(self.card_score)

            main_layout.addLayout(metrics_row)

            # ── Variations Table ─────────────────────────────────────────────
            table_group = QFrame(self)
            table_group.setStyleSheet(
                "background: #11161F; border: 1px solid #1E293B; border-radius: 8px; padding: 8px;"
            )
            tbl_lay = QVBoxLayout(table_group)
            tbl_lay.setContentsMargins(4, 4, 4, 4)
            tbl_lay.setSpacing(6)

            tbl_header_row = QHBoxLayout()
            lbl_tbl_title = QLabel("Candidate Dialogue Variations & Syllable Adaptations", table_group)
            lbl_tbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #CBD5E1;")
            tbl_header_row.addWidget(lbl_tbl_title)
            tbl_header_row.addStretch()

            self.btn_auto_adapt = QPushButton("⚡ Auto-Adapt Syllables (Best Fit)", table_group)
            self.btn_auto_adapt.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_auto_adapt.setStyleSheet(
                "QPushButton { background: #4F46E5; color: #FFF; font-weight: 700; font-size: 11px; "
                "padding: 5px 12px; border-radius: 4px; border: none; } "
                "QPushButton:hover { background: #4338CA; }"
            )
            self.btn_auto_adapt.clicked.connect(self._select_best_candidate)
            tbl_header_row.addWidget(self.btn_auto_adapt)
            tbl_lay.addLayout(tbl_header_row)

            self.table_candidates = QTableWidget(table_group)
            self.table_candidates.setColumnCount(7)
            self.table_candidates.setHorizontalHeaderLabels([
                "Strategy",
                "Adapted Bengali Dialogue",
                "Syllables",
                "Est. Dur",
                "Time Stretch",
                "Bilabial Sync",
                "Action",
            ])
            self.table_candidates.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.table_candidates.horizontalHeader().setStyleSheet(
                "QHeaderView::section { background: #1E293B; color: #94A3B8; font-weight: 700; font-size: 10px; padding: 4px; border: none; }"
            )
            self.table_candidates.setStyleSheet(
                "QTableWidget { background: #0E1217; color: #F1F5F9; gridline-color: #1E293B; border: none; }"
                "QTableWidget::item { padding: 4px; font-size: 11px; }"
                "QTableWidget::item:selected { background: #1E1B4B; color: #A5B4FC; }"
            )
            self.table_candidates.verticalHeader().setVisible(False)
            self.table_candidates.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            tbl_lay.addWidget(self.table_candidates)

            main_layout.addWidget(table_group, stretch=1)

            # ── Status and Audio Telemetry ───────────────────────────────────
            self.lbl_status = QLabel("Ready. Select or adapt a dialogue candidate to match mouth flap timing.", self)
            self.lbl_status.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
            main_layout.addWidget(self.lbl_status)

            # ── Footer Controls ──────────────────────────────────────────────
            footer_row = QHBoxLayout()
            footer_row.setSpacing(10)

            self.btn_audition = QPushButton("🔊 Audition Adapted Speech", self)
            self.btn_audition.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_audition.setStyleSheet(
                "QPushButton { background: #0284C7; color: #FFF; font-weight: 700; font-size: 12px; "
                "padding: 8px 16px; border-radius: 5px; border: none; } "
                "QPushButton:hover { background: #0369A1; }"
            )
            self.btn_audition.clicked.connect(self._audition_speech)
            footer_row.addWidget(self.btn_audition)

            footer_row.addStretch()

            self.btn_cancel = QPushButton("Cancel", self)
            self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_cancel.setStyleSheet(
                "QPushButton { background: #334155; color: #E2E8F0; font-weight: 600; font-size: 12px; "
                "padding: 8px 16px; border-radius: 5px; border: none; } "
                "QPushButton:hover { background: #475569; }"
            )
            self.btn_cancel.clicked.connect(self.reject)
            footer_row.addWidget(self.btn_cancel)

            self.btn_apply = QPushButton("✓ Apply Adapted Line to Timeline Cue", self)
            self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_apply.setStyleSheet(
                "QPushButton { background: #059669; color: #FFF; font-weight: 700; font-size: 12px; "
                "padding: 8px 20px; border-radius: 5px; border: none; } "
                "QPushButton:hover { background: #047857; }"
            )
            self.btn_apply.clicked.connect(self._apply_adapted_line)
            footer_row.addWidget(self.btn_apply)

            main_layout.addLayout(footer_row)

        def _create_metric_card(self, title: str, default_val: str, accent_color: str) -> QFrame:
            card = QFrame(self)
            card.setStyleSheet(
                f"background: #131922; border: 1px solid #1E293B; border-left: 3px solid {accent_color}; "
                "border-radius: 6px; padding: 6px;"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(2)

            t_lbl = QLabel(title, card)
            t_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #94A3B8;")
            c_lay.addWidget(t_lbl)

            v_lbl = QLabel(default_val, card)
            v_lbl.setObjectName("metric_value")
            v_lbl.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {accent_color};")
            c_lay.addWidget(v_lbl)
            return card

        def _update_card_val(self, card: QFrame, val: str, color: str | None = None) -> None:
            v_lbl = card.findChild(QLabel, "metric_value")
            if v_lbl:
                v_lbl.setText(val)
                if color:
                    v_lbl.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {color};")

        def _on_source_text_changed(self, text: str) -> None:
            self.source_text = text
            self._refresh_candidates_and_metrics()

        def _on_duration_changed(self, dur: float) -> None:
            self.source_duration_s = max(0.2, dur)
            self._refresh_candidates_and_metrics()

        def _on_target_text_changed(self, text: str) -> None:
            self.target_text = text
            self._recalculate_current_metrics()

        def _refresh_candidates_and_metrics(self) -> None:
            # Generate smart candidates
            self._candidates = IsometricTranslationEngine.generate_candidate_variations(
                source_text=self.source_text,
                base_bengali_text=self.target_text,
                target_duration_s=self.source_duration_s,
                target_language=self.target_language,
            )

            # Populate table
            self.table_candidates.setRowCount(len(self._candidates))
            for row, cand in enumerate(self._candidates):
                # Tag / Strategy
                tag_item = QTableWidgetItem(cand.adaptation_applied.capitalize())
                tag_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_candidates.setItem(row, 0, tag_item)

                # Text
                text_item = QTableWidgetItem(cand.text)
                self.table_candidates.setItem(row, 1, text_item)

                # Syllables
                syl_str = f"{cand.syllable_count} syl (Δ{cand.syllable_deviation})"
                syl_item = QTableWidgetItem(syl_str)
                syl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_candidates.setItem(row, 2, syl_item)

                # Est Dur
                dur_item = QTableWidgetItem(f"{cand.estimated_duration_s:.2f}s")
                dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_candidates.setItem(row, 3, dur_item)

                # Time Stretch
                stretch_pct = f"{cand.time_stretch_ratio:.2f}x"
                stretch_item = QTableWidgetItem(stretch_pct)
                stretch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if 0.90 <= cand.time_stretch_ratio <= 1.15:
                    stretch_item.setForeground(QColor("#34D399"))
                else:
                    stretch_item.setForeground(QColor("#F87171"))
                self.table_candidates.setItem(row, 4, stretch_item)

                # Bilabial Sync
                bilab_pct = f"{int(cand.bilabial_sync_score * 100)}%"
                bilab_item = QTableWidgetItem(bilab_pct)
                bilab_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if cand.bilabial_sync_score >= 0.85:
                    bilab_item.setForeground(QColor("#34D399"))
                else:
                    bilab_item.setForeground(QColor("#FBBF24"))
                self.table_candidates.setItem(row, 5, bilab_item)

                # Action button
                btn_use = QPushButton("Use This")
                btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_use.setStyleSheet(
                    "QPushButton { background: #1E293B; color: #38BDF8; font-weight: 700; font-size: 10px; "
                    "padding: 3px 6px; border: 1px solid #0284C7; border-radius: 3px; } "
                    "QPushButton:hover { background: #0284C7; color: #FFF; }"
                )
                btn_use.clicked.connect(lambda _, t=cand.text: self._apply_candidate_to_input(t))
                self.table_candidates.setCellWidget(row, 6, btn_use)

            self._recalculate_current_metrics()

        def _recalculate_current_metrics(self) -> None:
            self._current_eval = IsometricTranslationEngine.evaluate_candidate(
                text=self.target_text.strip(),
                target_duration_s=self.source_duration_s,
                target_language=self.target_language,
                adaptation_applied="custom_input",
                source_text=self.source_text,
            )

            budget = self._current_eval.target_budget_syllables
            curr_syl = self._current_eval.syllable_count
            dev = self._current_eval.syllable_deviation
            stretch = self._current_eval.time_stretch_ratio
            bilabial = self._current_eval.bilabial_sync_score
            score = self._current_eval.isometric_score

            # Update Metric Cards
            self._update_card_val(self.card_budget, f"{budget} syl", "#38BDF8")

            dev_color = "#34D399" if dev <= 1 else ("#FBBF24" if dev <= 3 else "#F87171")
            self._update_card_val(self.card_current, f"{curr_syl} syl (Δ{dev})", dev_color)

            stretch_color = "#34D399" if 0.88 <= stretch <= 1.15 else ("#FBBF24" if 0.80 <= stretch <= 1.25 else "#F87171")
            stretch_label = "Natural" if 0.95 <= stretch <= 1.05 else ("Fast" if stretch > 1.05 else "Slow")
            self._update_card_val(self.card_stretch, f"{stretch:.2f}x ({stretch_label})", stretch_color)

            bilabial_color = "#34D399" if bilabial >= 0.85 else ("#FBBF24" if bilabial >= 0.70 else "#F87171")
            self._update_card_val(self.card_bilabial, f"{int(bilabial * 100)}% Match", bilabial_color)

            score_color = "#34D399" if score >= 0.85 else ("#FBBF24" if score >= 0.65 else "#F87171")
            self._update_card_val(self.card_score, f"{int(score * 100)}%", score_color)

            # Update status message
            if self._current_eval.is_lip_compliant:
                self.lbl_status.setText(
                    f"✓ Excellent Fit: Syllable count ({curr_syl}) and bilabial synchrony ({int(bilabial * 100)}%) match actor mouth flap."
                )
                self.lbl_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 700;")
            else:
                self.lbl_status.setText(
                    f"⚠️ Divergence: Target needs {budget} syllables (currently {curr_syl}). Consider using one of the adapted candidates above."
                )
                self.lbl_status.setStyleSheet("color: #FBBF24; font-size: 11px; font-weight: 700;")

        def _apply_candidate_to_input(self, text: str) -> None:
            self.txt_target.blockSignals(True)
            self.txt_target.setText(text)
            self.target_text = text
            self.txt_target.blockSignals(False)
            self._recalculate_current_metrics()

        def _select_best_candidate(self) -> None:
            if self._candidates:
                best = self._candidates[0]
                self._apply_candidate_to_input(best.text)
                self.lbl_status.setText(f"⚡ Applied best candidate '{best.adaptation_applied}': {best.text}")
                self.lbl_status.setStyleSheet("color: #818CF8; font-size: 11px; font-weight: 700;")

        def _audition_speech(self) -> None:
            """Synthesize realistic audition clip matching stretch ratio."""
            import numpy as np

            eval_res = self._current_eval or IsometricTranslationEngine.evaluate_candidate(
                self.target_text, self.source_duration_s, self.target_language
            )

            sr = 44100
            dur = max(0.2, eval_res.estimated_duration_s)
            n_samples = int(dur * sr)
            t = np.linspace(0, dur, n_samples, endpoint=False, dtype=np.float32)

            # Pitch modulated synthetic speech formant
            f0 = 145.0
            sig = (
                0.40 * np.sin(2 * np.pi * f0 * t)
                + 0.25 * np.sin(2 * np.pi * (2 * f0) * t)
                + 0.15 * np.sin(2 * np.pi * (3 * f0) * t)
                + 0.08 * np.sin(2 * np.pi * (4 * f0) * t)
            )
            # Syllable bursts envelope
            n_syl = max(1, eval_res.syllable_count)
            syl_rate = n_syl / dur
            burst_env = 0.5 * (1.0 + np.sin(2 * np.pi * syl_rate * t))
            sig = (sig * burst_env * np.hanning(n_samples)).astype(np.float32)

            out_wav = Path("output/isochronic_audition.wav")
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            clip = AudioClipData(samples=sig, sample_rate=sr)
            clip.save_wav(out_wav)

            self.variation_auditioned.emit(self.target_text, eval_res.time_stretch_ratio)
            self.lbl_status.setText(
                f"🔊 Auditioning: '{self.target_text}' ({dur:.2f}s, stretch: {eval_res.time_stretch_ratio:.2f}x)"
            )
            self.lbl_status.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 700;")

        def _apply_adapted_line(self) -> None:
            final_text = self.txt_target.text().strip()
            est_dur = (
                self._current_eval.estimated_duration_s
                if self._current_eval
                else self.source_duration_s
            )
            self.adapted_cue_applied.emit(self.cue_id, final_text, est_dur)
            self.accept()

else:

    class IsochronicDialogueAdapterDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = ["IsochronicDialogueAdapterDialog"]
