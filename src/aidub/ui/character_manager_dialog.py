"""Interactive Character & Speaker Manager Dialog for AI Movie Dubbing Studio."""

from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class CharacterManagerDialog(QDialog):
        """Inspect, rename, assign voices, and reassign speakers across project dialogue."""

        characters_updated = Signal(dict)  # emits {old_char: new_char, ...} or updated mapping

        def __init__(
            self,
            character_counts: dict[str, int] | None = None,
            character_voices: dict[str, str] | None = None,
            parent: Any = None,
            *,
            media_path: str | Path | None = None,
            clips: list[Any] | None = None,
            clip_characters: dict[str, str] | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Character & Speaker Manager")
            self.setMinimumSize(640, 480)
            self.resize(760, 520)

            self._media_path = Path(media_path) if media_path else None
            self._clips = list(clips or [])
            self._clip_characters = dict(clip_characters or {})
            self._counts: dict[str, int] = dict(character_counts or {})
            self._voices: dict[str, str] = dict(character_voices or {})
            self._renames: dict[str, str] = {}

            # Standard available Bangla Edge-TTS voices
            self._available_voices = [
                "bn-BD-PradeepNeural (Male - Default)",
                "bn-BD-NabanitaNeural (Female)",
                "bn-IN-BashkarNeural (Male - Indian Bengali)",
                "bn-IN-TanishaaNeural (Female - Indian Bengali)",
                "en-US-JennyNeural (Female - English)",
                "en-US-GuyNeural (Male - English)",
            ]

            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            # Header
            header = QLabel("PROJECT CHARACTERS & VOICE ROLES", self)
            header.setStyleSheet("font-size:14px;font-weight:800;color:#F7F9FC;")
            layout.addWidget(header)

            desc = QLabel(
                "Review detected speakers from diarization or subtitle cues. "
                "Rename characters across all timeline cues, assign dub voices, or reassign dialogue lines.",
                self,
            )
            desc.setWordWrap(True)
            desc.setStyleSheet("color:#94A3B8;font-size:11px;")
            layout.addWidget(desc)

            # Table of characters
            self.table = QTableWidget(self)
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["Character / Speaker", "Lines / Cues", "Assigned Dub Voice", "Actions"])
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.table.setStyleSheet(
                "QTableWidget{background:#111722;color:#E2E8F0;border:1px solid #283446;gridline-color:#1E293B;}"
                "QHeaderView::section{background:#1A2234;color:#94A3B8;padding:6px;border:none;font-weight:700;}"
            )
            layout.addWidget(self.table, stretch=1)

            # Toolbar under table
            tb_row = QHBoxLayout()
            self.detect_btn = QPushButton("🤖 Auto-Detect Characters…", self)
            self.detect_btn.setToolTip("Automatically detect movie characters from dialogue cues and media audio")
            self.detect_btn.setStyleSheet(
                "QPushButton{background:#1E3A8A;color:#93C5FD;border:1px solid #3B82F6;border-radius:4px;padding:5px 12px;font-weight:700;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            self.detect_btn.clicked.connect(self._auto_detect_characters)

            self.add_char_btn = QPushButton("+ Add Character…", self)
            self.add_char_btn.clicked.connect(self._add_character)
            self.rename_btn = QPushButton("✏ Rename Selected…", self)
            self.rename_btn.clicked.connect(self._rename_selected)
            self.reassign_btn = QPushButton("🔄 Reassign Cues to Another Speaker…", self)
            self.reassign_btn.clicked.connect(self._reassign_selected)

            tb_row.addWidget(self.detect_btn)
            tb_row.addWidget(self.add_char_btn)
            tb_row.addWidget(self.rename_btn)
            tb_row.addWidget(self.reassign_btn)
            tb_row.addStretch()
            layout.addLayout(tb_row)

            # Dialog buttons
            btn_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                self,
            )
            btn_box.accepted.connect(self._on_accept)
            btn_box.rejected.connect(self.reject)
            layout.addWidget(btn_box)

            self._refresh_table()

        def _refresh_table(self) -> None:
            chars = sorted(self._counts.keys())
            if not chars:
                chars = ["SPEAKER_00"]
                self._counts["SPEAKER_00"] = 0

            self.table.setRowCount(len(chars))
            for row, char in enumerate(chars):
                # Column 0: Character name
                item_name = QTableWidgetItem(char)
                item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, item_name)

                # Column 1: Line count
                count = self._counts.get(char, 0)
                item_count = QTableWidgetItem(f"{count} cues")
                item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_count.setFlags(item_count.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 1, item_count)

                # Column 2: Voice ComboBox
                voice_combo = QComboBox(self.table)
                voice_combo.addItems(self._available_voices)
                assigned = self._voices.get(char, "")
                # Find matching combo item
                for idx, v in enumerate(self._available_voices):
                    if assigned and assigned in v:
                        voice_combo.setCurrentIndex(idx)
                        break
                else:
                    # Alternating default voice
                    default_idx = row % 2
                    voice_combo.setCurrentIndex(default_idx)

                voice_combo.currentTextChanged.connect(
                    lambda text, c=char: self._on_voice_changed(c, text)
                )
                self.table.setCellWidget(row, 2, voice_combo)

                # Column 3: Rename button
                act_btn = QPushButton("Rename", self.table)
                act_btn.setStyleSheet(
                    "QPushButton{background:#1E293B;color:#93C5FD;border:1px solid #3B82F6;padding:2px 8px;border-radius:3px;font-size:10px;}"
                    "QPushButton:hover{background:#2563EB;color:#FFF;}"
                )
                act_btn.clicked.connect(lambda _, c=char: self._rename_character(c))
                self.table.setCellWidget(row, 3, act_btn)

        def _auto_detect_characters(self) -> None:
            """Automatically discover characters from dialogue cues and media audio."""
            parent_studio = self.parent()
            if parent_studio is not None and hasattr(parent_studio, "auto_detect_characters"):
                detected = parent_studio.auto_detect_characters()
                counts = (
                    parent_studio._compute_character_counts()
                    if hasattr(parent_studio, "_compute_character_counts")
                    else {c: 1 for c in detected}
                )
                voices = parent_studio._current_project_data.get("character_voices", {})
                self._counts = dict(counts)
                self._voices = dict(voices)
                self._refresh_table()
                QMessageBox.information(
                    self,
                    "Characters Recognized",
                    f"Successfully recognized {len(self._counts)} character(s) across dialogue cues.",
                )
                return

            # Standalone fallback detection from provided clips and media
            from aidub.ai.voice.character_cloning_engine import (
                CharacterDetectionEngine,
                extract_speaker_from_cue_text,
            )

            detected_counts: dict[str, int] = {}
            for clip in self._clips:
                text = clip[3] if len(clip) > 3 else ""
                spk, _ = extract_speaker_from_cue_text(text)
                if spk:
                    detected_counts[spk] = detected_counts.get(spk, 0) + 1

            engine = CharacterDetectionEngine()
            if not detected_counts and self._media_path and self._media_path.is_file():
                try:
                    chars, _ = engine.detect_from_media(self._media_path)
                    for c in chars:
                        detected_counts[c.canonical_name] = detected_counts.get(c.canonical_name, 0) + 1
                except Exception:
                    pass

            if not detected_counts:
                detected_counts = {"SPEAKER_00": 1, "SPEAKER_01": 1}

            self._counts = detected_counts
            for idx, c in enumerate(sorted(self._counts.keys())):
                if c not in self._voices:
                    raw_voice = self._available_voices[idx % len(self._available_voices)].split(" ")[0]
                    self._voices[c] = raw_voice

            self._refresh_table()
            QMessageBox.information(
                self,
                "Characters Recognized",
                f"Successfully recognized {len(self._counts)} character(s).",
            )

        def _on_voice_changed(self, character: str, voice_display: str) -> None:
            # Extract raw voice name from "bn-BD-PradeepNeural (Male - Default)"
            voice_name = voice_display.split(" ")[0].strip()
            self._voices[character] = voice_name

        def _add_character(self) -> None:
            name, ok = QInputDialog.getText(
                self,
                "Add Character",
                "Enter new character name (e.g. John, Narrator, Maya):",
                QLineEdit.EchoMode.Normal,
            )
            name = name.strip()
            if ok and name:
                if name not in self._counts:
                    self._counts[name] = 0
                    self._refresh_table()

        def _rename_character(self, old_name: str) -> None:
            new_name, ok = QInputDialog.getText(
                self,
                "Rename Character",
                f"Enter new name for '{old_name}' (updates all assigned cues):",
                QLineEdit.EchoMode.Normal,
                old_name,
            )
            new_name = new_name.strip()
            if ok and new_name and new_name != old_name:
                self._renames[old_name] = new_name
                count = self._counts.pop(old_name, 0)
                self._counts[new_name] = self._counts.get(new_name, 0) + count
                if old_name in self._voices:
                    self._voices[new_name] = self._voices.pop(old_name)
                self._refresh_table()

        def _rename_selected(self) -> None:
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.information(self, "Rename Character", "Select a character row first.")
                return
            item = self.table.item(row, 0)
            if item:
                self._rename_character(item.text())

        def _reassign_selected(self) -> None:
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.information(self, "Reassign Cues", "Select a source character row first.")
                return
            item = self.table.item(row, 0)
            if not item:
                return
            source_char = item.text()
            other_chars = [c for c in self._counts if c != source_char]
            if not other_chars:
                QMessageBox.information(self, "Reassign Cues", "No other characters exist to reassign to. Add a character first.")
                return

            target_char, ok = QInputDialog.getItem(
                self,
                "Reassign Cues",
                f"Reassign all cues of '{source_char}' to:",
                other_chars,
                0,
                False,
            )
            if ok and target_char:
                cues_to_move = self._counts.get(source_char, 0)
                self._renames[source_char] = target_char
                self._counts[target_char] = self._counts.get(target_char, 0) + cues_to_move
                self._counts[source_char] = 0
                self._refresh_table()
                QMessageBox.information(
                    self,
                    "Reassignment Staged",
                    f"All cues of '{source_char}' ({cues_to_move} cues) will be reassigned to '{target_char}' upon clicking OK.",
                )

        def _on_accept(self) -> None:
            self.characters_updated.emit(
                {
                    "renames": self._renames,
                    "voices": self._voices,
                    "characters": list(self._counts.keys()),
                }
            )
            self.accept()

        def get_renames(self) -> dict[str, str]:
            return dict(self._renames)

        def get_voices(self) -> dict[str, str]:
            return dict(self._voices)

