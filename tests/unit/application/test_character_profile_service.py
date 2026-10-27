"""Unit tests for CharacterProfileService and cross-scene voice consistency."""

from __future__ import annotations

from pathlib import Path

from aidub.application.voice.character_profile_service import CharacterProfileService
from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile


def test_character_profile_registration_and_lookup(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)

    profile = CharacterVoiceProfile(
        profile_id=Identifier("vp_aragorn"),
        character_id=Identifier("aragorn"),
        display_name="Aragorn",
        consent_authorized=True,
        selected_engine="edge_tts",
        default_voice_id="en-US-GuyNeural",
        authorized_reference_path="aragorn_ref.wav",
    )

    service.register_profile(profile)

    retrieved = service.get_profile("aragorn")
    assert retrieved is not None
    assert retrieved.display_name == "Aragorn"
    assert retrieved.selected_engine == "edge_tts"
    assert retrieved.consent_authorized is True

    # Check persistence to disk
    assert (tmp_path / "aragorn.json").exists()

    # Re-instantiate service from disk
    service2 = CharacterProfileService(storage_dir=tmp_path)
    loaded = service2.get_profile("aragorn")
    assert loaded is not None
    assert loaded.profile_id == "vp_aragorn"


def test_invalidation_impact_analysis(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)

    profile = CharacterVoiceProfile(
        profile_id=Identifier("vp_legolas"),
        character_id=Identifier("legolas"),
        display_name="Legolas",
        consent_authorized=True,
        selected_engine="edge_tts",
        default_voice_id="en-US-GuyNeural",
        authorized_reference_path="legolas_ref_v1.wav",
    )
    service.register_profile(profile)

    # Link two dialogue takes across scenes
    service.link_take(
        character_id="legolas",
        utterance_id="utt_scene1_01",
        scene_id="scene_01",
        audio_path="scene1_take.wav",
        engine_kind="edge_tts",
        voice_id="en-US-GuyNeural",
    )
    service.link_take(
        character_id="legolas",
        utterance_id="utt_scene3_05",
        scene_id="scene_03",
        audio_path="scene3_take.wav",
        engine_kind="edge_tts",
        voice_id="en-US-GuyNeural",
    )

    # 1. No change -> no invalidation
    invalidates, affected = service.check_invalidation_impact(
        character_id="legolas",
        new_engine="edge_tts",
        new_voice_id="en-US-GuyNeural",
        new_reference_path="legolas_ref_v1.wav",
    )
    assert invalidates is False
    assert len(affected) == 0

    # 2. Changing engine to elevenlabs -> invalidation triggered!
    invalidates, affected = service.check_invalidation_impact(
        character_id="legolas",
        new_engine="elevenlabs",
    )
    assert invalidates is True
    assert set(affected) == {"utt_scene1_01", "utt_scene3_05"}

    # 3. Mark takes stale
    stale_count = service.mark_takes_stale("legolas")
    assert stale_count == 2

    # Now already stale, so check_invalidation_impact returns 0 active affected
    invalidates2, affected2 = service.check_invalidation_impact(
        character_id="legolas",
        new_engine="elevenlabs",
    )
    assert invalidates2 is False
    assert len(affected2) == 0


def test_remove_profile(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)
    profile = CharacterVoiceProfile(
        profile_id=Identifier("vp_gimli"),
        character_id=Identifier("gimli"),
        display_name="Gimli",
    )
    service.register_profile(profile)
    assert service.get_profile("gimli") is not None
    assert (tmp_path / "gimli.json").exists()

    removed = service.remove_profile("gimli")
    assert removed is True
    assert service.get_profile("gimli") is None
    assert not (tmp_path / "gimli.json").exists()


def test_profile_versioning_and_history(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)
    profile = CharacterVoiceProfile(
        profile_id=Identifier("vp_frodo"),
        character_id=Identifier("frodo"),
        display_name="Frodo Baggins",
        selected_engine="edge_tts",
        default_voice_id="en-US-GuyNeural",
    )
    service.register_profile(profile)
    assert profile.version == 1
    assert len(profile.history) == 0

    # Link take
    service.link_take(
        character_id="frodo",
        utterance_id="utt_frodo_01",
        scene_id="scene_01",
        audio_path="frodo_v1.wav",
        engine_kind="edge_tts",
    )

    # Update profile through service
    updated, affected = service.update_profile(
        character_id="frodo",
        updates={"selected_engine": "elevenlabs", "default_voice_id": "eleven_frodo"},
        change_summary="Upgraded to ElevenLabs expressive model",
    )
    assert updated is not None
    assert updated.version == 2
    assert len(updated.history) == 1
    assert updated.history[0].version == 1
    assert "ElevenLabs" in updated.history[0].change_summary
    assert affected == ["utt_frodo_01"]

    # Takes should now be stale
    stale_takes = service.get_affected_takes("frodo")
    assert len(stale_takes) == 1
    assert stale_takes[0].utterance_id == "utt_frodo_01"


def test_atomic_take_replacement_and_rollback(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)

    orig_audio = tmp_path / "orig.wav"
    orig_audio.write_bytes(b"RIFF....WAVEfmt....data....original")

    service.link_take(
        character_id="samwise",
        utterance_id="utt_sam_01",
        scene_id="scene_01",
        audio_path=str(orig_audio),
        engine_kind="edge_tts",
    )

    # 1. Attempt invalid replacement (file does not exist)
    failed = service.atomic_replace_take("utt_sam_01", str(tmp_path / "nonexistent.wav"))
    assert failed is False
    take = service.get_character_takes("samwise")[0]
    assert take.audio_path == str(orig_audio)  # Preserved!
    assert take.version == 1

    # 2. Attempt invalid replacement (zero-size file)
    empty_file = tmp_path / "empty.wav"
    empty_file.write_bytes(b"")
    failed_empty = service.atomic_replace_take("utt_sam_01", str(empty_file))
    assert failed_empty is False
    assert take.audio_path == str(orig_audio)  # Still preserved!

    # 3. Successful atomic replacement
    new_audio = tmp_path / "new_take.wav"
    new_audio.write_bytes(b"RIFF....WAVEfmt....data....new_audio_take")
    success = service.atomic_replace_take("utt_sam_01", str(new_audio))
    assert success is True
    assert take.audio_path == str(new_audio)
    assert take.previous_audio_path == str(orig_audio)
    assert take.version == 2

    # 4. Rollback to previous audio
    rolled_back = service.rollback_take("utt_sam_01")
    assert rolled_back is True
    assert take.audio_path == str(orig_audio)
    assert take.is_stale is True


def test_regenerate_take_failure_preserves_audio(tmp_path: Path) -> None:
    service = CharacterProfileService(storage_dir=tmp_path)

    initial_audio = tmp_path / "initial.wav"
    initial_audio.write_bytes(b"RIFF....WAVEfmt....data....initial")

    service.link_take(
        character_id="gandalf",
        utterance_id="utt_gandalf_01",
        scene_id="scene_02",
        audio_path=str(initial_audio),
        engine_kind="edge_tts",
    )

    def faulty_synthesizer(_take):
        raise RuntimeError("Cloud TTS network timeout!")

    # Attempt regeneration with failing synthesizer
    success = service.regenerate_take("utt_gandalf_01", faulty_synthesizer)
    assert success is False
    take = service.get_character_takes("gandalf")[0]
    assert take.audio_path == str(initial_audio)  # Preserved!

