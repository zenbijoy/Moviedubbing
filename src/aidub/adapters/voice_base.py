"""Voice engine adapter base interface and shared synthesis contracts."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import LanguageTag

logger = logging.getLogger(__name__)


class VoiceEngineKind(StrEnum):
    EDGE_TTS = "edge_tts"
    F5_TTS = "f5_tts"
    CHATTERBOX = "chatterbox"
    FISH_SPEECH = "fish_speech"
    GEMINI_TTS = "gemini_tts"
    ELEVENLABS = "elevenlabs"
    COSYVOICE = "cosyvoice"
    OPENVOICE = "openvoice"
    QWEN3_TTS = "qwen3_tts"
    TWO_STAGE_CLONER = "two_stage_cloner"
    SYNTHETIC = "synthetic"  # deterministic test stub


class EmotionLabel(StrEnum):
    NEUTRAL = "neutral"
    ANGRY = "angry"
    SAD = "sad"
    FEAR = "fear"
    WHISPER = "whisper"
    SHOUT = "shout"
    JOY = "joy"
    EXCITED = "excited"
    CALM = "calm"
    BREATHLESS = "breathless"


class EngineCapability(StrEnum):
    """Granular feature capabilities supported by a voice engine."""

    TEXT_TO_SPEECH = "text_to_speech"
    REFERENCE_AUDIO_CLONING = "reference_audio_cloning"
    VOICE_DESIGN_PROMPT = "voice_design_prompt"
    EMOTION_CONDITIONING = "emotion_conditioning"
    STYLE_INTENSITY = "style_intensity"
    STREAMING_SYNTHESIS = "streaming_synthesis"
    SPEAKER_CONSISTENCY = "speaker_consistency"
    WORD_TIMESTAMPS = "word_timestamps"
    PITCH_CONTROL = "pitch_control"
    RATE_CONTROL = "rate_control"
    MULTILINGUAL = "multilingual"


class VoiceEngineMetadata(ContractModel):
    """Public transparency, hardware, and capability manifest for an engine."""

    engine_kind: VoiceEngineKind
    display_name: str
    model_id: str
    version: str = "1.0.0"
    capabilities: set[EngineCapability] = Field(default_factory=set)
    supported_languages: list[str] = Field(default_factory=list)
    hardware_requirements: str = "CPU"
    license_info: str = "MIT"
    commercial_use_allowed: bool = True
    min_ram_gb: float = 0.5
    min_vram_gb: float = 0.0
    is_local: bool = True
    is_cloud_api: bool = False
    known_limitations: list[str] = Field(default_factory=list)


class NormalizedPerformance(ContractModel):
    """Normalized, engine-agnostic performance and delivery intent."""

    primary_emotion: EmotionLabel = EmotionLabel.NEUTRAL
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    style_descriptor: str = Field(default="neutral", max_length=64)
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch_shift_semitones: float = Field(default=0.0, ge=-12.0, le=12.0)
    energy_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    pause_after_ms: int = Field(default=0, ge=0, le=10_000)


class VoiceDesignPrompt(ContractModel):
    """Descriptive character attributes for generating a new voice timbre."""

    description: str = Field(default="", max_length=1000)
    gender: str = Field(default="neutral", max_length=32)
    age_range: str = Field(default="adult", max_length=32)
    pitch: str = Field(default="medium", max_length=32)
    timbre: str = Field(default="natural", max_length=64)
    accent: str = Field(default="standard", max_length=64)
    speed: str = Field(default="medium", max_length=32)
    personality: str = Field(default="", max_length=128)


class ReferenceAudioAnalysis(ContractModel):
    """Acoustic inspection report for reference cloning audio."""

    audio_path: str
    duration_s: float = Field(ge=0.0)
    sample_rate: int = Field(ge=8000)
    channels: int = Field(ge=1)
    snr_db: float = Field(ge=0.0)
    has_clipping: bool = False
    silence_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    is_suitable_for_cloning: bool = True
    quality_rating: str = Field(default="good")
    warnings: list[str] = Field(default_factory=list)


class VoiceConsentDeclaration(ContractModel):
    """Explicit legal consent verification for speaker voice cloning."""

    authorized_by: str = Field(min_length=1)
    voice_owner: str = Field(min_length=1)
    is_authorized: bool = True
    timestamp_iso: str = Field(default="")
    consent_notes: str = Field(default="")


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
    performance: NormalizedPerformance | None = None
    voice_design: VoiceDesignPrompt | None = None
    consent: VoiceConsentDeclaration | None = None
    target_duration_ms: int | None = None


class SynthesisResult(ContractModel):
    """Result returned by a voice engine adapter after synthesis."""

    request_id: Identifier
    utterance_id: Identifier
    engine_kind: VoiceEngineKind
    output_path: str
    sample_rate: int = Field(ge=8_000)
    duration_ms: int = Field(ge=0)
    seed_used: int = Field(ge=0)
    applied_controls: list[str] = Field(default_factory=list)
    actual_duration_ms: int = Field(default=0)
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class VoiceEngineError(RuntimeError):
    """Raised when synthesis fails in a voice engine adapter."""

    def __init__(self, engine: str, message: str) -> None:
        super().__init__(f"[{engine}] {message}")
        self.engine = engine


@runtime_checkable
class VoiceEngine(Protocol):
    """Protocol for all TTS voice engine adapters."""

    @property
    def engine_kind(self) -> VoiceEngineKind: ...

    @property
    def metadata(self) -> VoiceEngineMetadata: ...

    def is_available(self) -> tuple[bool, str]: ...

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult: ...

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]: ...

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis: ...


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

    @property
    def metadata(self) -> VoiceEngineMetadata:
        return VoiceEngineMetadata(
            engine_kind=VoiceEngineKind.SYNTHETIC,
            display_name="Synthetic Reference Engine",
            model_id="synthetic-deterministic-v1",
            capabilities={
                EngineCapability.TEXT_TO_SPEECH,
                EngineCapability.REFERENCE_AUDIO_CLONING,
                EngineCapability.VOICE_DESIGN_PROMPT,
                EngineCapability.EMOTION_CONDITIONING,
                EngineCapability.STYLE_INTENSITY,
                EngineCapability.PITCH_CONTROL,
                EngineCapability.RATE_CONTROL,
                EngineCapability.MULTILINGUAL,
            },
            supported_languages=["en-US", "bn-BD", "hi-IN", "es-ES", "ja-JP", "de-DE", "fr-FR"],
            hardware_requirements="CPU, Zero-GPU, < 10MB RAM",
            license_info="MIT",
            commercial_use_allowed=True,
            min_ram_gb=0.1,
            min_vram_gb=0.0,
            is_local=True,
            is_cloud_api=False,
            known_limitations=["Generates synthetic test audio without natural human prosody."],
        )

    def is_available(self) -> tuple[bool, str]:
        return True, "Ready (built-in deterministic test engine)"

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        out_path = Path(output_dir) / f"{request.utterance_id}_{request.seed}.wav"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if request.target_duration_ms and request.target_duration_ms > 0:
            stub_duration_ms = int(request.target_duration_ms)
        else:
            word_count = len(request.text.split())
            base_duration = max(500, word_count * 200)
            stub_duration_ms = int(base_duration / max(0.2, request.pace_multiplier))
        out_path.write_bytes(self._STUB_HEADER + b"\x00" * (stub_duration_ms * 2))

        applied = ["rate", "pitch"]
        if request.emotion != EmotionLabel.NEUTRAL:
            applied.append(f"emotion:{request.emotion.value}")
        if request.reference_audio_path:
            applied.append("reference_conditioning")

        logger.debug("synthetic_voice: wrote %s (%dms)", out_path.name, stub_duration_ms)
        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=VoiceEngineKind.SYNTHETIC,
            output_path=str(out_path),
            sample_rate=request.output_sample_rate,
            duration_ms=stub_duration_ms,
            actual_duration_ms=stub_duration_ms,
            seed_used=request.seed,
            applied_controls=applied,
        )

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]:
        return {
            "voice_id": f"synthetic_{prompt.gender}_{prompt.age_range}_{prompt.pitch}",
            "description": prompt.description,
            "timbre": prompt.timbre,
            "prompt_applied": True,
        }

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis:
        p = Path(audio_path)
        exists = p.is_file()
        size = p.stat().st_size if exists else 0
        dur = max(0.5, size / 32000.0) if exists else 0.0
        snr = 28.5 if dur >= 3.0 else 12.0
        warnings = []
        if dur < 3.0:
            warnings.append("Sample is shorter than recommended 3.0s threshold.")
        return ReferenceAudioAnalysis(
            audio_path=audio_path,
            duration_s=round(dur, 2),
            sample_rate=16000,
            channels=1,
            snr_db=snr,
            has_clipping=False,
            silence_ratio=0.08,
            is_suitable_for_cloning=exists and dur >= 2.0,
            quality_rating="excellent" if dur >= 5.0 and snr > 20 else "good",
            warnings=warnings,
        )


__all__ = [
    "EmotionLabel",
    "EngineCapability",
    "NormalizedPerformance",
    "ReferenceAudioAnalysis",
    "SynthesisRequest",
    "SynthesisResult",
    "SyntheticVoiceEngine",
    "VoiceConsentDeclaration",
    "VoiceDesignPrompt",
    "VoiceEngine",
    "VoiceEngineError",
    "VoiceEngineKind",
    "VoiceEngineMetadata",
]
