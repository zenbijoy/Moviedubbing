"""Unit tests for ScenePerformanceService and candidate take auditioning."""

from __future__ import annotations

from pathlib import Path

from aidub.adapters.voice_base import (
    EmotionLabel,
    EngineCapability,
    SyntheticVoiceEngine,
)
from aidub.application.voice.scene_performance_service import (
    DialogueCuePerformance,
    SceneContext,
    ScenePerformanceService,
)
from aidub.contracts.base import Identifier


def test_scene_context_and_cue_registration() -> None:
    service = ScenePerformanceService()

    scene = SceneContext(
        scene_id=Identifier("scene_03"),
        name="Council of Elrond",
        dramatic_tone="tense",
        acoustic_environment="hall",
        default_emotion="serious",
        default_intensity=0.8,
    )
    service.register_scene(scene)

    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_101"),
        scene_id=Identifier("scene_03"),
        character_id=Identifier("boromir"),
        speaker_id=Identifier("spk_01"),
        source_text="One does not simply walk into Mordor.",
        target_text="কেউ সহজে মরডোরে হেঁটে যেতে পারে না।",
        start_s=12.5,
        end_s=16.0,
        target_duration_s=3.5,
        per_line_emotion="whisper",
        pause_after_ms=300,
    )
    service.register_cue(cue)

    retrieved_scene = service.get_scene("scene_03")
    assert retrieved_scene is not None
    assert retrieved_scene.dramatic_tone == "tense"

    retrieved_cue = service.get_cue("cue_101")
    assert retrieved_cue is not None
    assert retrieved_cue.per_line_emotion == "whisper"
    assert retrieved_cue.target_duration_s == 3.5


def test_resolve_effective_performance_capability_fallback() -> None:
    service = ScenePerformanceService()

    scene = SceneContext(
        scene_id=Identifier("scene_01"),
        name="Prologue",
        dramatic_tone="epic",
        default_emotion="calm",
    )
    service.register_scene(scene)

    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_01"),
        scene_id=Identifier("scene_01"),
        character_id=Identifier("galadriel"),
        speaker_id=Identifier("spk_02"),
        source_text="The world is changed.",
        target_text="পৃথিবী বদলে গেছে।",
        per_line_emotion="whisper",
        per_line_intensity=0.9,
    )
    service.register_cue(cue)

    # 1. Engine WITHOUT emotion or style capabilities
    basic_caps = {EngineCapability.TEXT_TO_SPEECH}
    norm, applied, fallbacks = service.resolve_effective_performance("cue_01", basic_caps)
    assert norm.primary_emotion == EmotionLabel.NEUTRAL
    assert norm.emotion_intensity == 0.5
    assert "whisper" not in applied.get("emotion", "")
    assert len(fallbacks) >= 1
    assert any("does not support emotion" in f for f in fallbacks)

    # 2. Engine WITH emotion and style capabilities
    full_caps = {
        EngineCapability.TEXT_TO_SPEECH,
        EngineCapability.EMOTION_CONDITIONING,
        EngineCapability.STYLE_INTENSITY,
    }
    norm_full, applied_full, fallbacks_full = service.resolve_effective_performance("cue_01", full_caps)
    assert norm_full.primary_emotion == EmotionLabel.WHISPER
    assert norm_full.emotion_intensity == 0.9
    assert applied_full["emotion"] == "whisper"
    assert applied_full["emotion_intensity"] == 0.9
    assert len(fallbacks_full) == 0


def test_candidate_takes_audition_and_approval(tmp_path: Path) -> None:
    service = ScenePerformanceService()

    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_201"),
        scene_id=Identifier("scene_battle"),
        character_id=Identifier("theoden"),
        speaker_id=Identifier("spk_03"),
        source_text="Ride now, ride for ruin!",
        target_text="এখন এগিয়ে চলো, সর্বনাশের দিকে এগিয়ে চলো!",
        target_duration_s=3.0,
    )
    service.register_cue(cue)

    take1_path = tmp_path / "take1.wav"
    take1_path.write_bytes(b"RIFF....take1")
    take1 = service.add_candidate_take(
        cue_id="cue_201",
        audio_path=str(take1_path),
        duration_s=2.8,
        applied_parameters={"emotion": "excited", "intensity": 0.8},
        fallback_notes=[],
    )
    assert take1.take_id == "take_1"
    assert cue.selected_take_id == "take_1"

    # Add Take 2
    take2_path = tmp_path / "take2.wav"
    take2_path.write_bytes(b"RIFF....take2")
    take2 = service.add_candidate_take(
        cue_id="cue_201",
        audio_path=str(take2_path),
        duration_s=3.1,
        applied_parameters={"emotion": "shout", "intensity": 1.0},
        fallback_notes=[],
    )
    assert take2.take_id == "take_2"

    # Audition comparison
    comparison = service.get_audition_comparison("cue_201", "take_1", "take_2")
    assert comparison["cue_id"] == "cue_201"
    assert comparison["take_a"]["take_id"] == "take_1"
    assert comparison["take_b"]["take_id"] == "take_2"

    # Approve Take 2
    approved = service.approve_take("cue_201", "take_2")
    assert approved is True
    assert cue.selected_take_id == "take_2"
    assert take2.is_approved is True
    assert cue.validation_status == "validated"

    # Reject Take 1
    rejected = service.reject_take("cue_201", "take_1", reason="Lacks battle energy")
    assert rejected is True
    assert take1.is_rejected is True
    assert take1.rejection_reason == "Lacks battle energy"


def test_regenerate_single_line_isolated(tmp_path: Path) -> None:
    service = ScenePerformanceService()
    cue = DialogueCuePerformance(
        cue_id=Identifier("cue_regen"),
        scene_id=Identifier("scene_peace"),
        character_id=Identifier("sam"),
        speaker_id=Identifier("spk_04"),
        source_text="There's some good in this world.",
        target_text="এই পৃথিবীতে এখনও কিছু ভালো অবশিষ্ট আছে।",
        target_duration_s=2.5,
    )
    service.register_cue(cue)

    engine = SyntheticVoiceEngine()
    candidate = service.regenerate_single_line(
        cue_id="cue_regen",
        voice_engine=engine,
        voice_id="synth_voice_1",
        output_dir=tmp_path,
    )

    assert candidate.take_id == "take_1"
    assert Path(candidate.audio_path).exists()
    assert cue.selected_take_id == "take_1"
    assert candidate.duration_s > 0.0
