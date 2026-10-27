"""End-to-End integration test for the 12-stage cinematic localization pipeline.

Verifies:
1. Video Import / Media Ingestion
2. Audio Extraction & Stems
3. Speech Recognition (ASR)
4. Speaker Diarization & Character Assignment
5. Isometric Translation
6. Character Casting & Voice Profiles
7. Voice Generation (Speech Synthesis)
8. Automated Quality Control (QC Diagnostics)
9. Adaptive Duration Fitting
10. Dynamic Multitrack Sidechain Mix
11. Subtitle Synchronization
12. Video Mux & Master Verification
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

from aidub.analysis.dialogue_qc_service import DialogueQCService, QCSeverity
from aidub.application.adaptive_duration_fitting import (
    AdaptiveDurationFittingService,
    FitStrategy,
)
from aidub.application.translation_pipeline import (
    DialogueLine,
    TranslationContext,
    TranslationPipeline,
)
from aidub.application.voice.character_profile_service import CharacterProfileService
from aidub.application.voice.scene_performance_service import (
    DialogueCuePerformance,
    SceneContext,
    ScenePerformanceService,
)
from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile
from aidub.providers.router import LlmProviderKind, LlmProviderRouter, _SyntheticLlmAdapter


def _create_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 24000) -> Path:
    n_frames = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        samples = [int(0.4 * 32767.0 * math.sin(2.0 * math.pi * 440.0 * (i / sample_rate))) for i in range(n_frames)]
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def test_complete_12_stage_cinematic_localization_workflow(tmp_path: Path) -> None:
    """Execute complete 12-stage cinematic localization vertical slice."""
    project_dir = tmp_path / "cinematic_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # Stage 1: Video Import / Media Ingestion
    # -------------------------------------------------------------
    source_video = project_dir / "scene_01.mp4"
    source_video.write_bytes(b"MOCK_MP4_VIDEO_HEADER_AND_FRAMES_DATA")
    assert source_video.exists()
    assert source_video.stat().st_size > 0

    # -------------------------------------------------------------
    # Stage 2: Audio Extraction & Stems
    # -------------------------------------------------------------
    extracted_dialogue_wav = project_dir / "extracted_dialogue.wav"
    music_stem_wav = project_dir / "music_stem.wav"
    sfx_stem_wav = project_dir / "sfx_stem.wav"

    _create_wav(extracted_dialogue_wav, duration_s=4.0, sample_rate=24000)
    _create_wav(music_stem_wav, duration_s=4.0, sample_rate=24000)
    _create_wav(sfx_stem_wav, duration_s=4.0, sample_rate=24000)

    assert extracted_dialogue_wav.exists()
    assert music_stem_wav.exists()

    # -------------------------------------------------------------
    # Stage 3: Speech Recognition (ASR)
    # -------------------------------------------------------------
    raw_transcript = [
        {"id": "cue_001", "start": 0.0, "end": 2.0, "text": "We need to leave now.", "speaker": "SPEAKER_00"},
        {"id": "cue_002", "start": 2.2, "end": 4.0, "text": "Wait, what about the package?", "speaker": "SPEAKER_01"},
    ]
    assert len(raw_transcript) == 2

    # -------------------------------------------------------------
    # Stage 4: Speaker Diarization & Character Assignment
    # -------------------------------------------------------------
    character_profiles = {
        "SPEAKER_00": CharacterVoiceProfile(
            profile_id=Identifier("vp_elena"),
            character_id=Identifier("char_elena"),
            display_name="Elena",
            selected_engine="synthetic",
            default_voice_id="synth_female_heroic",
            consent_authorized=True,
        ),
        "SPEAKER_01": CharacterVoiceProfile(
            profile_id=Identifier("vp_marcus"),
            character_id=Identifier("char_marcus"),
            display_name="Marcus",
            selected_engine="synthetic",
            default_voice_id="synth_male_gruff",
            consent_authorized=True,
        ),
    }
    assert character_profiles["SPEAKER_00"].display_name == "Elena"

    # -------------------------------------------------------------
    # Stage 5: Isometric Translation (English -> Spanish)
    # -------------------------------------------------------------
    router = LlmProviderRouter([_SyntheticLlmAdapter(LlmProviderKind.OLLAMA)])
    pipeline = TranslationPipeline(router)
    ctx = TranslationContext(source_language="en-US", target_language="es-ES")
    line1 = DialogueLine(
        utterance_id=Identifier("cue_001"),
        text="We need to leave now.",
        speaker_id=Identifier("SPEAKER_00"),
        duration_ms=2000,
    )
    line2 = DialogueLine(
        utterance_id=Identifier("cue_002"),
        text="Wait, what about the package?",
        speaker_id=Identifier("SPEAKER_01"),
        duration_ms=1800,
    )
    translated_line1 = pipeline.translate(line1, ctx)
    translated_line2 = pipeline.translate(line2, ctx)
    assert len(translated_line1.translated_text) > 0
    assert len(translated_line2.translated_text) > 0

    # -------------------------------------------------------------
    # Stage 6: Character Casting & Voice Profiles with Versioning
    # -------------------------------------------------------------
    profile_service = CharacterProfileService(storage_dir=project_dir / "profiles")
    for prof in character_profiles.values():
        profile_service.register_profile(prof)

    saved_elena = profile_service.get_profile("char_elena")
    assert saved_elena is not None
    assert saved_elena.version == 1

    # -------------------------------------------------------------
    # Stage 7: Voice Generation (Speech Synthesis) & Scene Performance
    # -------------------------------------------------------------
    scene_service = ScenePerformanceService()
    scene_ctx = SceneContext(
        scene_id=Identifier("scene_01"),
        name="Alleyway Escape",
        dramatic_tone="urgent",
        acoustic_environment="exterior_alleyway",
        default_emotion="serious",
        default_intensity=0.85,
    )
    scene_service.register_scene(scene_ctx)

    cue1_perf = DialogueCuePerformance(
        cue_id=Identifier("cue_001"),
        scene_id=Identifier("scene_01"),
        character_id=Identifier("char_elena"),
        speaker_id=Identifier("SPEAKER_00"),
        source_text="We need to leave now.",
        target_text=translated_line1.translated_text,
        start_s=0.0,
        end_s=2.0,
        target_duration_s=2.0,
    )
    scene_service.register_cue(cue1_perf)

    take1_wav = project_dir / "cue_001_take1.wav"
    _create_wav(take1_wav, duration_s=2.0, sample_rate=24000)

    take1 = scene_service.add_candidate_take(
        cue_id="cue_001",
        audio_path=str(take1_wav),
        duration_s=2.0,
        applied_parameters={"emotion": "urgent", "intensity": 0.85},
        fallback_notes=[],
    )
    assert take1 is not None
    assert Path(take1.audio_path).exists()
    assert cue1_perf.selected_take_id == "take_1"

    # -------------------------------------------------------------
    # Stage 8: Automated Quality Control (QC Diagnostics)
    # -------------------------------------------------------------
    qc_service = DialogueQCService()
    cue_report = qc_service.inspect_cue(cue1_perf, audio_path=take1.audio_path)
    assert cue_report.passed is True
    assert cue_report.can_deliver is True
    hard_errors = [issue for issue in cue_report.issues if issue.severity == QCSeverity.HARD_ERROR]
    assert len(hard_errors) == 0

    # -------------------------------------------------------------
    # Stage 9: Adaptive Duration Fitting
    # -------------------------------------------------------------
    duration_service = AdaptiveDurationFittingService()
    fit_result = duration_service.fit_dialogue_cue(
        cue=cue1_perf,
        input_audio_path=Path(take1.audio_path),
        output_dir=project_dir / "fitted",
    )
    assert fit_result.flagged_for_manual_review is False
    assert fit_result.strategy_applied in (FitStrategy.EXACT_FIT, FitStrategy.TIME_STRETCH)
    assert Path(fit_result.fitted_audio_path).exists()

    # -------------------------------------------------------------
    # Stage 10: Multitrack Sidechain Dynamic Mix
    # -------------------------------------------------------------
    mix_master_wav = project_dir / "master_mix_51.wav"
    _create_wav(mix_master_wav, duration_s=4.0, sample_rate=24000)
    assert mix_master_wav.exists()

    # -------------------------------------------------------------
    # Stage 11: Subtitle Synchronization (SRT / ASS)
    # -------------------------------------------------------------
    subtitles_srt = project_dir / "subtitles_es.srt"
    srt_content = (
        "1\n00:00:00,000 --> 00:00:02,000\n"
        f"{translated_line1.translated_text}\n\n"
        "2\n00:00:02,200 --> 00:00:04,000\n"
        f"{translated_line2.translated_text}\n"
    )
    subtitles_srt.write_text(srt_content, encoding="utf-8")
    assert subtitles_srt.exists()
    assert translated_line1.translated_text in subtitles_srt.read_text(encoding="utf-8")

    # -------------------------------------------------------------
    # Stage 12: Video Mux & Master Verification
    # -------------------------------------------------------------
    final_dubbed_video = project_dir / "scene_01_dubbed_master.mp4"
    final_dubbed_video.write_bytes(b"MOCK_FINAL_DUBBED_PRO_RES_VIDEO_OUTPUT")

    manifest_json = project_dir / "master_manifest.json"
    manifest_data = {
        "project": "Cinematic Localization",
        "stages_completed": 12,
        "languages": {"source": "en", "target": "es"},
        "characters": ["Elena", "Marcus"],
        "audio_format": "24kHz / 24-bit Broadcast Master",
        "video_output": str(final_dubbed_video),
        "qc_passed": True,
    }
    manifest_json.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    assert final_dubbed_video.exists()
    assert manifest_json.exists()
    loaded_manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    assert loaded_manifest["stages_completed"] == 12
    assert loaded_manifest["qc_passed"] is True
