"""
Unit tests for Movie Character Recognition, Diarization, and Studio Integration:
- Text speaker tag extraction & identifier sanitization
- CharacterDetectionEngine detection from segments, cues, and media
- CharacterDetectionWorker background thread execution and signals
- CharacterManagerDialog UI inspection, auto-detection, rename, and cue reassignment
- TimelineScreen per-cue character tracking, inspector updates, voice assignment, and continuity
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from aidub.ai.voice.character_cloning_engine import (
    CharacterDetectionEngine,
    MovieCharacter,
    extract_speaker_from_cue_text,
    sanitize_identifier,
)
from aidub.contracts.base import Identifier
from aidub.ui.character_manager_dialog import CharacterManagerDialog
from aidub.ui.screens.timeline_editor import TimelineScreen
from aidub.ui.workers import CharacterDetectionWorker


def test_extract_speaker_from_cue_text() -> None:
    # Bracketed speaker tags
    spk, rem = extract_speaker_from_cue_text("[SPEAKER_00] Welcome to the show.")
    assert spk == "SPEAKER_00"
    assert rem == "Welcome to the show."

    spk, rem = extract_speaker_from_cue_text("[John]: What is happening?")
    assert spk == "John"
    assert rem == "What is happening?"

    # Colon speaker tags
    spk, rem = extract_speaker_from_cue_text("COBB: We must go deeper.")
    assert spk == "COBB"
    assert rem == "We must go deeper."

    # Arrow or hyphen speaker tags
    spk, rem = extract_speaker_from_cue_text(">> NARRATOR: Once upon a time.")
    assert spk == "NARRATOR"
    assert rem == "Once upon a time."

    spk, rem = extract_speaker_from_cue_text("- Alice: Good morning.")
    assert spk == "Alice"
    assert rem == "Good morning."

    # Plain text without speaker tag
    spk, rem = extract_speaker_from_cue_text("This is an ordinary sentence without speaker.")
    assert spk is None
    assert rem == "This is an ordinary sentence without speaker."


def test_sanitize_identifier_no_validation_crash() -> None:
    # Strings with spaces, punctuation, or special chars must not crash Pydantic Identifier
    id1 = sanitize_identifier("John Doe")
    assert isinstance(id1, Identifier)
    assert id1 == "John_Doe"

    id2 = sanitize_identifier("Dr. Smith (Lead)")
    assert isinstance(id2, Identifier)
    assert "Dr._Smith" in id2

    id3 = sanitize_identifier("   ")
    assert isinstance(id3, Identifier)
    assert id3 == "speaker_00"

    # Verify MovieCharacter model accepts sanitized ID
    char = MovieCharacter(
        character_id=id1,
        canonical_name="John Doe",
    )
    assert char.character_id == "John_Doe"
    assert char.canonical_name == "John Doe"


def test_character_detection_engine_with_real_names() -> None:
    engine = CharacterDetectionEngine()
    segments = [
        {"speaker": "John Doe", "character": "John Doe", "text": "Hello there."},
        {"speaker": "Ariadne", "name": "Ariadne", "text": "Are you sure?"},
        {"speaker": "SPEAKER_00", "text": "Unknown speaker line."},
    ]
    characters = engine.detect_movie_characters(segments)
    names = {c.canonical_name for c in characters}
    assert "John Doe" in names
    assert "Ariadne" in names
    assert "Speaker SPEAKER_00" in names

    # Test detection from subtitle cues
    cues = [
        ("S1", 1.0, 2.0, "[Cobb] We have to leave.", None),
        ("S1", 3.5, 2.0, "MAL: Don't trust him.", None),
        ("S1", 6.0, 2.0, "Just background audio.", None),
    ]
    detected = engine.detect_from_subtitle_cues(cues)
    det_names = {c.canonical_name for c in detected}
    assert "Cobb" in det_names
    assert "MAL" in det_names


def test_character_detection_worker_signals() -> None:
    cues = [
        ("S1", 0.0, 2.0, "[SPEAKER_00] Line one.", None),
        ("S1", 3.0, 2.0, "[SPEAKER_01] Line two.", None),
    ]
    worker = CharacterDetectionWorker(
        subtitle_cues=cues,
        target_language="bn",
    )

    detected_chars: list[Any] = []
    diar_data: list[Any] = []
    progress_calls: list[tuple[int, str]] = []

    worker.characters_detected.connect(lambda chars: detected_chars.extend(chars))
    worker.diarization_completed.connect(lambda t, n, r: diar_data.append((t, n, r)))
    worker.progress_updated.connect(lambda p, m: progress_calls.append((p, m)))

    # Run directly in test thread
    worker.run()

    assert len(detected_chars) == 2
    names = {c.canonical_name for c in detected_chars}
    assert "SPEAKER_00" in names or "Speaker SPEAKER_00" in names
    assert "SPEAKER_01" in names or "Speaker SPEAKER_01" in names
    assert len(diar_data) == 1
    assert len(progress_calls) >= 1


def test_character_manager_dialog_auto_detect_and_reassign(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)

    app = QApplication.instance() or QApplication([])
    clips = [
        ("S1", 1.0, 2.0, "[Hero] I will protect you.", None),
        ("S1", 3.0, 2.0, "[Hero] Stay back.", None),
        ("S1", 6.0, 2.0, "[Villain] You cannot stop me.", None),
    ]
    dlg = CharacterManagerDialog(
        clips=clips,
    )
    try:
        # Trigger auto-detect
        dlg._auto_detect_characters()
        assert "Hero" in dlg._counts
        assert "Villain" in dlg._counts
        assert dlg._counts["Hero"] == 2
        assert dlg._counts["Villain"] == 1

        # Test renaming Hero -> "Captain"
        dlg._renames["Hero"] = "Captain"
        count = dlg._counts.pop("Hero")
        dlg._counts["Captain"] = count
        dlg._refresh_table()

        assert "Captain" in dlg._counts
        assert dlg._counts["Captain"] == 2
        assert dlg.get_renames() == {"Hero": "Captain"}
    finally:
        dlg.close()
        app.processEvents()


def test_timeline_screen_per_cue_character_tracking(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Create a sample subtitle file with distinct characters
        srt_file = tmp_path / "movie_subtitles.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n[Cobb] We need an architect.\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\n[Ariadne] What kind of architect?\n\n"
            "3\n00:00:07,000 --> 00:00:09,000\n[Cobb] Someone who can build dreams.\n\n",
            encoding="utf-8",
        )

        screen.import_subtitle_file(str(srt_file), track_id="S1")
        app.processEvents()

        # Check per-cue characters are recognized
        clip_chars = screen._current_project_data.get("clip_characters", {})
        assert len(clip_chars) >= 2
        assert "Cobb" in clip_chars.values()
        assert "Ariadne" in clip_chars.values()

        # Accurate count per character
        counts = screen._compute_character_counts()
        assert counts.get("Cobb") == 2
        assert counts.get("Ariadne") == 1

        # When clicking cue 1 (Cobb)
        screen._on_timeline_clip_clicked(
            {
                "tid": "S1",
                "start": 1.0,
                "dur": 2.0,
                "label": "[Cobb] We need an architect.",
            }
        )
        app.processEvents()
        assert screen.inspector_panel.char_in.currentText() == "Cobb"

        # When clicking cue 2 (Ariadne)
        screen._on_timeline_clip_clicked(
            {
                "tid": "S1",
                "start": 4.0,
                "dur": 2.0,
                "label": "[Ariadne] What kind of architect?",
            }
        )
        app.processEvents()
        assert screen.inspector_panel.char_in.currentText() == "Ariadne"

        # Change character on cue 2 to "Arthur"
        screen._on_character_changed("Arthur")
        app.processEvents()
        key_cue2 = "S1:4.0"
        assert screen._current_project_data["clip_characters"][key_cue2] == "Arthur"

        # Re-compute counts reflects Arthur
        new_counts = screen._compute_character_counts()
        assert new_counts.get("Cobb") == 2
        assert new_counts.get("Arthur") == 1
        assert "Ariadne" not in new_counts

        # Test renaming Arthur -> "Arthur_Renamed" via _on_characters_updated
        screen._on_characters_updated(
            {
                "renames": {"Arthur": "Arthur_Renamed"},
                "voices": {"Arthur_Renamed": "bn-BD-PradeepNeural"},
                "characters": ["Cobb", "Arthur_Renamed"],
            }
        )
        app.processEvents()
        assert screen._current_project_data["clip_characters"][key_cue2] == "Arthur_Renamed"
        assert (
            screen._current_project_data["character_voices"]["Arthur_Renamed"]
            == "bn-BD-PradeepNeural"
        )
    finally:
        screen.close()
        app.processEvents()


def test_timeline_screen_auto_detect_characters_action() -> None:
    app = QApplication.instance() or QApplication([])
    screen = TimelineScreen()
    try:
        # Set sample clips with speaker tags
        screen._current_project_data["clips"] = [
            ("S1", 0.5, 2.0, "COBB: Wake up.", None),
            ("S1", 3.0, 2.0, "MAL: Not yet.", None),
            ("S1", 5.5, 2.0, "COBB: It is time.", None),
        ]
        detected = screen.auto_detect_characters()
        assert "COBB" in detected
        assert "MAL" in detected
        assert "COBB" in screen._current_project_data["character_voices"]
        assert "MAL" in screen._current_project_data["character_voices"]
        assert screen.inspector_panel.meta_chars_lbl.text() == "2 speakers"
    finally:
        screen.close()
        app.processEvents()
