"""Unit tests for Mel-Band Roformer source separation adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from aidub.adapters.separation_demucs import SeparatedStem, SourceSeparationResult, StemKind
from aidub.adapters.separation_roformer import (
    RoformerSeparationAdapter,
    RoformerSeparationOptions,
)
from aidub.contracts.base import Identifier
from aidub.domain.types import SemanticVersion, Sha256
from aidub.speech.contracts import SpeechEngineIdentity


def test_roformer_options_validation() -> None:
    opts = RoformerSeparationOptions(
        model_name="mel_band_roformer_karaoke",
        device="cuda",
        shifts=2,
        overlap=0.3,
    )
    assert opts.model_name == "mel_band_roformer_karaoke"
    assert opts.device == "cuda"
    assert opts.shifts == 2

    # Invalid device
    with pytest.raises(ValidationError):
        RoformerSeparationOptions(device="vpu")


def test_roformer_adapter_identity() -> None:
    adapter = RoformerSeparationAdapter()
    assert adapter.identity.engine_id == Identifier("mel-band-roformer")
    assert adapter.identity.engine_version == SemanticVersion("1.0.0")


def test_roformer_separate_file_not_found(tmp_path: Path) -> None:
    adapter = RoformerSeparationAdapter(RoformerSeparationOptions(device="cpu"))
    with pytest.raises(FileNotFoundError):
        adapter.separate(str(tmp_path / "nonexistent.wav"), str(tmp_path / "out"))


def test_roformer_separate_fallback_execution(tmp_path: Path) -> None:
    adapter = RoformerSeparationAdapter(RoformerSeparationOptions(device="cpu"))
    fake_source = tmp_path / "source.wav"
    fake_source.write_bytes(b"dummy RIFF audio")

    # Mock DemucsSeparationAdapter to return a valid result
    mock_stems = (
        SeparatedStem(stem_kind=StemKind.DIALOGUE, stem_path=str(tmp_path / "vocals.wav"), sample_rate=44100, channels=2, sample_count=44100),
        SeparatedStem(stem_kind=StemKind.MUSIC, stem_path=str(tmp_path / "music.wav"), sample_rate=44100, channels=2, sample_count=44100),
    )
    mock_res = SourceSeparationResult(
        engine=SpeechEngineIdentity(
            engine_id=Identifier("demucs-separation"),
            engine_version=SemanticVersion("4.0.0"),
            model_id=Identifier("htdemucs"),
            model_version=SemanticVersion("4.0.0"),
            model_weights_sha256=Sha256("abc" * 21 + "a"),
        ),
        stems=mock_stems,
        me_preserved=True,
    )

    with patch("aidub.adapters.separation_demucs.DemucsSeparationAdapter.separate", return_value=mock_res):
        res = adapter.separate(str(fake_source), str(tmp_path / "out"))

    assert res.me_preserved is True
    assert res.get_stem(StemKind.DIALOGUE) is not None
    assert res.get_stem(StemKind.MUSIC) is not None
