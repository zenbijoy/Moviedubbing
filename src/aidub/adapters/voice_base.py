"""Voice engine adapter base interface and shared synthesis contracts."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import LanguageTag

logger = logging.getLogger(__name__)


class VoiceEngineKind(StrEnum):
    EDGE_TTS = "edge_tts"
    F5_TTS = "f5_tts"
    CHATTERBOX = "chatterbox"
    FISH_SPEECH = "fish_speech"
    SYNTHETIC = "synthetic"  # deterministic test stub


class EmotionLabel(StrEnum):
    NEUTRAL = "neutral"
    ANGRY = "angry"
    SAD = "sad"
    FEAR = "fear"
    WHISPER = "whisper"
    SHOUT = "shout"
    JOY = "joy"


class SynthesisRequest(ContractModel):
    """Single-utterance TTS synthesis request."""

    request_id: Identifier
    utterance_id: Identifier
    voice_profile_id: Identifier
    text: str = Field(min_length=1, max_length=8_000)
    language: LanguageTag
    emotion: EmotionLabel = EmotionLabel.NEUTRAL
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    pace_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch_shift_semitones: float = Field(default=0.0, ge=-12.0, le=12.0)
    seed: int = Field(default=42, ge=0)
    reference_audio_path: str = Field(default="", max_length=2_048)
    output_sample_rate: int = Field(default=48_000, ge=8_000, le=96_000)


class SynthesisResult(ContractModel):
    """Result returned by a voice engine adapter after synthesis."""

    request_id: Identifier
    utterance_id: Identifier
    engine_kind: VoiceEngineKind
    output_path: str
    sample_rate: int = Field(ge=8_000)
    duration_ms: int = Field(ge=0)
    seed_used: int = Field(ge=0)


class VoiceEngineError(RuntimeError):
    """Raised when synthesis fails in a voice engine adapter."""

    def __init__(self, engine: str, message: str) -> None:
        super().__init__(f"[{engine}] {message}")
        self.engine = engine


@runtime_checkable
class VoiceEngine(Protocol):
    """Protocol for all TTS voice engine adapters."""

    @property
    def engine_kind(self) -> VoiceEngineKind:
        ...

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        ...


class SyntheticVoiceEngine:
    """
    Deterministic synthetic voice engine for test environments.

    Writes a stub WAV header to disk without requiring GPU or network access.
    Output is deterministic per (text, seed) pair.
    """

    _STUB_HEADER = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\xbb\x00\x00\x00\x77\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.SYNTHETIC

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        out_path = Path(output_dir) / f"{request.utterance_id}_{request.seed}.wav"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Estimate 200ms per word as stub duration
        word_count = len(request.text.split())
        stub_duration_ms = max(500, word_count * 200)
        out_path.write_bytes(self._STUB_HEADER + b"\x00" * (stub_duration_ms * 2))

        logger.debug(
            "synthetic_voice: wrote %s (%dms)", out_path.name, stub_duration_ms
        )
        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=VoiceEngineKind.SYNTHETIC,
            output_path=str(out_path),
            sample_rate=request.output_sample_rate,
            duration_ms=stub_duration_ms,
            seed_used=request.seed,
        )


__all__ = [
    "EmotionLabel",
    "SynthesisRequest",
    "SynthesisResult",
    "SyntheticVoiceEngine",
    "VoiceEngine",
    "VoiceEngineError",
    "VoiceEngineKind",
]
