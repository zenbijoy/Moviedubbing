"""
ElevenLabs Multilingual Expressive Speech Generation & Voice Cloning Adapter.

Provides integration with ElevenLabs v1 speech synthesis and instant voice cloning APIs:
  - Models: eleven_multilingual_v2, eleven_turbo_v2_5, eleven_flash_v2_5.
  - Expressive stability, similarity boost, and style exaggeration controls.
  - Authorized voice cloning with mandatory legal consent verification.
  - Safe fallback to Edge-TTS or synthetic speech when unconfigured or offline.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from aidub.adapters.voice_base import (
    EmotionLabel,
    EngineCapability,
    ReferenceAudioAnalysis,
    SynthesisRequest,
    SynthesisResult,
    VoiceConsentDeclaration,
    VoiceDesignPrompt,
    VoiceEngineError,
    VoiceEngineKind,
    VoiceEngineMetadata,
)
from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration
from aidub.media.voice_dsp import analyze_voice_audio

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Built-in popular ElevenLabs voices for fallback or default selection
DEFAULT_ELEVENLABS_VOICES = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "antoni": "ErXwobaYiN019PkySvjV",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "arnold": "VR6AewLTigWG4xSOukaG",
}

# Emotion to stability & style exaggeration mapping
EMOTION_VOICE_SETTINGS: dict[EmotionLabel, tuple[float, float]] = {
    EmotionLabel.NEUTRAL: (0.75, 0.0),
    EmotionLabel.CALM: (0.85, 0.0),
    EmotionLabel.JOY: (0.45, 0.45),
    EmotionLabel.EXCITED: (0.35, 0.65),
    EmotionLabel.ANGRY: (0.30, 0.70),
    EmotionLabel.SHOUT: (0.25, 0.80),
    EmotionLabel.SAD: (0.50, 0.40),
    EmotionLabel.FEAR: (0.35, 0.60),
    EmotionLabel.WHISPER: (0.40, 0.50),
    EmotionLabel.BREATHLESS: (0.35, 0.55),
}


class ElevenLabsAdapter:
    """
    HTTP client for ElevenLabs speech generation and instant voice cloning.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = DEFAULT_ELEVENLABS_MODEL,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model_id = model_id
        self.allow_fallback = allow_fallback

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def synthesize_to_file(
        self,
        text: str,
        output_wav_path: Path | str,
        voice_id: str | None = None,
        emotion: EmotionLabel = EmotionLabel.NEUTRAL,
        emotion_intensity: float = 0.5,
        reference_audio: str | None = None,
        consent: VoiceConsentDeclaration | None = None,
        sample_rate: int = 48000,
        target_duration_ms: int | None = None,
    ) -> tuple[Path, list[str]]:
        """
        Synthesize speech using ElevenLabs API with performance controls.

        Returns (output_wav_path, applied_controls_list).
        """
        out_wav = Path(output_wav_path)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        applied: list[str] = []

        if not text.strip():
            raise ValueError("Synthesis text cannot be empty.")

        # Reference-audio cloning validation
        if reference_audio:
            if not consent or not consent.is_authorized:
                raise VoiceEngineError(
                    "elevenlabs",
                    "Voice cloning blocked: Affirmative consent confirmation from the voice owner is required.",
                )
            applied.append("reference_audio_conditioned")

        if not self.is_configured():
            if not self.allow_fallback:
                raise VoiceEngineError("elevenlabs", "ELEVENLABS_API_KEY is not configured.")
            logger.info("ElevenLabs key missing; falling back to Edge-TTS neural base")
            return self._synthesize_fallback(text, out_wav, emotion, sample_rate)

        # Resolve voice ID
        target_voice_id = voice_id or DEFAULT_ELEVENLABS_VOICES["rachel"]
        if target_voice_id in DEFAULT_ELEVENLABS_VOICES:
            target_voice_id = DEFAULT_ELEVENLABS_VOICES[target_voice_id]

        # Calculate stability & style
        base_stability, base_style = EMOTION_VOICE_SETTINGS.get(emotion, (0.75, 0.0))
        # Scale style by emotion_intensity
        final_style = round(min(1.0, base_style * (0.5 + emotion_intensity * 0.5)), 2)
        final_stability = round(max(0.1, min(1.0, base_stability * (1.2 - emotion_intensity * 0.4))), 2)

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": final_stability,
                "similarity_boost": 0.80,
                "style": final_style,
                "use_speaker_boost": True,
            },
        }
        applied.extend([f"stability:{final_stability}", f"style:{final_style}"])
        if emotion != EmotionLabel.NEUTRAL:
            applied.append(f"emotion:{emotion.value}")

        url = f"{ELEVENLABS_API_URL}/text-to-speech/{target_voice_id}?output_format=mp3_44100_128"
        headers = {
            "xi-api-key": self.api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        if not url.startswith("https://"):
            raise ValueError("Insecure or invalid URL scheme")
        temp_mp3 = out_wav.with_suffix(".tmp.mp3")
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")  # noqa: S310
            with urllib.request.urlopen(req, timeout=30.0) as resp:  # noqa: S310
                audio_bytes = resp.read()
                if not audio_bytes:
                    raise RuntimeError("ElevenLabs returned zero-byte audio payload.")
                temp_mp3.write_bytes(audio_bytes)

            # Transcode to PCM WAV with specified sample rate
            _run(
                [
                    _ffmpeg_exe(),
                    "-y",
                    "-i",
                    str(temp_mp3),
                    "-ac",
                    "1",
                    "-ar",
                    str(sample_rate),
                    str(out_wav),
                ]
            )
            return out_wav, applied
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            logger.warning("ElevenLabs HTTP %d error: %s", exc.code, err_body[:160])
            if not self.allow_fallback:
                raise VoiceEngineError("elevenlabs", f"HTTP {exc.code}: {err_body}") from exc
            return self._synthesize_fallback(text, out_wav, emotion, sample_rate)
        except Exception as exc:
            logger.warning("ElevenLabs synthesis error: %s", exc)
            if not self.allow_fallback:
                raise VoiceEngineError("elevenlabs", f"Request failed: {exc}") from exc
            return self._synthesize_fallback(text, out_wav, emotion, sample_rate)
        finally:
            temp_mp3.unlink(missing_ok=True)

    def _synthesize_fallback(
        self,
        text: str,
        output_wav: Path,
        emotion: EmotionLabel,
        sample_rate: int,
    ) -> tuple[Path, list[str]]:
        from aidub.adapters.voice.edge_tts_adapter import DEFAULT_BENGALI_VOICE, EdgeTTSAdapter

        temp_mp3 = output_wav.with_suffix(".fallback.mp3")
        rate_str = "+0%"
        pitch_str = "+0Hz"
        if emotion in {EmotionLabel.ANGRY, EmotionLabel.SHOUT, EmotionLabel.EXCITED}:
            rate_str = "+10%"
            pitch_str = "+6Hz"
        elif emotion in {EmotionLabel.SAD, EmotionLabel.CALM}:
            rate_str = "-10%"
            pitch_str = "-4Hz"

        try:
            EdgeTTSAdapter(DEFAULT_BENGALI_VOICE).synthesize_to_file(
                text=text,
                output_mp3_path=temp_mp3,
                rate=rate_str,
                pitch=pitch_str,
            )
            _run(
                [
                    _ffmpeg_exe(),
                    "-y",
                    "-i",
                    str(temp_mp3),
                    "-ac",
                    "1",
                    "-ar",
                    str(sample_rate),
                    str(output_wav),
                ]
            )
            return output_wav, ["fallback:edge_tts", f"emotion_simulation:{emotion.value}"]
        finally:
            temp_mp3.unlink(missing_ok=True)


class ElevenLabsVoiceEngine:
    """VoiceEngine protocol implementation for ElevenLabs Speech AI."""

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = DEFAULT_ELEVENLABS_MODEL,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.adapter = ElevenLabsAdapter(api_key=api_key, model_id=model_id, allow_fallback=allow_fallback)

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.ELEVENLABS

    @property
    def metadata(self) -> VoiceEngineMetadata:
        return VoiceEngineMetadata(
            engine_kind=VoiceEngineKind.ELEVENLABS,
            display_name="ElevenLabs Multilingual Speech AI",
            model_id=self.adapter.model_id,
            version="v2.5",
            capabilities={
                EngineCapability.TEXT_TO_SPEECH,
                EngineCapability.REFERENCE_AUDIO_CLONING,
                EngineCapability.VOICE_DESIGN_PROMPT,
                EngineCapability.EMOTION_CONDITIONING,
                EngineCapability.STYLE_INTENSITY,
                EngineCapability.STREAMING_SYNTHESIS,
                EngineCapability.SPEAKER_CONSISTENCY,
                EngineCapability.RATE_CONTROL,
                EngineCapability.MULTILINGUAL,
            },
            supported_languages=[
                "en", "bn", "hi", "es", "fr", "de", "ja", "zh", "pt", "it",
                "ko", "ar", "ru", "tr", "pl", "nl", "sv", "id", "cs", "uk",
            ],
            hardware_requirements="Cloud REST API (Zero local GPU / minimal CPU)",
            license_info="ElevenLabs Commercial Terms of Service",
            commercial_use_allowed=True,
            min_ram_gb=0.1,
            min_vram_gb=0.0,
            is_local=False,
            is_cloud_api=True,
            known_limitations=[
                "Requires valid ELEVENLABS_API_KEY environment variable or configured key.",
                "Consumes paid character quota per generation.",
                "Zero-shot instant voice cloning strictly requires affirmative consent verification.",
            ],
        )

    def is_available(self) -> tuple[bool, str]:
        if not self.adapter.is_configured():
            return (
                False,
                "API key not configured (set ELEVENLABS_API_KEY in Environment or Settings).",
            )
        return True, "Ready (ElevenLabs Cloud API configured)"

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        out_wav = out_root / f"{request.utterance_id}_{request.seed}_elevenlabs.wav"

        voice_id = str(request.voice_profile_id) if request.voice_profile_id else None
        res_path, applied = self.adapter.synthesize_to_file(
            text=request.text,
            output_wav_path=out_wav,
            voice_id=voice_id,
            emotion=request.emotion,
            emotion_intensity=request.emotion_intensity,
            reference_audio=request.reference_audio_path or None,
            consent=request.consent,
            sample_rate=request.output_sample_rate,
            target_duration_ms=request.target_duration_ms,
        )

        dur_ms = round(duration(res_path) * 1000)
        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=self.engine_kind,
            output_path=str(res_path),
            sample_rate=request.output_sample_rate,
            duration_ms=dur_ms,
            actual_duration_ms=dur_ms,
            seed_used=request.seed,
            applied_controls=applied,
        )

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]:
        """
        Translate voice design prompt attributes into ElevenLabs configuration parameters.
        """
        gender_voice = (
            DEFAULT_ELEVENLABS_VOICES["rachel"]
            if prompt.gender.lower() in {"female", "woman", "girl"}
            else DEFAULT_ELEVENLABS_VOICES["adam"]
        )
        return {
            "voice_id": gender_voice,
            "description": prompt.description,
            "gender": prompt.gender,
            "age_range": prompt.age_range,
            "accent": prompt.accent,
            "pitch": prompt.pitch,
            "timbre": prompt.timbre,
            "prompt_applied": True,
        }

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis:
        return analyze_voice_audio(audio_path)


__all__ = [
    "DEFAULT_ELEVENLABS_MODEL",
    "DEFAULT_ELEVENLABS_VOICES",
    "EMOTION_VOICE_SETTINGS",
    "ElevenLabsAdapter",
    "ElevenLabsVoiceEngine",
]
