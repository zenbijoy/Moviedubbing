"""
Chatterbox AI Voice Engine Adapter.

Provides expressive, emotion-aware speech synthesis and zero-shot voice cloning
using Chatterbox AI endpoints or local Chatterbox neural inference servers.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from aidub.adapters.voice_base import (
    EmotionLabel,
    EngineCapability,
    ReferenceAudioAnalysis,
    SynthesisRequest,
    SynthesisResult,
    VoiceDesignPrompt,
    VoiceEngineError,
    VoiceEngineKind,
    VoiceEngineMetadata,
)
from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration
from aidub.media.voice_dsp import analyze_voice_audio

logger = logging.getLogger(__name__)

DEFAULT_CHATTERBOX_URL = "http://localhost:8000/v1/audio/speech"
DEFAULT_CHATTERBOX_MODEL = "chatterbox-v1"


class ChatterboxAdapter:
    """
    Client for Chatterbox AI expressive voice synthesis and voice cloning.

    Supports:
      - HTTP REST API for remote or local self-hosted Chatterbox servers.
      - Expressive emotion styles (neutral, angry, sad, joy, fear, whisper, shout).
      - Zero-shot voice cloning from a reference speaker WAV/MP3.
      - Safe fallback to Edge-TTS / neural modulation if Chatterbox server is offline.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.api_url = api_url or os.environ.get("CHATTERBOX_API_URL") or DEFAULT_CHATTERBOX_URL
        self.api_key = api_key or os.environ.get("CHATTERBOX_API_KEY", "")
        self.model = model or os.environ.get("CHATTERBOX_MODEL") or DEFAULT_CHATTERBOX_MODEL
        self.allow_fallback = allow_fallback

    def is_server_reachable(self, timeout_sec: float = 1.5) -> bool:
        """Check if the Chatterbox server endpoint is live."""
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            health_url = f"{parsed.scheme}://{parsed.netloc}/health"
            req = urllib.request.Request(health_url, method="GET")  # noqa: S310
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
                return resp.status in {200, 204}
        except Exception:
            return False

    def synthesize_to_file(
        self,
        text: str,
        output_wav_path: Path | str,
        *,
        voice: str | None = None,
        emotion: str | EmotionLabel = EmotionLabel.NEUTRAL,
        reference_audio: Path | str | None = None,
        pace: float = 1.0,
        pitch_shift: float = 0.0,
        sample_rate: int = 44100,
    ) -> Path:
        """
        Synthesize speech to a WAV file using Chatterbox AI.

        Args:
            text: Text to synthesize.
            output_wav_path: Target output WAV path.
            voice: Optional target voice ID or character tag.
            emotion: Emotion name or EmotionLabel.
            reference_audio: Optional path to reference speaker audio for cloning.
            pace: Speed factor (1.0 = normal, 0.8 = slower, 1.2 = faster).
            pitch_shift: Semitones pitch shift.
            sample_rate: Output audio sample rate in Hz.

        Returns:
            Path to the written output WAV file.
        """
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Speech text cannot be empty.")

        out_path = Path(output_wav_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        emotion_str = emotion.value if isinstance(emotion, EmotionLabel) else str(emotion)

        payload: dict[str, Any] = {
            "model": self.model,
            "input": clean_text,
            "voice": voice or "chatterbox_default",
            "emotion": emotion_str,
            "speed": pace,
            "pitch_shift": pitch_shift,
            "sample_rate": sample_rate,
        }

        if reference_audio and Path(reference_audio).is_file():
            ref_path = Path(reference_audio)
            payload["reference_audio"] = str(ref_path.resolve())
            try:
                import base64

                ref_bytes = ref_path.read_bytes()
                # If audio is reasonable size (< 20MB), embed base64 so remote Kaggle/cloud endpoints can access it
                if len(ref_bytes) < 20 * 1024 * 1024:
                    payload["reference_audio_base64"] = base64.b64encode(ref_bytes).decode("ascii")
            except Exception as exc:
                logger.warning("Could not encode reference audio for remote endpoint: %s", exc)

        # Attempt synthesis against Chatterbox HTTP endpoint
        try:
            req_data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "aidub-chatterbox/1.0",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            request = urllib.request.Request(  # noqa: S310
                self.api_url,
                data=req_data,
                headers=headers,
                method="POST",
            )
            timeout_sec = float(os.environ.get("CHATTERBOX_TIMEOUT_SEC", "90.0"))
            with urllib.request.urlopen(request, timeout=timeout_sec) as resp:  # noqa: S310
                content_type = resp.headers.get("Content-Type", "")
                audio_bytes = resp.read()
                if not audio_bytes:
                    raise RuntimeError("Chatterbox server returned empty audio payload.")

                if "json" in content_type:
                    # JSON response with base64 encoded audio
                    import base64

                    data = json.loads(audio_bytes.decode("utf-8"))
                    b64_audio = data.get("audio_base64") or data.get("audio") or ""
                    if not b64_audio:
                        raise RuntimeError(
                            f"Chatterbox server returned JSON without audio data: {list(data.keys())}"
                        )
                    audio_bytes = base64.b64decode(b64_audio)
                    if not audio_bytes:
                        raise RuntimeError("Chatterbox audio payload decoded to 0 bytes.")

                out_path.write_bytes(audio_bytes)
                logger.info(
                    "Chatterbox AI synthesis succeeded: %s (%d bytes)",
                    out_path.name,
                    len(audio_bytes),
                )
                return out_path

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError, RuntimeError) as exc:
            if not self.allow_fallback:
                raise VoiceEngineError(
                    "chatterbox", f"Synthesis failed and fallback disabled: {exc}"
                ) from exc

            logger.info(
                "Chatterbox AI endpoint unreachable or error (%s); using adaptive neural fallback with emotion=%s",
                exc,
                emotion_str,
            )
            return self._synthesize_fallback(
                clean_text,
                out_path,
                voice=voice,
                emotion=emotion_str,
                pace=pace,
                pitch_shift=pitch_shift,
                sample_rate=sample_rate,
            )

    def _synthesize_fallback(
        self,
        text: str,
        output_wav: Path,
        voice: str | None,
        emotion: str,
        pace: float,
        pitch_shift: float,
        sample_rate: int,
    ) -> Path:
        """Adaptive fallback using Edge-TTS with emotion-mapped prosody adjustments."""
        from aidub.adapters.voice.edge_tts_adapter import DEFAULT_BENGALI_VOICE, EdgeTTSAdapter

        # Map Chatterbox emotions to pitch/rate prosody offsets
        emotion_prosody = {
            "angry": ("+14%", "+6Hz"),
            "shout": ("+18%", "+8Hz"),
            "joy": ("+8%", "+4Hz"),
            "sad": ("-12%", "-4Hz"),
            "fear": ("+10%", "+3Hz"),
            "whisper": ("-8%", "-3Hz"),
            "neutral": ("+0%", "+0Hz"),
        }
        rate_offset_str, pitch_offset_str = emotion_prosody.get(emotion.lower(), ("+0%", "+0Hz"))

        # Combine user's editorial pacing and pitch with emotional offsets
        base_rate = round((pace - 1.0) * 100)
        base_pitch = round(pitch_shift * 4)

        rate_emo_val = int(rate_offset_str.replace("%", "").replace("+", ""))
        pitch_emo_val = int(pitch_offset_str.replace("Hz", "").replace("+", ""))

        final_rate = f"{base_rate + rate_emo_val:+d}%"
        final_pitch = f"{base_pitch + pitch_emo_val:+d}Hz"

        selected_voice = voice or DEFAULT_BENGALI_VOICE
        temp_mp3 = output_wav.with_suffix(".tmp.mp3")
        try:
            EdgeTTSAdapter(selected_voice).synthesize_to_file(
                text,
                temp_mp3,
                rate=final_rate,
                pitch=final_pitch,
            )
            # Transcode to WAV with requested sample rate
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
            return output_wav
        finally:
            temp_mp3.unlink(missing_ok=True)


