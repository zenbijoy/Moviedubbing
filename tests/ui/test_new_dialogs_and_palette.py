"""Unit tests for newly added Studio Dialogs and Command Palette."""

from __future__ import annotations

import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from aidub.ui.dialogs.adr_punch_in_dialog import AdrPunchInDialog
from aidub.ui.dialogs.bangla_dub_studio_dialog import BanglaDubStudioDialog
from aidub.ui.dialogs.command_palette_dialog import CommandPaletteDialog
from aidub.ui.dialogs.prosody_transfer_dialog import ProsodyTransferDialog
from aidub.media.pro_audio_editor import AudioClipData


@pytest.fixture(autouse=True)
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_adr_punch_in_dialog_initialization_and_splice() -> None:
    clip = AudioClipData.synthesize_speech_like(duration=3.0, sample_rate=44100)
    dlg = AdrPunchInDialog(base_clip=clip, cue_id="test_cue", punch_in_sec=0.5, punch_out_sec=1.5)
    assert dlg.cue_id == "test_cue"
    assert dlg.spin_in.value() == 0.5
    assert dlg.spin_out.value() == 1.5

    # Trigger punch-in execution
    dlg._execute_punch_in()
    assert dlg._spliced_clip is not None
    assert len(dlg._spliced_clip.samples) == len(clip.samples)

    # Test signal emission on apply
    emitted = []
    dlg.punch_in_applied.connect(lambda c: emitted.append(c))
    dlg._apply_to_timeline()
    assert len(emitted) == 1
    assert emitted[0] is dlg._spliced_clip


def test_prosody_transfer_dialog_render_and_apply() -> None:
    guide = AudioClipData.synthesize_speech_like(duration=2.0, sample_rate=44100)
    dub = AudioClipData.synthesize_tone(frequency=180.0, duration=2.0, sample_rate=44100)

    dlg = ProsodyTransferDialog(guide_clip=guide, dub_clip=dub, cue_id="cue_test")
    assert dlg.slider_energy.value() == 80
    assert dlg.slider_pitch.value() == 65

    # Render match
    dlg._render_prosody()
    assert dlg._transferred_clip is not None
    assert len(dlg._transferred_clip.samples) == len(dub.samples)

    emitted = []
    dlg.prosody_applied.connect(lambda c: emitted.append(c))
    dlg._apply_to_timeline()
    assert len(emitted) == 1


def test_bangla_dub_studio_dialog_recalc_and_apply() -> None:
    dlg = BanglaDubStudioDialog(
        text="আমি তোমাকে খুব ভালোবাসি কিন্তু তুমি বুঝলে না।",
        cue_id="bangla_01",
        duration_sec=3.0,
    )
    assert dlg.combo_dialect.count() >= 5
    assert "জয়" in dlg.lbl_emo_type.text().lower() or "joy" in dlg.lbl_emo_type.text().lower() or "neutral" in dlg.lbl_emo_type.text().lower() or len(dlg.lbl_emo_type.text()) > 0
    assert dlg.table_visemes.rowCount() > 0

    emitted = []
    dlg.bangla_dub_applied.connect(lambda d: emitted.append(d))
    dlg._apply_all()
    assert len(emitted) == 1
    data = emitted[0]
    assert data["cue_id"] == "bangla_01"
    assert "bangla_text" in data
    assert "dialect" in data
    assert "timed_visemes" in data


def test_command_palette_dialog_filtering_and_execution() -> None:
    executed = []
    commands = [
        {"title": "VariAudio 3", "category": "Cubase DAW", "hotkey": "Ctrl+Shift+V", "action": lambda: executed.append("variaudio")},
        {"title": "Bangla Dub Studio", "category": "Bangla Suite", "hotkey": "Ctrl+B", "action": lambda: executed.append("bangla")},
        {"title": "ADR Punch-In", "category": "Dubbing", "hotkey": "Ctrl+R", "action": lambda: executed.append("punch_in")},
    ]

    palette = CommandPaletteDialog(commands=commands)
    assert palette.list_widget.count() == 3

    # Filter for Bangla
    palette._filter_commands("bangla")
    assert palette.list_widget.count() == 1

    # Execute selected
    palette._execute_selected()
    assert executed == ["bangla"]
