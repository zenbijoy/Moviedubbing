from __future__ import annotations

import pytest

from aidub.adapters.diarization_pyannote import (
    DiarizedSpeakerSegment,
    PyannoteDiarizationAdapter,
    PyannoteDiarizationOptions,
    cluster_speaker_embeddings,
)
from aidub.contracts.base import Identifier
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.domain.types import Sha256


def make_audio_range() -> AudioSampleRange:
    return AudioSampleRange(
        start=AudioSamplePosition(sample_index=0, sample_rate=48_000),
        sample_count=480_000,
    )


def test_pyannote_options_validation() -> None:
    options = PyannoteDiarizationOptions(
        model_id="pyannote/speaker-diarization-3.1",
        device="cpu",
        num_speakers=2,
    )
    assert options.device == "cpu"
    assert options.num_speakers == 2

    with pytest.raises(ValueError, match="min_speakers cannot exceed max_speakers"):
        PyannoteDiarizationOptions(min_speakers=4, max_speakers=2)


def test_pyannote_adapter_diarization() -> None:
    adapter = PyannoteDiarizationAdapter(PyannoteDiarizationOptions(device="cpu"))
    audio_range = make_audio_range()
    source_sha = Sha256("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    with pytest.raises(RuntimeError, match="real source_audio_path"):
        adapter.diarize(audio_range, source_sha)


def test_cluster_speaker_embeddings() -> None:
    range1 = AudioSampleRange(
        start=AudioSamplePosition(sample_index=0, sample_rate=48_000),
        sample_count=48_000,
    )
    range2 = AudioSampleRange(
        start=AudioSamplePosition(sample_index=48_000, sample_rate=48_000),
        sample_count=48_000,
    )
    range3 = AudioSampleRange(
        start=AudioSamplePosition(sample_index=96_000, sample_rate=48_000),
        sample_count=48_000,
    )

    # Segment 1 and Segment 3 have very similar embeddings
    seg1 = DiarizedSpeakerSegment(
        segment_id=Identifier("seg_1"),
        speaker_id=Identifier("spk_a"),
        audio_range=range1,
        confidence=0.9,
        embedding=(1.0, 0.0, 0.0),
    )
    seg2 = DiarizedSpeakerSegment(
        segment_id=Identifier("seg_2"),
        speaker_id=Identifier("spk_b"),
        audio_range=range2,
        confidence=0.9,
        embedding=(0.0, 1.0, 0.0),
    )
    seg3 = DiarizedSpeakerSegment(
        segment_id=Identifier("seg_3"),
        speaker_id=Identifier("spk_c"),
        audio_range=range3,
        confidence=0.9,
        embedding=(0.99, 0.05, 0.0),
    )

    clustered = cluster_speaker_embeddings((seg1, seg2, seg3), threshold=0.8)

    assert len(clustered) == 3
    # Seg 1 and Seg 3 should be clustered into the same canonical speaker ID
    assert clustered[0].speaker_id == clustered[2].speaker_id
    assert clustered[0].speaker_id != clustered[1].speaker_id
