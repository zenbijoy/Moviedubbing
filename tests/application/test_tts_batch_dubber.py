"""Unit tests for BatchDubber multi-provider TTS, Voice Clone Profiles, and ETA Telemetry."""

from __future__ import annotations

import time
import pytest

from aidub.application.batch.batch_dubber import (
    BatchDubber,
    BatchProgress,
    DubCue,
    DubResult,
    TtsProvider,
    VoiceCloneProfile,
)


def test_voice_clone_profile_validation() -> None:
    profile = VoiceCloneProfile(
        profile_id="lead_actor",
        speaker_name="Protagonist Voice",
        reference_wav_path="samples/voice_ref.wav",
        similarity_boost=0.85,
        stability=0.70,
        pitch_offset_semitones=-1.5,
    )
    assert profile.profile_id == "lead_actor"
    assert profile.speaker_name == "Protagonist Voice"
    assert profile.similarity_boost == 0.85
    assert profile.pitch_offset_semitones == -1.5


def test_batch_progress_telemetry_structure() -> None:
    prog = BatchProgress(
        total_cues=10,
        completed_cues=5,
        successful_cues=5,
        failed_cues=0,
        percent_complete=50.0,
        items_per_second=2.0,
        estimated_time_remaining_s=2.5,
    )
    assert prog.total_cues == 10
    assert prog.completed_cues == 5
    assert prog.percent_complete == 50.0
    assert prog.estimated_time_remaining_s == 2.5


def test_batch_dubber_multi_provider_and_cloning(tmp_path) -> None:
    dubber = BatchDubber(output_dir=tmp_path, default_provider=TtsProvider.LOCAL_FALLBACK)
    profile = VoiceCloneProfile(
        profile_id="spk_hero",
        speaker_name="Hero",
        pitch_offset_semitones=0.5,
    )

    cues = [
        DubCue(cue_id="cue_01", text="নমস্কার, স্বাগতম।", clone_profile=profile, target_duration_s=2.0),
        DubCue(cue_id="cue_02", text="আমরা শুরু করছি।", clone_profile=profile, target_duration_s=1.5),
    ]

    progress_events: list[BatchProgress] = []
    results = dubber.run(cues, progress_callback=lambda p: progress_events.append(p))

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is True
    assert results[0].audio_path is not None
    assert results[1].audio_path is not None
    assert len(progress_events) >= 2
    assert progress_events[-1].completed_cues == 2
    assert progress_events[-1].percent_complete == 100.0
