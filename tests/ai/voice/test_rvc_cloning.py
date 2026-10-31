"""
Unit tests for RVC v2 Voice Conversion, Spectral Timbre Transfer,
and Two-Stage Character Voice Cloning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf

from aidub.ai.voice.character_cloning_engine import (
    CharacterVoiceCloningUnavailableError,
    CharacterVoiceToneCloningEngine,
    MovieCharacter,
)
from aidub.ai.voice.rvc_cloning_engine import (
    NativeSpectralTimbreMatcher,
    RvcVoiceConversionAdapter,
)
from aidub.application.voice.consent_guard import PermissionDeniedError
from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import (
    CharacterVoiceProfile,
    ReferenceBank,
    ReferenceQualityReport,
    ReferenceQualityTier,
    ReferenceSample,
)


@pytest.fixture
def test_audio_stems(tmp_path: Path) -> dict[str, Path]:
    sr = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # Base synthetic voice (220 Hz)
    src_data = 0.3 * np.sin(2 * np.pi * 220.0 * t)
    src_path = tmp_path / "base_tts.wav"
    sf.write(src_path, src_data.astype(np.float32), sr)

    # Actor reference sample (150 Hz with harmonics)
    ref_data = 0.4 * np.sin(2 * np.pi * 150.0 * t) + 0.2 * np.sin(2 * np.pi * 300.0 * t)
    ref_path = tmp_path / "actor_ref.wav"
    sf.write(ref_path, ref_data.astype(np.float32), sr)

    return {"base": src_path, "ref": ref_path}


def test_native_spectral_timbre_transfer(test_audio_stems: dict[str, Path], tmp_path: Path) -> None:
    matcher = NativeSpectralTimbreMatcher()
    out_file = tmp_path / "transferred.wav"

    matcher.transfer_timbre(
        source_audio_path=test_audio_stems["base"],
        reference_audio_paths=[test_audio_stems["ref"]],
        output_wav_path=out_file,
        f0_shift_semitones=-2.0,
    )

    assert out_file.is_file()
    assert out_file.stat().st_size > 1000
    with sf.SoundFile(str(out_file)) as f:
        assert f.samplerate == 16000
        assert f.frames > 0


def test_rvc_adapter_with_references(test_audio_stems: dict[str, Path], tmp_path: Path) -> None:
    adapter = RvcVoiceConversionAdapter()
    out_file = tmp_path / "rvc_output.wav"

    adapter.convert_timbre(
        base_tts_audio_path=test_audio_stems["base"],
        output_converted_path=out_file,
        reference_audio_paths=[test_audio_stems["ref"]],
    )

    assert out_file.is_file()
    assert out_file.stat().st_size > 1000


def test_rvc_adapter_rejects_unauthorized_profile(
    test_audio_stems: dict[str, Path], tmp_path: Path
) -> None:
    adapter = RvcVoiceConversionAdapter()
    out_file = tmp_path / "unauth.wav"

    unauthorized_profile = CharacterVoiceProfile(
        profile_id=Identifier("prof_01"),
        character_id=Identifier("char_01"),
        display_name="Actor",
        consent_authorized=False,
    )

    with pytest.raises(PermissionDeniedError, match="Voice cloning prohibited"):
        adapter.convert_timbre(
            base_tts_audio_path=test_audio_stems["base"],
            output_converted_path=out_file,
            character_profile=unauthorized_profile,
        )


def test_rvc_adapter_authorized_profile_extracts_references(
    test_audio_stems: dict[str, Path], tmp_path: Path
) -> None:
    adapter = RvcVoiceConversionAdapter()
    out_file = tmp_path / "auth.wav"

    sample = ReferenceSample(
        sample_id=Identifier("samp_01"),
        character_id=Identifier("char_01"),
        audio_file_path=str(test_audio_stems["ref"]),
        duration_s=1.0,
        quality_report=ReferenceQualityReport(
            sample_id=Identifier("samp_01"),
            speech_duration_s=1.0,
            snr_db=25.0,
            overlapping_speech_score=0.0,
            background_music_score=0.0,
            reverb_score=0.1,
            phonetic_coverage=0.9,
            quality_score=92.0,
            tier=ReferenceQualityTier.EXCELLENT_REFERENCE,
            recommendation="Golden reference",
        ),
    )
    bank = ReferenceBank(
        character_id=Identifier("char_01"),
        references=[sample],
    )
    authorized_profile = CharacterVoiceProfile(
        profile_id=Identifier("prof_02"),
        character_id=Identifier("char_02"),
        display_name="Authorized Actor",
        consent_authorized=True,
        reference_banks={"neutral": bank},
    )

    adapter.convert_timbre(
        base_tts_audio_path=test_audio_stems["base"],
        output_converted_path=out_file,
        character_profile=authorized_profile,
    )
    assert out_file.is_file()


def test_two_stage_cloning_engine_success(
    test_audio_stems: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MockEdgeTTS:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def synthesize_to_file(self, text: str, path: Path | str, **kwargs: Any) -> None:
            sr = 16000
            t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
            sf.write(str(path), (0.2 * np.sin(2 * np.pi * 200.0 * t)).astype(np.float32), sr)

    monkeypatch.setattr("aidub.adapters.voice.edge_tts_adapter.EdgeTTSAdapter", MockEdgeTTS)

    char = MovieCharacter(
        character_id=Identifier("HERO_01"),
        canonical_name="Protagonist",
        recommended_base_voice="bn-BD-PradeepNeural",
        reference_audio_paths=[str(test_audio_stems["ref"])],
    )

    engine = CharacterVoiceToneCloningEngine()
    out_file = tmp_path / "cloned_hero.wav"

    result = engine.clone_character_utterance(
        character=char,
        bengali_text="আমরা এখনই যাচ্ছি",
        output_wav_path=out_file,
    )

    assert result["status"] == "success"
    assert out_file.is_file()
    assert result["stage_b_engine"] == "rvc_v2_timbre_transfer"


def test_two_stage_cloning_engine_fails_without_backend_or_refs(tmp_path: Path) -> None:
    char = MovieCharacter(
        character_id=Identifier("EXTRA_01"),
        canonical_name="Background Extra",
        reference_audio_paths=[],
    )
    engine = CharacterVoiceToneCloningEngine()
    out_file = tmp_path / "fail.wav"

    with pytest.raises(CharacterVoiceCloningUnavailableError, match="no consent-aware RVC"):
        engine.clone_character_utterance(
            character=char,
            bengali_text="কিছু না",
            output_wav_path=out_file,
        )
