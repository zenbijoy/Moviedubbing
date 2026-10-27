"""Unit tests for DialogueQCService."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from aidub.analysis.dialogue_qc_service import (
    DialogueQCService,
    QCIssueType,
    QCSeverity,
)
from aidub.application.voice.scene_performance_service import (
    CandidateTake,
    DialogueCuePerformance,
)
from aidub.contracts.base import Identifier


def _create_wav(
    path: Path,
    duration_s: float = 1.0,
    sample_rate: int = 48000,
    channels: int = 1,
    amplitude: float = 0.5,
    is_silent: bool = False,
    boundary_dc: float = 0.0,
) -> Path:
    """Helper to generate deterministic WAV files for QC tests."""
    n_frames = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        samples = []
        for i in range(n_frames):
            if is_silent:
                val = 0
            else:
                t = float(i) / sample_rate
                # 440 Hz tone
                val = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * 440.0 * t))

            # Optional boundary DC offset
            if (i == 0 or i == n_frames - 1) and boundary_dc > 0.0:
                val = int(boundary_dc * 32767.0)

            val = max(-32768, min(32767, val))
            samples.append(val)
            if channels == 2:
                samples.append(val)

        raw = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(raw)

    return path


def test_qc_detects_missing_and_empty_file(tmp_path: Path) -> None:
    service = DialogueQCService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_empty"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("aragorn"),
        speaker_id=Identifier("spk_1"),
        source_text="Hold your ground!",
        target_text="নিজের জায়গা ধরে রাখো!",
        target_duration_s=2.0,
    )

    # 1. No audio associated
    report_none = service.inspect_cue(cue)
    assert report_none.passed is False
    assert report_none.can_deliver is False
    assert any(i.issue_type == QCIssueType.MISSING_OR_EMPTY_AUDIO for i in report_none.issues)

    # 2. 0-byte file
    zero_file = tmp_path / "zero.wav"
    zero_file.write_bytes(b"")
    report_zero = service.inspect_cue(cue, audio_path=str(zero_file))
    assert report_zero.passed is False
    assert report_zero.can_deliver is False
    assert any(i.severity == QCSeverity.HARD_ERROR for i in report_zero.issues)


def test_qc_detects_dead_silence(tmp_path: Path) -> None:
    service = DialogueQCService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_silent"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("legolas"),
        speaker_id=Identifier("spk_2"),
        source_text="They're taking the hobbits to Isengard!",
        target_text="তারা হবিটদের আইসেনগার্দে নিয়ে যাচ্ছে!",
        target_duration_s=2.5,
    )

    silent_wav = _create_wav(tmp_path / "silent.wav", duration_s=1.5, is_silent=True)
    report = service.inspect_cue(cue, audio_path=str(silent_wav))

    assert report.passed is False
    assert report.can_deliver is False  # Hard error!
    assert any(i.issue_type == QCIssueType.DEAD_SILENCE for i in report.issues)
    assert report.silence_ratio >= 0.98


def test_qc_detects_clipping_and_excessive_peaks(tmp_path: Path) -> None:
    service = DialogueQCService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_clipped"),
        scene_id=Identifier("sc_01"),
        character_id=Identifier("gimli"),
        speaker_id=Identifier("spk_3"),
        source_text="And my axe!",
        target_text="এবং আমার কুঠার!",
        target_duration_s=1.5,
    )

    # Amplitude 1.0 -> hits 32767 -> clipping
    clipped_wav = _create_wav(tmp_path / "clipped.wav", duration_s=1.0, amplitude=1.0)
    report = service.inspect_cue(cue, audio_path=str(clipped_wav))

    assert report.passed is False
    assert report.can_deliver is True  # Warning, non-blocking
    assert any(i.issue_type == QCIssueType.DIGITAL_CLIPPING for i in report.issues)
    assert any("peak normalization" in i.actionable_repair.lower() for i in report.issues)


def test_qc_detects_duration_overrun_and_timing_overlap(tmp_path: Path) -> None:
    service = DialogueQCService()

    cue1 = DialogueCuePerformance(
        cue_id=Identifier("cue_overrun_1"),
        scene_id=Identifier("sc_02"),
        character_id=Identifier("frodo"),
        speaker_id=Identifier("spk_4"),
        source_text="I will take the Ring.",
        target_text="আমি আংটিটি নেব।",
        start_s=10.0,
        end_s=12.0,
        target_duration_s=2.0,
    )
    cue2 = DialogueCuePerformance(
        cue_id=Identifier("cue_overrun_2"),
        scene_id=Identifier("sc_02"),
        character_id=Identifier("elrond"),
        speaker_id=Identifier("spk_5"),
        source_text="Though I do not know the way.",
        target_text="যদিও আমি পথ জানি না।",
        start_s=13.0,
        end_s=15.0,
        target_duration_s=2.0,
    )

    # Actual duration is 3.5s (Target was 2.0s -> 75% overrun! And ends at 10.0 + 3.5 = 13.5s, overlapping cue2 at 13.0s)
    long_wav = _create_wav(tmp_path / "long.wav", duration_s=3.5, amplitude=0.4)
    report = service.inspect_cue(cue1, audio_path=str(long_wav), next_cue=cue2)

    assert report.passed is False
    # Should flag both DURATION_OVERRUN and TIMING_OVERLAP
    issue_types = {i.issue_type for i in report.issues}
    assert QCIssueType.DURATION_OVERRUN in issue_types
    assert QCIssueType.TIMING_OVERLAP in issue_types
    assert any("adaptive duration fitting" in i.actionable_repair.lower() for i in report.issues)


def test_qc_detects_boundary_discontinuity(tmp_path: Path) -> None:
    service = DialogueQCService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_click"),
        scene_id=Identifier("sc_03"),
        character_id=Identifier("sam"),
        speaker_id=Identifier("spk_6"),
        source_text="Don't turn me into anything unnatural.",
        target_text="আমাকে অস্বাভাবিক কিছু বানাবেন না।",
        target_duration_s=2.0,
    )

    click_wav = _create_wav(tmp_path / "click.wav", duration_s=1.0, amplitude=0.3, boundary_dc=0.3)
    report = service.inspect_cue(cue, audio_path=str(click_wav))

    assert any(i.issue_type == QCIssueType.BOUNDARY_DISCONTINUITY for i in report.issues)
    assert any("micro-fade" in i.actionable_repair.lower() for i in report.issues)


def test_qc_detects_stale_audio(tmp_path: Path) -> None:
    service = DialogueQCService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_stale"),
        scene_id=Identifier("sc_04"),
        character_id=Identifier("gollum"),
        speaker_id=Identifier("spk_7"),
        source_text="My precious...",
        target_text="আমার প্রিয়...",
        target_duration_s=1.0,
    )

    clean_wav = _create_wav(tmp_path / "clean.wav", duration_s=1.0, amplitude=0.4)
    report = service.inspect_cue(cue, audio_path=str(clean_wav), is_stale=True)

    assert report.passed is False
    assert any(i.issue_type == QCIssueType.STALE_AUDIO for i in report.issues)


def test_batch_qc_inspection(tmp_path: Path) -> None:
    service = DialogueQCService()

    wav1 = _create_wav(tmp_path / "cue1.wav", duration_s=2.0, amplitude=0.5)
    wav2 = _create_wav(tmp_path / "cue2.wav", duration_s=1.5, is_silent=True)  # Defect

    cue1 = DialogueCuePerformance(
        cue_id=Identifier("cue_b1"),
        scene_id=Identifier("sc_05"),
        character_id=Identifier("boromir"),
        speaker_id=Identifier("spk_8"),
        source_text="It is a gift.",
        target_text="এটা একটা উপহার।",
        start_s=0.0,
        end_s=2.0,
        target_duration_s=2.0,
    )
    cue1.candidate_takes.append(CandidateTake(take_id="take_1", audio_path=str(wav1), duration_s=2.0))
    cue1.selected_take_id = "take_1"

    cue2 = DialogueCuePerformance(
        cue_id=Identifier("cue_b2"),
        scene_id=Identifier("sc_05"),
        character_id=Identifier("aragorn"),
        speaker_id=Identifier("spk_9"),
        source_text="We cannot use it.",
        target_text="আমরা এটা ব্যবহার করতে পারি না।",
        start_s=2.5,
        end_s=4.0,
        target_duration_s=1.5,
    )
    cue2.candidate_takes.append(CandidateTake(take_id="take_1", audio_path=str(wav2), duration_s=1.5))
    cue2.selected_take_id = "take_1"

    batch_report = service.inspect_batch([cue1, cue2])
    assert batch_report.total_cues == 2
    assert batch_report.passed_cues == 1
    assert batch_report.hard_errors_count == 1  # From dead silence in cue2
    assert batch_report.can_deliver is False
