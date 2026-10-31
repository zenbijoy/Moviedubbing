"""Unit tests for BatchDialogueOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aidub.application.batch_dialogue_orchestrator import (
    BatchDialogueOrchestrator,
    BatchStage,
    compute_dialogue_fingerprint,
)
from aidub.application.voice.scene_performance_service import (
    DialogueCuePerformance,
)
from aidub.contracts.base import Identifier


def test_dialogue_input_fingerprinting() -> None:
    fp1 = compute_dialogue_fingerprint("Hello world", "voice_1", "synthetic", pace=1.0)
    fp2 = compute_dialogue_fingerprint("Hello world", "voice_1", "synthetic", pace=1.0)
    assert fp1 == fp2  # Deterministic!

    # Changing text changes fingerprint
    fp_text_change = compute_dialogue_fingerprint("Hello world!", "voice_1", "synthetic", pace=1.0)
    assert fp1 != fp_text_change

    # Changing voice changes fingerprint
    fp_voice_change = compute_dialogue_fingerprint("Hello world", "voice_2", "synthetic", pace=1.0)
    assert fp1 != fp_voice_change


def test_batch_execution_and_resumption(tmp_path: Path) -> None:
    orchestrator = BatchDialogueOrchestrator(output_dir=tmp_path / "batch_out")

    cues = [
        DialogueCuePerformance(
            cue_id=Identifier("cue_01"),
            scene_id=Identifier("sc_01"),
            character_id=Identifier("frodo"),
            speaker_id=Identifier("spk_1"),
            source_text="I will take it.",
            target_text="আমি এটা নেব।",
            target_duration_s=1.5,
        ),
        DialogueCuePerformance(
            cue_id=Identifier("cue_02"),
            scene_id=Identifier("sc_01"),
            character_id=Identifier("sam"),
            speaker_id=Identifier("spk_2"),
            source_text="I am coming with you.",
            target_text="আমি আপনার সাথে আসছি।",
            target_duration_s=2.0,
        ),
    ]

    character_voices = {
        "frodo": ("synthetic", "synth_frodo"),
        "sam": ("synthetic", "synth_sam"),
    }

    # 1. First run: processes both cues to completion
    state1 = orchestrator.process_batch(cues, character_voices)
    assert state1.current_stage == BatchStage.COMPLETED
    assert state1.completed_cues == 2
    assert state1.failed_cues == 0

    item1 = state1.items["cue_01"]
    assert item1.is_completed is True
    assert Path(item1.audio_path).exists()
    assert Path(item1.fitted_audio_path).exists()

    # 2. Resumption run: Nothing changed, should skip re-synthesis
    orchestrator2 = BatchDialogueOrchestrator(output_dir=tmp_path / "batch_out")
    progress_log = []

    def mock_progress(stage, cur, total, msg):
        progress_log.append(msg)

    state2 = orchestrator2.process_batch(cues, character_voices, progress_callback=mock_progress)
    assert state2.current_stage == BatchStage.COMPLETED
    assert any("Reused cached take" in log for log in progress_log)

    # 3. Edit text of cue_01 -> Invalidate cue_01 and re-synthesize
    cues[0].target_text = "আমি অবশ্যই আংটিটি নেব।"
    state3 = orchestrator2.process_batch(cues, character_voices)
    assert state3.current_stage == BatchStage.COMPLETED
    item1_updated = state3.items["cue_01"]
    assert item1_updated.is_completed is True


def test_batch_cancellation(tmp_path: Path) -> None:
    orchestrator = BatchDialogueOrchestrator(output_dir=tmp_path / "batch_cancel")
    cues = [
        DialogueCuePerformance(
            cue_id=Identifier("cue_c1"),
            scene_id=Identifier("sc_01"),
            character_id=Identifier("aragorn"),
            speaker_id=Identifier("spk_1"),
            source_text="For Frodo.",
            target_text="ফ্রোডোর জন্য।",
            target_duration_s=1.0,
        )
    ]
    character_voices = {"aragorn": ("synthetic", "synth_aragorn")}

    # Cancel immediately
    orchestrator.cancel()
    assert orchestrator.is_cancelled is True

    state = orchestrator.process_batch(cues, character_voices)
    assert state.current_stage == BatchStage.CANCELLED


def test_batch_preflight_disk_space_check(tmp_path: Path) -> None:
    orchestrator = BatchDialogueOrchestrator(output_dir=tmp_path / "batch_disk")
    cues = [
        DialogueCuePerformance(
            cue_id=Identifier("cue_d1"),
            scene_id=Identifier("sc_01"),
            character_id=Identifier("gimli"),
            speaker_id=Identifier("spk_2"),
            source_text="Baruk Khazad!",
            target_text="বারুক খাজাদ!",
            target_duration_s=1.0,
        )
    ]
    character_voices = {"gimli": ("synthetic", "synth_gimli")}

    # Mock registry to report only 0.5 GB free
    orchestrator.registry.get_disk_free_gb = MagicMock(return_value=0.5)

    with pytest.raises(RuntimeError, match="Insufficient disk space"):
        orchestrator.process_batch(cues, character_voices)