class ChatterboxVoiceEngine:
    """VoiceEngine protocol implementation for Chatterbox AI."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.adapter = ChatterboxAdapter(
            api_url=api_url, api_key=api_key, allow_fallback=allow_fallback
        )

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.CHATTERBOX

    @property
    def metadata(self) -> VoiceEngineMetadata:
        return VoiceEngineMetadata(
            engine_kind=VoiceEngineKind.CHATTERBOX,
            display_name="Chatterbox AI Voice Engine",
            model_id=self.adapter.model,
            version="1.0.0",
            capabilities={
                EngineCapability.TEXT_TO_SPEECH,
                EngineCapability.REFERENCE_AUDIO_CLONING,
                EngineCapability.EMOTION_CONDITIONING,
                EngineCapability.STYLE_INTENSITY,
                EngineCapability.RATE_CONTROL,
                EngineCapability.PITCH_CONTROL,
                EngineCapability.MULTILINGUAL,
            },
            supported_languages=["bn", "en", "hi", "es", "fr", "de", "ja"],
            hardware_requirements="HTTP Server (Local or Remote, min 4GB VRAM if local)",
            license_info="Proprietary / Chatterbox AI Terms",
            commercial_use_allowed=True,
            min_ram_gb=4.0,
            min_vram_gb=4.0,
            is_local=False,
            is_cloud_api=True,
            known_limitations=[
                "Requires running Chatterbox inference server endpoint (default: http://localhost:8000).",
                "Automatically falls back to Edge-TTS if endpoint unreachable.",
            ],
        )

    def is_available(self) -> tuple[bool, str]:
        if self.adapter.is_server_reachable():
            return True, f"Ready (Chatterbox server online at {self.adapter.api_url})"
        return (
            False,
            f"Chatterbox server not reachable at {self.adapter.api_url} (fallback mode active)",
        )

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]:
        return {
            "engine": "chatterbox",
            "gender": prompt.gender,
            "timbre": prompt.timbre,
            "prompt_applied": True,
        }

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis:
        return analyze_voice_audio(audio_path)

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        out_wav = out_root / f"{request.utterance_id}_{request.seed}_chatterbox.wav"

        self.adapter.synthesize_to_file(
            text=request.text,
            output_wav_path=out_wav,
            voice=str(request.voice_profile_id) if request.voice_profile_id else None,
            emotion=request.emotion,
            reference_audio=request.reference_audio_path or None,
            pace=request.pace_multiplier,
            pitch_shift=request.pitch_shift_semitones,
            sample_rate=request.output_sample_rate,
        )

        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=self.engine_kind,
            output_path=str(out_wav),
            sample_rate=request.output_sample_rate,
            duration_ms=round(duration(out_wav) * 1_000),
            seed_used=request.seed,
        )


__all__ = [
    "DEFAULT_CHATTERBOX_MODEL",
    "DEFAULT_CHATTERBOX_URL",
    "ChatterboxAdapter",
    "ChatterboxVoiceEngine",
]
