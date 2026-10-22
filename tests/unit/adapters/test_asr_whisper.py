from __future__ import annotations

import pytest

from aidub.adapters.asr_whisper import FasterWhisperAdapter, FasterWhisperOptions
from aidub.domain.identifiers import MediaAssetId, ProjectId
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.domain.types import LanguageTag, Sha256
from aidub.speech.contracts import SpeechRecognitionRequest
from aidub.speech.runtime import NullRecognitionRuntime


def make_asr_request() -> SpeechRecognitionRequest:
    audio_range = AudioSampleRange(
        start=AudioSamplePosition(sample_index=0, sample_rate=48_000),
        sample_count=480_000,
    )
    return SpeechRecognitionRequest(
        request_id="req_asr_001",
        project_id=ProjectId("prj_asr_test"),
        media_asset_id=MediaAssetId("med_audio_001"),
        source_audio_sha256=Sha256(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        language=LanguageTag("en-US"),
        full_audio_range=audio_range,
        audio_range=audio_range,
        chunk_index=0,
        chunk_count=1,
    )


def test_faster_whisper_options_validation() -> None:
    options = FasterWhisperOptions(
        model_size="medium",
        device="cpu",
        compute_type="float32",
        beam_size=3,
        vad_filter=True,
    )
    assert options.model_size == "medium"
    assert options.device == "cpu"

    with pytest.raises(ValueError, match="unsupported compute type"):
        FasterWhisperOptions(compute_type="invalid_type")

    with pytest.raises(ValueError, match="unsupported device"):
        FasterWhisperOptions(device="tpu")


def test_faster_whisper_adapter_recognition() -> None:
    adapter = FasterWhisperAdapter(FasterWhisperOptions(device="cpu", compute_type="float32"))
    request = make_asr_request()
    runtime = NullRecognitionRuntime()

    with pytest.raises(RuntimeError, match="real source_audio_path"):
        adapter.recognize(request, runtime=runtime)
