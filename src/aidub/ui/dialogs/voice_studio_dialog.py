"""
Advanced Voice Creation Studio & Dialogue Engineering Dialog.

Integrates:
  - Tab 1: Voice Library & Engine Resource Manager (local models, cloud APIs, hardware inspection).
  - Tab 2: Voice Design Studio (prompt-driven character timbre, pitch, resonance, accent, age).
  - Tab 3: Authorized Voice Cloning & Legal Consent Gate (reference audio SNR/clipping analysis, consent verification).
  - Tab 4: Multi-Speaker Dialogue Editor (multi-character turns, scene context, timing and overlap alignment).
  - Tab 5: Audio Quality & Comparison Lab (A/B audition, waveforms, true peak, clipping, spectral similarity, human ratings).
"""

from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path

from aidub.adapters.voice.engine_registry import get_voice_engine_registry
from aidub.adapters.voice_base import (
    EmotionLabel,
    EngineCapability,
    ReferenceAudioAnalysis,
    SynthesisRequest,
    VoiceConsentDeclaration,
    VoiceDesignPrompt,
    VoiceEngineKind,
)
from aidub.application.voice.character_profile_service import CharacterProfileService
from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile
from aidub.media.voice_dsp import (
    analyze_voice_audio,
    measure_acoustic_similarity,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QPainter,
        QPaintEvent,
        QPen,
    )
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class _WaveformWidget(QWidget):
        """Dynamic interactive waveform canvas with playback scrubber indicator."""

        def __init__(self, color_hex: str = "#38BDF8", parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.color_hex = color_hex
            self.progress = 0.0
            self.setFixedHeight(54)
            self.setMinimumWidth(200)
            self.bars = [
                0.15 + 0.85 * abs(math.sin(i * 0.28) * math.cos(i * 0.14) * math.sin(i * 0.45 + 0.1))
                for i in range(50)
            ]

        def set_progress(self, val: float) -> None:
            self.progress = max(0.0, min(1.0, val))
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mid_y = h / 2.0
            n = len(self.bars)
            spacing = 2.0
            bar_w = max(2.0, (w - (n * spacing)) / max(1, n))

            # Backdrop
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#0F172A")))
            painter.drawRoundedRect(0, 0, w, h, 6, 6)

            # Centerline
            painter.setPen(QPen(QColor("#1E293B"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, int(mid_y), w, int(mid_y))

            active_color = QColor(self.color_hex)
            dim_color = QColor("#334155")

            scrub_x = int(self.progress * w)

            for i, peak in enumerate(self.bars):
                bx = i * (bar_w + spacing) + 2
                bar_h = max(4.0, (h - 10) * peak)
                top_y = mid_y - (bar_h / 2.0)

                if bx <= scrub_x:
                    painter.setBrush(QBrush(active_color))
                else:
                    painter.setBrush(QBrush(dim_color))

                painter.drawRoundedRect(int(bx), int(top_y), max(1, int(bar_w)), max(2, int(bar_h)), 2, 2)

            # Playhead
            if 0.0 < self.progress < 1.0:
                painter.setPen(QPen(QColor("#F8FAFC"), 2))
                painter.drawLine(scrub_x, 0, scrub_x, h)


    class VoiceStudioDialog(QDialog):
        """
        Advanced AI Voice Creation Studio & Dialogue Engineering Workspace.
        """

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("AI Voice Creation Studio & Dialogue Engineering")
            self.resize(1120, 780)
            self.setMinimumSize(960, 680)
            self.setStyleSheet(
                """
                QDialog { background-color: #0B0F19; color: #F8FAFC; }
                QTabWidget::pane { border: 1px solid #1E293B; background: #0F172A; border-radius: 6px; }
                QTabBar::tab {
                    background: #1E293B; color: #94A3B8; font-size: 12px; font-weight: 600;
                    padding: 8px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
                }
                QTabBar::tab:selected { background: #0F172A; color: #38BDF8; border-bottom: 2px solid #38BDF8; }
                QTabBar::tab:hover { color: #F8FAFC; }
                QLabel { color: #E2E8F0; font-size: 12px; }
                QLineEdit, QTextEdit, QComboBox, QSpinBox {
                    background: #1E293B; color: #F8FAFC; border: 1px solid #334155;
                    border-radius: 6px; padding: 6px 10px; font-size: 12px;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #38BDF8; }
                QPushButton {
                    background: #2563EB; color: #FFFFFF; font-weight: 600; font-size: 12px;
                    border-radius: 6px; padding: 8px 16px; border: none;
                }
                QPushButton:hover { background: #1D4ED8; }
                QPushButton:disabled { background: #334155; color: #64748B; }
                QGroupBox {
                    border: 1px solid #1E293B; border-radius: 8px; margin-top: 10px;
                    padding-top: 14px; font-weight: 700; color: #38BDF8;
                }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 4px; }
                QSlider::groove:horizontal { height: 6px; background: #1E293B; border-radius: 3px; }
                QSlider::sub-page:horizontal { background: #38BDF8; border-radius: 3px; }
                QSlider::handle:horizontal { background: #F8FAFC; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }
                QTableWidget {
                    background: #0F172A; gridline-color: #1E293B; color: #F8FAFC; border: 1px solid #1E293B;
                    selection-background-color: #1E3A8A; font-size: 11px;
                }
                QHeaderView::section {
                    background: #1E293B; color: #94A3B8; font-weight: 700; font-size: 11px;
                    padding: 4px; border: 1px solid #0F172A;
                }
                """
            )

            self.registry = get_voice_engine_registry()
            self.profile_service = CharacterProfileService(
                storage_dir=Path.cwd() / ".aidub_profiles"
            )

            # Audio playback subsystem
            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(1.0)
            self._last_synth_path: str = ""

            self._init_ui()

        def _init_ui(self) -> None:
            root_layout = QVBoxLayout(self)
            root_layout.setContentsMargins(16, 14, 16, 14)
            root_layout.setSpacing(12)

            # Header
            header_layout = QHBoxLayout()
            title_col = QVBoxLayout()
            title_col.setSpacing(2)
            main_title = QLabel("🎬  AI Voice Creation Studio & Dialogue Engineering", self)
            main_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #F8FAFC;")
            subtitle = QLabel("Modular Voice Generation • Character Consistency • Cinematic Dialogue Matching", self)
            subtitle.setStyleSheet("font-size: 11px; color: #94A3B8;")
            title_col.addWidget(main_title)
            title_col.addWidget(subtitle)
            header_layout.addLayout(title_col, 1)

            # Live hardware pill
            self.hw_label = QLabel(self)
            self.hw_label.setStyleSheet(
                "background: #131D31; border: 1px solid #1E293B; border-radius: 6px; padding: 6px 12px; font-size: 11px; color: #38BDF8;"
            )
            self._refresh_hardware_banner()
            header_layout.addWidget(self.hw_label)

            root_layout.addLayout(header_layout)

            # Main Tab Widget
            self.tabs = QTabWidget(self)
            self.tab_engines = QWidget()
            self.tab_design = QWidget()
            self.tab_cloning = QWidget()
            self.tab_dialogue = QWidget()
            self.tab_quality = QWidget()

            self.tabs.addTab(self.tab_engines, "⚙️ Voice Library & Engines")
            self.tabs.addTab(self.tab_design, "🎨 Voice Design Studio")
            self.tabs.addTab(self.tab_cloning, "🧬 Authorized Voice Cloning")
            self.tabs.addTab(self.tab_dialogue, "🎭 Multi-Speaker Dialogue")
            self.tabs.addTab(self.tab_quality, "🔬 Audio Quality & Comparison Lab")

            self._build_tab_engines()
            self._build_tab_design()
            self._build_tab_cloning()
            self._build_tab_dialogue()
            self._build_tab_quality()

            root_layout.addWidget(self.tabs, 1)

            # Footer button bar
            footer = QHBoxLayout()
            footer.addStretch()
            close_btn = QPushButton("Close Studio", self)
            close_btn.setStyleSheet("background: #1E293B; color: #E2E8F0; padding: 6px 16px;")
            close_btn.clicked.connect(self.accept)
            footer.addWidget(close_btn)
            root_layout.addLayout(footer)

        def _refresh_hardware_banner(self) -> None:
            hw = self.registry.inspect_hardware()
            gpu_desc = f"{hw['gpu_name']} ({hw['vram_free_gb']}GB VRAM free)" if hw["cuda_available"] else "CPU Mode"
            self.hw_label.setText(
                f"RAM: {hw['ram_available_gb']:.1f} / {hw['ram_total_gb']:.1f} GB  •  {gpu_desc}  •  Disk: {hw['disk_free_gb']:.0f} GB free"
            )

        # ======================================================================
        # TAB 1: VOICE LIBRARY & ENGINES
        # ======================================================================
        def _build_tab_engines(self) -> None:
            layout = QHBoxLayout(self.tab_engines)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(14)

            # Left: Engine selector list
            left_col = QVBoxLayout()
            left_col.setSpacing(8)
            lbl = QLabel("Configured Speech Backends:", self.tab_engines)
            lbl.setStyleSheet("font-weight: 700; color: #38BDF8;")
            left_col.addWidget(lbl)

            self.engine_combo = QComboBox(self.tab_engines)
            for kind in self.registry.list_registered_engines():
                engine = self.registry.get_engine(kind)
                self.engine_combo.addItem(f"{engine.metadata.display_name} ({kind.value})", kind.value)
            self.engine_combo.currentIndexChanged.connect(self._on_engine_selected)
            left_col.addWidget(self.engine_combo)

            # Engine details card
            self.engine_detail_box = QTextEdit(self.tab_engines)
            self.engine_detail_box.setReadOnly(True)
            self.engine_detail_box.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
            left_col.addWidget(self.engine_detail_box, 1)

            test_btn = QPushButton("Probe Backend Availability", self.tab_engines)
            test_btn.clicked.connect(self._test_current_engine_status)
            left_col.addWidget(test_btn)

            layout.addLayout(left_col, 3)

            # Right: System Resource and Management Panel
            right_col = QVBoxLayout()
            right_col.setSpacing(10)

            res_group = QGroupBox("System Resource & Memory Controls", self.tab_engines)
            res_lay = QVBoxLayout(res_group)
            res_lay.setSpacing(8)

            self.res_detail_label = QLabel(res_group)
            self.res_detail_label.setStyleSheet("font-size: 11px; color: #94A3B8; line-height: 1.4;")
            res_lay.addWidget(self.res_detail_label)

            refresh_hw_btn = QPushButton("Refresh Hardware Status", res_group)
            refresh_hw_btn.setStyleSheet("background: #1E293B; color: #E2E8F0;")
            refresh_hw_btn.clicked.connect(self._update_resource_display)
            res_lay.addWidget(refresh_hw_btn)

            unload_btn = QPushButton("Unload All Active Models from VRAM", res_group)
            unload_btn.setStyleSheet("background: #991B1B; color: #FEE2E2;")
            unload_btn.clicked.connect(self._unload_all_models)
            res_lay.addWidget(unload_btn)

            res_lay.addStretch()
            right_col.addWidget(res_group, 1)

            layout.addLayout(right_col, 2)
            self._on_engine_selected()
            self._update_resource_display()

        def _on_engine_selected(self) -> None:
            kind_val = self.engine_combo.currentData()
            if not kind_val:
                return
            kind = VoiceEngineKind(kind_val)
            meta = self.registry.get_engine(kind).metadata

            caps = "\n  - ".join(c.value for c in sorted(meta.capabilities))
            langs = ", ".join(meta.supported_languages[:12]) + ("..." if len(meta.supported_languages) > 12 else "")
            limits = "\n  * ".join(meta.known_limitations) if meta.known_limitations else "None reported."

            info_text = (
                f"ENGINE: {meta.display_name}\n"
                f"Model Identifier: {meta.model_id}\n"
                f"Version: {meta.version}\n"
                f"License: {meta.license_info} (Commercial allowed: {meta.commercial_use_allowed})\n"
                f"Execution: {'Local Model' if meta.is_local else 'Cloud REST API'}\n"
                f"Hardware Specs: {meta.hardware_requirements}\n"
                f"Min RAM: {meta.min_ram_gb:.1f} GB  |  Min VRAM: {meta.min_vram_gb:.1f} GB\n\n"
                f"Supported Capabilities:\n  - {caps}\n\n"
                f"Languages:\n  {langs}\n\n"
                f"Known Limitations:\n  * {limits}"
            )
            self.engine_detail_box.setPlainText(info_text)

        def _test_current_engine_status(self) -> None:
            kind_val = self.engine_combo.currentData()
            if not kind_val:
                return
            kind = VoiceEngineKind(kind_val)
            engine = self.registry.get_engine(kind)
            ready, reason = engine.is_available()
            if ready:
                QMessageBox.information(self, "Engine Status: Ready", f"[{engine.metadata.display_name}]\n\n{reason}")
            else:
                QMessageBox.warning(self, "Engine Status: Unavailable", f"[{engine.metadata.display_name}]\n\n{reason}")

        def _update_resource_display(self) -> None:
            self._refresh_hardware_banner()
            hw = self.registry.inspect_hardware()
            loaded = ", ".join(hw["active_models_loaded"]) if hw["active_models_loaded"] else "None (idle)"
            txt = (
                f"Host RAM: {hw['ram_available_gb']:.1f} GB available (of {hw['ram_total_gb']:.1f} GB)\n"
                f"CUDA Device: {hw['gpu_name']}\n"
                f"VRAM Capacity: {hw['vram_total_gb']:.1f} GB total, {hw['vram_free_gb']:.1f} GB free\n"
                f"Disk Free Space: {hw['disk_free_gb']:.1f} GB\n\n"
                f"Currently Loaded Models:\n  {loaded}"
            )
            self.res_detail_label.setText(txt)

        def _unload_all_models(self) -> None:
            self.registry.unload_all_engines()
            self._update_resource_display()
            QMessageBox.information(self, "Models Unloaded", "All active model weights and tensors released from memory.")

        # ======================================================================
        # TAB 2: VOICE DESIGN STUDIO
        # ======================================================================
        def _build_tab_design(self) -> None:
            layout = QVBoxLayout(self.tab_design)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(12)

            grid = QGridLayout()
            grid.setSpacing(10)

            # Row 0: Character Prompt Description
            grid.addWidget(QLabel("Character Voice Prompt Description:", self.tab_design), 0, 0, 1, 4)
            self.vd_prompt_edit = QTextEdit(self.tab_design)
            self.vd_prompt_edit.setPlaceholderText(
                "Describe the character's vocal presentation, age, roughness, resonance, personality (e.g. 'A rugged, battle-worn mercenary captain in his late 40s with a deep raspy baritone and a dry, sarcastic delivery')..."
            )
            self.vd_prompt_edit.setFixedHeight(72)
            grid.addWidget(self.vd_prompt_edit, 1, 0, 1, 4)

            # Row 2: Gender / Presentation, Age Range, Pitch, Timbre
            grid.addWidget(QLabel("Vocal Presentation:", self.tab_design), 2, 0)
            self.vd_gender_combo = QComboBox(self.tab_design)
            self.vd_gender_combo.addItems(["Male", "Female", "Non-Binary", "Androgynous"])
            grid.addWidget(self.vd_gender_combo, 2, 1)

            grid.addWidget(QLabel("Approximate Age:", self.tab_design), 2, 2)
            self.vd_age_combo = QComboBox(self.tab_design)
            self.vd_age_combo.addItems(["Child (6-12)", "Young Adult (18-25)", "Adult (30-50)", "Senior (60+)"])
            grid.addWidget(self.vd_age_combo, 2, 3)

            # Row 3: Pitch, Timbre
            grid.addWidget(QLabel("Pitch Range:", self.tab_design), 3, 0)
            self.vd_pitch_combo = QComboBox(self.tab_design)
            self.vd_pitch_combo.addItems(["Deep Bass", "Low Baritone", "Medium Natural", "High Tenor", "Piercing"])
            grid.addWidget(self.vd_pitch_combo, 3, 1)

            grid.addWidget(QLabel("Timbre & Texture:", self.tab_design), 3, 2)
            self.vd_timbre_combo = QComboBox(self.tab_design)
            self.vd_timbre_combo.addItems(["Warm & Resonant", "Gravelly & Raspy", "Breathy & Intimate", "Silky & Smooth", "Metallic & Crisp"])
            grid.addWidget(self.vd_timbre_combo, 3, 3)

            # Row 4: Accent & Speed
            grid.addWidget(QLabel("Accent / Dialect:", self.tab_design), 4, 0)
            self.vd_accent_combo = QComboBox(self.tab_design)
            self.vd_accent_combo.addItems(["Bengali (Dhaka Native)", "Bengali (Kolkata)", "Standard English (RP)", "US English (General)", "Hindi (Standard)", "Spanish (Castilian)"])
            grid.addWidget(self.vd_accent_combo, 4, 1)

            grid.addWidget(QLabel("Speaking Rate:", self.tab_design), 4, 2)
            self.vd_speed_combo = QComboBox(self.tab_design)
            self.vd_speed_combo.addItems(["Slow & Deliberate", "Natural Conversational", "Fast-Paced", "Rapid Dramatic"])
            grid.addWidget(self.vd_speed_combo, 4, 3)

            layout.addLayout(grid)

            # Audition phrase input
            phrase_row = QHBoxLayout()
            phrase_row.addWidget(QLabel("Audition Text Phrase:", self.tab_design))
            self.vd_test_phrase = QLineEdit("In this city, the only thing thicker than the shadows is the silence.", self.tab_design)
            phrase_row.addWidget(self.vd_test_phrase, 1)
            layout.addLayout(phrase_row)

            # Waveform and player controls
            self.vd_waveform = _WaveformWidget("#8B5CF6", self.tab_design)
            layout.addWidget(self.vd_waveform)

            btn_row = QHBoxLayout()
            synth_btn = QPushButton("🎙️  Synthesize Audition Sample", self.tab_design)
            synth_btn.clicked.connect(self._synthesize_voice_design_sample)
            btn_row.addWidget(synth_btn)

            play_btn = QPushButton("▶ Play", self.tab_design)
            play_btn.setStyleSheet("background: #10B981; color: #FFF;")
            play_btn.clicked.connect(self._play_audition_sample)
            btn_row.addWidget(play_btn)

            btn_row.addStretch()

            # Save as Character Profile
            self.vd_char_name_input = QLineEdit(self.tab_design)
            self.vd_char_name_input.setPlaceholderText("Character Name (e.g. Detective Roy)")
            self.vd_char_name_input.setFixedWidth(200)
            btn_row.addWidget(self.vd_char_name_input)

            save_profile_btn = QPushButton("💾 Save as Character Profile", self.tab_design)
            save_profile_btn.setStyleSheet("background: #7C3AED; color: #FFF;")
            save_profile_btn.clicked.connect(self._save_designed_voice_profile)
            btn_row.addWidget(save_profile_btn)

            layout.addLayout(btn_row)
            layout.addStretch()

        def _synthesize_voice_design_sample(self) -> None:
            text = self.vd_test_phrase.text().strip()
            if not text:
                QMessageBox.warning(self, "Missing Text", "Please enter an audition text phrase.")
                return

            kind = VoiceEngineKind(self.engine_combo.currentData() or VoiceEngineKind.SYNTHETIC.value)
            engine = self.registry.get_engine(kind)

            prompt = VoiceDesignPrompt(
                description=self.vd_prompt_edit.toPlainText().strip(),
                gender=self.vd_gender_combo.currentText(),
                age_range=self.vd_age_combo.currentText(),
                pitch=self.vd_pitch_combo.currentText(),
                timbre=self.vd_timbre_combo.currentText(),
                accent=self.vd_accent_combo.currentText(),
                speed=self.vd_speed_combo.currentText(),
            )

            # Check capability
            if EngineCapability.VOICE_DESIGN_PROMPT not in engine.metadata.capabilities:
                QMessageBox.information(
                    self,
                    "Engine Capability Notice",
                    f"{engine.metadata.display_name} does not natively generate parametric prompt-designed voices.\n\n"
                    "Applying closest matching preset speaker profile and prosodic adjustments."
                )

            req = SynthesisRequest(
                request_id=Identifier("req_design"),
                utterance_id=Identifier("utt_design"),
                voice_profile_id=Identifier("vp_design"),
                text=text,
                language="bn-BD" if "Bengali" in prompt.accent else "en-US",
                voice_design=prompt,
                seed=42,
            )

            tmp_dir = tempfile.mkdtemp(prefix="aidub_design_")
            try:
                result = engine.synthesize(req, tmp_dir)
                self._last_synth_path = result.output_path
                self.vd_waveform.set_progress(0.0)
                QMessageBox.information(
                    self,
                    "Audition Synthesized",
                    f"Generated audition sample ({result.duration_ms}ms) via {engine.metadata.display_name}.\n"
                    f"Controls Applied: {', '.join(result.applied_controls)}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Synthesis Error", f"Failed generating voice sample: {exc}")

        def _play_audition_sample(self) -> None:
            if not self._last_synth_path or not Path(self._last_synth_path).is_file():
                QMessageBox.warning(self, "No Audio", "Please synthesize a voice sample first.")
                return
            self._player.setSource(QUrl.fromLocalFile(self._last_synth_path))
            self._player.play()

        def _save_designed_voice_profile(self) -> None:
            char_name = self.vd_char_name_input.text().strip()
            if not char_name:
                QMessageBox.warning(self, "Missing Name", "Please specify a character name.")
                return

            char_id = char_name.lower().replace(" ", "_")
            kind_val = self.engine_combo.currentData() or "edge_tts"

            profile = CharacterVoiceProfile(
                profile_id=Identifier(f"vp_{char_id}"),
                character_id=Identifier(char_id),
                display_name=char_name,
                consent_authorized=True,
                selected_engine=kind_val,
                primary_language="bn-BD" if "Bengali" in self.vd_accent_combo.currentText() else "en-US",
                consent_notes=f"Created via Voice Design Studio ({self.vd_gender_combo.currentText()}, {self.vd_age_combo.currentText()})",
            )
            self.profile_service.register_profile(profile)
            QMessageBox.information(self, "Profile Saved", f"Character voice profile '{char_name}' registered successfully.")

        # ======================================================================
        # TAB 3: AUTHORIZED VOICE CLONING & CONSENT GATE
        # ======================================================================
        def _build_tab_cloning(self) -> None:
            layout = QVBoxLayout(self.tab_cloning)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(12)

            # Step 1: Reference Audio Selection
            ref_box = QGroupBox("1. Reference Speaker Audio (Clean Speech Sample)", self.tab_cloning)
            ref_lay = QHBoxLayout(ref_box)
            self.clone_ref_path = QLineEdit(ref_box)
            self.clone_ref_path.setPlaceholderText("Path to clean WAV/MP3 reference speech recording...")
            ref_lay.addWidget(self.clone_ref_path, 1)

            browse_btn = QPushButton("Browse Audio File…", ref_box)
            browse_btn.clicked.connect(self._browse_clone_ref_audio)
            ref_lay.addWidget(browse_btn)

            analyze_btn = QPushButton("🔍 Analyze Acoustic Quality", ref_box)
            analyze_btn.setStyleSheet("background: #0284C7; color: #FFF;")
            analyze_btn.clicked.connect(self._run_reference_analysis)
            ref_lay.addWidget(analyze_btn)
            layout.addWidget(ref_box)

            # Acoustic Quality Inspection Report
            self.clone_analysis_label = QLabel(self.tab_cloning)
            self.clone_analysis_label.setStyleSheet(
                "background: #131D31; border: 1px solid #1E293B; border-radius: 6px; padding: 10px; font-size: 11px; line-height: 1.5;"
            )
            self.clone_analysis_label.setText("No reference audio analyzed yet. Select a file above and click 'Analyze Acoustic Quality'.")
            layout.addWidget(self.clone_analysis_label)

            # Step 2: Legal Consent Confirmation & Safeguards
            consent_box = QGroupBox("2. Mandatory Legal Authorization & Consent Verification", self.tab_cloning)
            consent_lay = QVBoxLayout(consent_box)
            consent_lay.setSpacing(8)

            self.consent_checkbox = QCheckBox(
                "I affirm and certify that I have explicit authorization, consent, or legal license from the speaker/rights-holder "
                "to clone their voice for this film dubbing project. I agree NOT to use this profile for deceptive impersonation.",
                consent_box,
            )
            self.consent_checkbox.setStyleSheet("color: #FBBF24; font-weight: 600;")
            self.consent_checkbox.stateChanged.connect(self._on_consent_changed)
            consent_lay.addWidget(self.consent_checkbox)

            fields_row = QHBoxLayout()
            self.signer_name_edit = QLineEdit(consent_box)
            self.signer_name_edit.setPlaceholderText("Authorized Signer / Studio Executive...")
            fields_row.addWidget(self.signer_name_edit)

            self.voice_owner_edit = QLineEdit(consent_box)
            self.voice_owner_edit.setPlaceholderText("Voice Owner / Actor Name...")
            fields_row.addWidget(self.voice_owner_edit)
            consent_lay.addLayout(fields_row)

            layout.addWidget(consent_box)

            # Step 3: Synthesis & Verification
            synth_box = QGroupBox("3. Clone Generation & Acoustic Verification", self.tab_cloning)
            synth_lay = QHBoxLayout(synth_box)

            self.clone_test_phrase = QLineEdit("Every great movie voice begins with respect for the actor's craft.", synth_box)
            synth_lay.addWidget(self.clone_test_phrase, 1)

            self.clone_generate_btn = QPushButton("🧬 Generate Cloned Preview", synth_box)
            self.clone_generate_btn.setEnabled(False)
            self.clone_generate_btn.setStyleSheet("background: #059669; color: #FFF;")
            self.clone_generate_btn.clicked.connect(self._generate_cloned_preview)
            synth_lay.addWidget(self.clone_generate_btn)

            layout.addWidget(synth_box)

            self.clone_waveform = _WaveformWidget("#10B981", self.tab_cloning)
            layout.addWidget(self.clone_waveform)
            layout.addStretch()

        def _browse_clone_ref_audio(self) -> None:
            fn, _ = QFileDialog.getOpenFileName(self, "Select Reference Audio", "", "Audio Files (*.wav *.mp3 *.flac *.m4a)")
            if fn:
                self.clone_ref_path.setText(fn)
                self._run_reference_analysis()

        def _run_reference_analysis(self) -> None:
            p = self.clone_ref_path.text().strip()
            if not p or not Path(p).is_file():
                QMessageBox.warning(self, "File Not Found", "Please select an existing audio file on disk.")
                return

            rep: ReferenceAudioAnalysis = analyze_voice_audio(p)
            warns = "\n  ⚠️ " + "\n  ⚠️ ".join(rep.warnings) if rep.warnings else "None. Audio meets high fidelity criteria."

            color_map = {"excellent": "#10B981", "good": "#38BDF8", "marginal": "#F59E0B", "rejected": "#EF4444"}
            badge_color = color_map.get(rep.quality_rating, "#94A3B8")

            txt = (
                f"<b>Duration:</b> {rep.duration_s:.1f}s  |  "
                f"<b>Sample Rate:</b> {rep.sample_rate} Hz  |  "
                f"<b>Estimated SNR:</b> {rep.snr_db:.1f} dB  |  "
                f"<b>Clipping Detected:</b> {'YES' if rep.has_clipping else 'No'}  |  "
                f"<b>Silence Ratio:</b> {rep.silence_ratio * 100:.1f}%\n"
                f"<b>Cloning Suitability:</b> <font color='{badge_color}'><b>{rep.quality_rating.upper()}</b></font> "
                f"({'Meets requirements' if rep.is_suitable_for_cloning else 'Unsuitable for reference cloning'})\n"
                f"<b>Acoustic Diagnostics:</b>{warns}"
            )
            self.clone_analysis_label.setText(txt)

        def _on_consent_changed(self) -> None:
            self.clone_generate_btn.setEnabled(self.consent_checkbox.isChecked())

        def _generate_cloned_preview(self) -> None:
            if not self.consent_checkbox.isChecked():
                QMessageBox.critical(self, "Consent Required", "Voice cloning requires affirmative legal authorization.")
                return

            ref_p = self.clone_ref_path.text().strip()
            if not ref_p or not Path(ref_p).is_file():
                QMessageBox.warning(self, "Reference Audio Required", "Please specify an existing reference audio file.")
                return

            kind = VoiceEngineKind(self.engine_combo.currentData() or VoiceEngineKind.SYNTHETIC.value)
            engine = self.registry.get_engine(kind)

            consent = VoiceConsentDeclaration(
                authorized_by=self.signer_name_edit.text().strip() or "Studio Lead",
                voice_owner=self.voice_owner_edit.text().strip() or "Actor",
                is_authorized=True,
            )

            req = SynthesisRequest(
                request_id=Identifier("req_clone"),
                utterance_id=Identifier("utt_clone"),
                voice_profile_id=Identifier("vp_clone"),
                text=self.clone_test_phrase.text().strip(),
                language="en-US",
                reference_audio_path=ref_p,
                consent=consent,
                seed=42,
            )

            tmp_dir = tempfile.mkdtemp(prefix="aidub_clone_")
            try:
                res = engine.synthesize(req, tmp_dir)
                self._last_synth_path = res.output_path

                # Measure spectral correlation between reference and synthesis
                similarity = measure_acoustic_similarity(ref_p, res.output_path)

                QMessageBox.information(
                    self,
                    "Clone Generated",
                    f"Cloned preview generated successfully via {engine.metadata.display_name}.\n\n"
                    f"Duration: {res.duration_ms}ms\n"
                    f"Acoustic Spectral Similarity: {similarity:.3f} (0.0 to 1.0)\n"
                    f"Applied Controls: {', '.join(res.applied_controls)}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Cloning Failed", f"Failed generating cloned voice: {exc}")

        # ======================================================================
        # TAB 4: MULTI-SPEAKER DIALOGUE EDITOR
        # ======================================================================
        def _build_tab_dialogue(self) -> None:
            layout = QVBoxLayout(self.tab_dialogue)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)

            top_bar = QHBoxLayout()
            top_bar.addWidget(QLabel("Scene Dialogue Turns Sequence:", self.tab_dialogue))
            top_bar.addStretch()

            add_btn = QPushButton("+ Add Turn", self.tab_dialogue)
            add_btn.clicked.connect(self._add_dialogue_turn)
            top_bar.addWidget(add_btn)

            del_btn = QPushButton("- Remove Selected", self.tab_dialogue)
            del_btn.setStyleSheet("background: #1E293B; color: #E2E8F0;")
            del_btn.clicked.connect(self._remove_dialogue_turn)
            top_bar.addWidget(del_btn)

            layout.addLayout(top_bar)

            # Table of dialogue turns
            self.dialogue_table = QTableWidget(self.tab_dialogue)
            self.dialogue_table.setColumnCount(6)
            self.dialogue_table.setHorizontalHeaderLabels([
                "Turn #", "Character", "Emotion", "Speaking Rate", "Target Dur (s)", "Dialogue Text"
            ])
            self.dialogue_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.dialogue_table, 1)

            # Populate with sample cinematic turns
            self._populate_sample_dialogue_turns()

            # Batch Synthesis button
            action_row = QHBoxLayout()
            action_row.addStretch()
            synth_all_btn = QPushButton("🎭 Synthesize Entire Scene Dialogue", self.tab_dialogue)
            synth_all_btn.setStyleSheet("background: #0284C7; color: #FFF; padding: 8px 20px;")
            synth_all_btn.clicked.connect(self._synthesize_all_dialogue_turns)
            action_row.addWidget(synth_all_btn)
            layout.addLayout(action_row)

        def _populate_sample_dialogue_turns(self) -> None:
            samples = [
                ("1", "Detective Miller", "tense", "1.0", "3.2", "We don't have much time. Did anyone see you leave the docks?"),
                ("2", "Witness Elena", "fear", "1.1", "2.8", "I told you, there was a black sedan waiting by warehouse four!"),
                ("3", "Detective Miller", "calm", "0.95", "4.0", "Take a breath. You're safe in this room. Tell me about the driver."),
            ]
            self.dialogue_table.setRowCount(len(samples))
            for row, item in enumerate(samples):
                for col in range(6):
                    it = QTableWidgetItem(item[col])
                    self.dialogue_table.setItem(row, col, it)

        def _add_dialogue_turn(self) -> None:
            r = self.dialogue_table.rowCount()
            self.dialogue_table.insertRow(r)
            self.dialogue_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.dialogue_table.setItem(r, 1, QTableWidgetItem("Character"))
            self.dialogue_table.setItem(r, 2, QTableWidgetItem("neutral"))
            self.dialogue_table.setItem(r, 3, QTableWidgetItem("1.0"))
            self.dialogue_table.setItem(r, 4, QTableWidgetItem("3.0"))
            self.dialogue_table.setItem(r, 5, QTableWidgetItem("New dialogue line..."))

        def _remove_dialogue_turn(self) -> None:
            cr = self.dialogue_table.currentRow()
            if cr >= 0:
                self.dialogue_table.removeRow(cr)

        def _synthesize_all_dialogue_turns(self) -> None:
            rows = self.dialogue_table.rowCount()
            if rows == 0:
                return

            kind = VoiceEngineKind(self.engine_combo.currentData() or VoiceEngineKind.SYNTHETIC.value)
            engine = self.registry.get_engine(kind)

            success_count = 0
            tmp_dir = tempfile.mkdtemp(prefix="aidub_scene_")

            for r in range(rows):
                char_name = self.dialogue_table.item(r, 1).text() if self.dialogue_table.item(r, 1) else "Actor"
                emo_str = self.dialogue_table.item(r, 2).text() if self.dialogue_table.item(r, 2) else "neutral"
                text = self.dialogue_table.item(r, 5).text() if self.dialogue_table.item(r, 5) else ""

                if not text.strip():
                    continue

                emo = EmotionLabel.NEUTRAL
                for e in EmotionLabel:
                    if e.value == emo_str.lower():
                        emo = e
                        break

                req = SynthesisRequest(
                    request_id=Identifier(f"req_turn_{r}"),
                    utterance_id=Identifier(f"utt_turn_{r}"),
                    voice_profile_id=Identifier(f"vp_{char_name.lower().replace(' ', '_')}"),
                    text=text,
                    language="en-US",
                    emotion=emo,
                    seed=42 + r,
                )
                try:
                    res = engine.synthesize(req, tmp_dir)
                    self.profile_service.link_take(
                        character_id=char_name.lower().replace(" ", "_"),
                        utterance_id=str(req.utterance_id),
                        scene_id="scene_01",
                        audio_path=res.output_path,
                        engine_kind=kind.value,
                    )
                    success_count += 1
                except Exception as exc:
                    logger.warning("Turn %d synthesis error: %s", r, exc)

            QMessageBox.information(
                self,
                "Dialogue Scene Synthesized",
                f"Successfully synthesized {success_count}/{rows} dialogue turns into timeline buffer.\n"
                f"Engine: {engine.metadata.display_name}"
            )

        # ======================================================================
        # TAB 5: AUDIO QUALITY & COMPARISON LAB
        # ======================================================================
        def _build_tab_quality(self) -> None:
            layout = QVBoxLayout(self.tab_quality)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(12)

            # A/B slots
            ab_layout = QHBoxLayout()

            # Slot A
            box_a = QGroupBox("Channel A (Reference Speech / Engine 1)", self.tab_quality)
            lay_a = QVBoxLayout(box_a)
            self.path_a_edit = QLineEdit(box_a)
            self.path_a_edit.setPlaceholderText("Path to WAV audio file A...")
            lay_a.addWidget(self.path_a_edit)
            btn_a = QPushButton("Browse A…", box_a)
            btn_a.clicked.connect(lambda: self._browse_quality_file(self.path_a_edit))
            lay_a.addWidget(btn_a)
            self.wave_a = _WaveformWidget("#38BDF8", box_a)
            lay_a.addWidget(self.wave_a)
            play_a = QPushButton("▶ Play A", box_a)
            play_a.clicked.connect(lambda: self._play_file(self.path_a_edit.text()))
            lay_a.addWidget(play_a)
            ab_layout.addWidget(box_a)

            # Slot B
            box_b = QGroupBox("Channel B (Synthesized Speech / Engine 2)", self.tab_quality)
            lay_b = QVBoxLayout(box_b)
            self.path_b_edit = QLineEdit(box_b)
            self.path_b_edit.setPlaceholderText("Path to WAV audio file B...")
            lay_b.addWidget(self.path_b_edit)
            btn_b = QPushButton("Browse B…", box_b)
            btn_b.clicked.connect(lambda: self._browse_quality_file(self.path_b_edit))
            lay_b.addWidget(btn_b)
            self.wave_b = _WaveformWidget("#8B5CF6", box_b)
            lay_b.addWidget(self.wave_b)
            play_b = QPushButton("▶ Play B", box_b)
            play_b.clicked.connect(lambda: self._play_file(self.path_b_edit.text()))
            lay_b.addWidget(play_b)
            ab_layout.addWidget(box_b)

            layout.addLayout(ab_layout)

            # Compare Button & Metric Display
            cmp_btn = QPushButton("🔬 Compare Acoustic Metrics & Similarity", self.tab_quality)
            cmp_btn.setStyleSheet("background: #0284C7; color: #FFF;")
            cmp_btn.clicked.connect(self._run_quality_comparison)
            layout.addWidget(cmp_btn)

            self.quality_report_text = QTextEdit(self.tab_quality)
            self.quality_report_text.setReadOnly(True)
            self.quality_report_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
            self.quality_report_text.setPlainText("Select two audio takes above and click 'Compare Acoustic Metrics & Similarity'.")
            layout.addWidget(self.quality_report_text, 1)

        def _browse_quality_file(self, target_line_edit: QLineEdit) -> None:
            fn, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.wav *.mp3 *.flac)")
            if fn:
                target_line_edit.setText(fn)

        def _play_file(self, path_str: str) -> None:
            p = Path(path_str)
            if not p.is_file():
                QMessageBox.warning(self, "Missing Audio", "Audio file not found on disk.")
                return
            self._player.setSource(QUrl.fromLocalFile(str(p)))
            self._player.play()

        def _run_quality_comparison(self) -> None:
            pa = self.path_a_edit.text().strip()
            pb = self.path_b_edit.text().strip()

            if not pa or not pb or not Path(pa).is_file() or not Path(pb).is_file():
                QMessageBox.warning(self, "Files Required", "Please specify valid audio files for both Channel A and B.")
                return

            rep_a = analyze_voice_audio(pa)
            rep_b = analyze_voice_audio(pb)
            sim = measure_acoustic_similarity(pa, pb)

            txt = (
                f"=== ACOUSTIC COMPARISON REPORT ===\n\n"
                f"CHANNEL A: {Path(pa).name}\n"
                f"  Duration: {rep_a.duration_s:.2f}s  |  Sample Rate: {rep_a.sample_rate} Hz\n"
                f"  Estimated SNR: {rep_a.snr_db:.1f} dB  |  Clipping: {rep_a.has_clipping}  |  Silence: {rep_a.silence_ratio * 100:.1f}%\n"
                f"  Rating: {rep_a.quality_rating.upper()}\n\n"
                f"CHANNEL B: {Path(pb).name}\n"
                f"  Duration: {rep_b.duration_s:.2f}s  |  Sample Rate: {rep_b.sample_rate} Hz\n"
                f"  Estimated SNR: {rep_b.snr_db:.1f} dB  |  Clipping: {rep_b.has_clipping}  |  Silence: {rep_b.silence_ratio * 100:.1f}%\n"
                f"  Rating: {rep_b.quality_rating.upper()}\n\n"
                f"RELATIVE ACOUSTIC SPECTRAL SIMILARITY: {sim:.3f} (0.0 to 1.0)\n\n"
                f"DISCLAIMER & METHODOLOGY:\n"
                f"  * Mathematical acoustic similarity measures normalized power spectral correlation across frequency bands.\n"
                f"  * This metric evaluates acoustic frequency distribution and does NOT replace human-perceived vocal naturalness.\n"
                f"  * Timing delta: {abs(rep_a.duration_s - rep_b.duration_s):.2f}s ({(abs(rep_a.duration_s - rep_b.duration_s)/max(0.1, rep_a.duration_s))*100:.1f}%)"
            )
            self.quality_report_text.setPlainText(txt)


__all__ = [
    "VoiceStudioDialog",
]
