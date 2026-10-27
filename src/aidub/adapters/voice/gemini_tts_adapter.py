"""
Gemini 3.8 Flash Studio Expressive Neural Speech Generation Adapter.

Delivers cinema-grade, emotionally authentic speech synthesis for movie dubbing:
  - Supports native Bengali, Hindi, English, Spanish, Japanese, etc.
  - Direct dramatic performance control via speech_metadata.style:
    anger, grief/weeping, suspenseful whispers, shouts, romantic tenderness, humor.
  - Multi-character voice casting:
    Male voices: Fenrir, Charon, Puck, Orus
    Female voices: Kore, Aoede, Leda, Zephyr
  - Automatic API key rotation across key pools for high reliability and quota resilience.
  - Sub-second turnaround with zero heavy local GPU VRAM requirements.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Sequence
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

GEMINI_TTS_MODEL = "gemini-3.8-flash-tts"

# Pre-built Gemini Studio Voices
GEMINI_VOICES_MALE = ("Fenrir", "Charon", "Puck", "Orus")
GEMINI_VOICES_FEMALE = ("Kore", "Aoede", "Leda", "Zephyr")

DEFAULT_MALE_VOICE = "Fenrir"
DEFAULT_FEMALE_VOICE = "Kore"

# Emotion to expressive style prompt mapping
EMOTION_STYLE_PROMPTS: dict[str, str] = {
    "neutral": "natural cinematic dialogue, clear conversational cadence",
    "joy": "joyful, cheerful, lively and animated with warmth and excitement",
    "anger": "intense fury, fierce and aggressive, harsh breathing and shouting with outrage",
    "sadness": "deep sorrow and heartbreak, choked-up trembling voice, weeping, mourning",
    "fear": "terrified, trembling, breathless panic, rushed and frightened whisper",
    "surprise": "astonished, sudden intake of breath, stunned exclamation of shock",
    "disgust": "scornful, revolted, sneering and disdainful contempt",
    "anticipation": "eager, expectant, focused and leaned-in with intrigue",
    "whisper": "quiet intimate whisper, soft and hush, cautious secrecy",
    "suspense": "tense, guarded, hushed and cautious, dramatic suspense",
    "intense_confrontation": "furious dramatic confrontation, screaming with rage and emotional betrayal",
    "sarcastic": "dry, mocking, biting sarcasm and cynical smirk",
    "tender": "gentle, tender, deeply intimate and affectionate, soothing soft tone",
    "despair": "devastated, utterly broken, exhausted gasping for air in total despair",
    "resolute": "firm, authoritative, steely determination, commanding hero voice",
    "shouting": "loud shouting, projecting at full lung capacity, strained shouting",
    "excited": "bursting with excitement, high energy, fast-paced and ecstatic",
}


class GeminiExpressiveTTSAdapter:
    """
    Client for Gemini 3.8 Flash Studio Expressive Speech Generation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        key_pool: Sequence[str] | None = None,
        *,
        model: str = GEMINI_TTS_MODEL,
        allow_fallback: bool = True,
    ) -> None:
        self.model = model
        self.allow_fallback = allow_fallback
        self._key_index = 0

        # Build key pool from explicit args or environment variables
        keys: list[str] = []
        if api_key:
            keys.append(api_key.strip())
        elif os.environ.get("GEMINI_API_KEY"):
            keys.append(os.environ["GEMINI_API_KEY"].strip())

        pool_env = os.environ.get("GEMINI_API_KEYS", "")
        if pool_env:
            for k in pool_env.split(","):
                k_clean = k.strip()
                if k_clean and k_clean not in keys:
                    keys.append(k_clean)

        self._keys = [k for k in keys if k]

    def _next_key(self) -> str:
        """Rotate through the key pool for rate limit resilience."""
        if not self._keys:
            # Check environment one more time
            env_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if env_key:
                return env_key
            raise VoiceEngineError(
                "gemini_tts", "No GEMINI_API_KEY or GEMINI_API_KEYS configured in environment."
            )
        key = self._keys[self._key_index % len(self._keys)]
        self._key_index += 1
        return key

    @classmethod
    def pick_voice_for_character(
        cls,
        gender: str | None = None,
        character_name: str = "",
        pitch_median_hz: float | None = None,
    ) -> str:
        """
        Cast character to best matching pre-built Gemini studio voice.
        """
        # Pitch-based determination if available
        if pitch_median_hz is not None and pitch_median_hz > 0:
            if pitch_median_hz < 165.0:
                # Male pitch range
                return "Fenrir" if pitch_median_hz < 130.0 else "Charon"
            # Female pitch range
            return "Kore" if pitch_median_hz < 220.0 else "Aoede"

        # Gender / name heuristics
        g = (gender or "").lower().strip()
        if g in {"male", "m", "man", "boy", "actor"}:
            return DEFAULT_MALE_VOICE
        if g in {"female", "f", "woman", "girl", "actress"}:
            return DEFAULT_FEMALE_VOICE

        name_lower = character_name.lower()
        if any(
            term in name_lower
            for term in (
                "mrs",
                "ms",
                "miss",
                "lady",
                "she",
                "her",
                "mother",
                "sister",
                "girl",
                "woman",
            )
        ):
            return DEFAULT_FEMALE_VOICE
        if any(
            term in name_lower
            for term in ("mr", "sir", "lord", "he", "his", "father", "brother", "boy", "man")
        ):
            return DEFAULT_MALE_VOICE

        return DEFAULT_MALE_VOICE

    def synthesize_to_file(
        self,
        text: str,
        output_wav_path: Path | str,
        *,
        voice: str | None = None,
        emotion: str | EmotionLabel | None = None,
        style_instruction: str | None = None,
        sample_rate: int = 24000,
    ) -> Path:
        """
        Synthesize text to high-quality expressive WAV using Gemini 3.8 Flash TTS.

        Args:
            text: Dialogue line text (Bengali or other target language).
            output_wav_path: Target output WAV path.
            voice: Optional prebuilt voice name (Fenrir, Kore, Charon, etc.).
            emotion: Emotion name (anger, sadness, whisper, etc.) or EmotionLabel.
            style_instruction: Direct detailed acting prompt for the voice.
            sample_rate: Audio output sample rate (24000 standard).

        Returns:
            Path to written output WAV file.
        """
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Speech dialogue text cannot be empty.")

        out_path = Path(output_wav_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        eff_voice = voice or DEFAULT_MALE_VOICE
        # Normalize voice name to valid Gemini pre-built names
        valid_voices = set(GEMINI_VOICES_MALE) | set(GEMINI_VOICES_FEMALE)
        if eff_voice not in valid_voices:
            # Map edge-tts or generic voice name to Gemini equivalent
            if any(
                term in eff_voice.lower()
                for term in ("female", "nabanita", "tanishaa", "jenny", "kore", "aoede", "leda")
            ):
                eff_voice = "Kore"
            else:
                eff_voice = "Fenrir"

        # Determine emotional style prompt
        emo_key = ""
        if emotion:
            emo_key = (
                emotion.value if isinstance(emotion, EmotionLabel) else str(emotion).lower().strip()
            )

        style_prompt = style_instruction
        if not style_prompt:
            style_prompt = EMOTION_STYLE_PROMPTS.get(
                emo_key, "expressive natural theatrical dialogue delivery"
            )

        # Attempt synthesis with key rotation
        max_attempts = max(3, len(self._keys) * 2)
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            api_key = self._next_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": clean_text, "speech_metadata": {"style": style_prompt}}],
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": eff_voice}}
                    },
                },
            }

            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=25.0) as resp:  # noqa: S310
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini TTS response contained no candidate speech.")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    audio_b64 = None
                    mime_type = "audio/wav"
                    for p in parts:
                        if "inlineData" in p:
                            audio_b64 = p["inlineData"].get("data")
                            mime_type = p["inlineData"].get("mimeType", "audio/wav")
                            break

                    if not audio_b64:
                        raise RuntimeError("Gemini TTS candidate contained no inline audio data.")

                    raw_bytes = base64.b64decode(audio_b64)
                    if len(raw_bytes) < 100:
                        raise RuntimeError("Gemini TTS returned corrupt or empty audio.")

                    # Write audio to disk
                    temp_raw = out_path.with_suffix(".gemini.raw")
                    temp_raw.write_bytes(raw_bytes)

                    # Ensure standard PCM 16-bit WAV at desired sample rate
                    if "wav" in mime_type.lower() and raw_bytes[:4] == b"RIFF":
                        # Valid WAV header
                        out_path.write_bytes(raw_bytes)
                        temp_raw.unlink(missing_ok=True)
                    else:
                        # Convert raw audio / PCM to standard WAV using ffmpeg
                        cmd = [
                            _ffmpeg_exe(),
                            "-y",
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-i",
                            str(temp_raw),
                            "-ac",
                            "1",
                            "-ar",
                            str(sample_rate),
                            str(out_path),
                        ]
                        _run(cmd)
                        temp_raw.unlink(missing_ok=True)

                    logger.info(
                        "Gemini 3.8 Flash TTS generated expressive line: voice=%s, style='%s', bytes=%d -> %s",
                        eff_voice,
                        style_prompt[:40],
                        len(raw_bytes),
                        out_path.name,
                    )
                    return out_path

            except urllib.error.HTTPError as exc:
                err_msg = exc.read().decode("utf-8", errors="replace")
                last_exc = RuntimeError(f"HTTP {exc.code}: {err_msg}")
                logger.warning(
                    "Gemini TTS attempt %d failed (HTTP %d): %s",
                    attempt + 1,
                    exc.code,
                    err_msg[:120],
                )
                if exc.code == 429:
                    # Rate limit, continue to next rotated key immediately
                    continue
                if exc.code in {400, 404}:
                    # Invalid model or payload, don't spin indefinitely
                    break
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini TTS attempt %d network exception: %s", attempt + 1, exc)

        # Fallback handling
        if not self.allow_fallback:
            raise VoiceEngineError(
                "gemini_tts", f"Gemini expressive synthesis failed: {last_exc}"
            ) from last_exc

        logger.warning(
            "Gemini Expressive TTS failed (%s); falling back to Edge-TTS neural base",
            last_exc,
        )
        return self._synthesize_fallback(clean_text, out_path, voice=voice, emotion=emo_key)

    def _synthesize_fallback(
        self,
        text: str,
        output_wav: Path,
        voice: str | None,
        emotion: str,
    ) -> Path:
        """Clean Edge-TTS fallback when Gemini API is unavailable."""
        from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter

        # Clean Edge-TTS fallback
        bn_voice = (
            "bn-BD-NabanitaNeural" if voice in set(GEMINI_VOICES_FEMALE) else "bn-BD-PradeepNeural"
        )
        tts = EdgeTTSAdapter(bn_voice)

        rate_str = "+0%"
        pitch_str = "+0Hz"
        if emotion in {"anger", "shouting", "excited"}:
            rate_str = "+10%"
            pitch_str = "+8Hz"
        elif emotion in {"sadness", "despair"}:
            rate_str = "-12%"
            pitch_str = "-6Hz"
        elif emotion in {"whisper", "suspense"}:
            rate_str = "-8%"
            pitch_str = "-4Hz"

        tts.synthesize_to_file(
            text=text,
            output_mp3_path=output_wav,
            voice=bn_voice,
            rate=rate_str,
            pitch=pitch_str,
        )
        return output_wav


class GeminiTTSVoiceEngine:
    """VoiceEngine protocol implementation for Gemini 3.8 Expressive Speech Generation."""

    def __init__(
        self,
        api_key: str | None = None,
        key_pool: Sequence[str] | None = None,
        *,
        model: str = GEMINI_TTS_MODEL,
        allow_fallback: bool = True,
    ) -> None:
        self.adapter = GeminiExpressiveTTSAdapter(
            api_key=api_key, key_pool=key_pool, model=model, allow_fallback=allow_fallback
        )

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.GEMINI_TTS

    @property
    def metadata(self) -> VoiceEngineMetadata:
        return VoiceEngineMetadata(
            engine_kind=VoiceEngineKind.GEMINI_TTS,
            display_name="Gemini 3.8 Flash Expressive TTS",
            model_id=self.adapter.model,
            version="3.8.0",
            capabilities={
                EngineCapability.TEXT_TO_SPEECH,
                EngineCapability.EMOTION_CONDITIONING,
                EngineCapability.STYLE_INTENSITY,
                EngineCapability.SPEAKER_CONSISTENCY,
                EngineCapability.MULTILINGUAL,
            },
            supported_languages=[
                "en", "bn", "hi", "es", "fr", "de", "ja", "zh", "pt", "it",
                "ko", "ar", "ru", "tr", "id", "nl", "sv",
            ],
            hardware_requirements="Cloud REST API (Zero local GPU)",
            license_info="Google Cloud / Gemini API Terms",
            commercial_use_allowed=True,
            min_ram_gb=0.1,
            min_vram_gb=0.0,
            is_local=False,
            is_cloud_api=True,
            known_limitations=[
                "Requires GEMINI_API_KEY environment variable or configured API key pool.",
                "Zero-shot cloning not supported; uses curated expressive cinematic voices.",
            ],
        )

    def is_available(self) -> tuple[bool, str]:
        has_keys = bool(self.adapter.key_pool or os.environ.get("GEMINI_API_KEY"))
        if has_keys:
            return True, "Ready (Gemini API credentials detected)"
        return (
            False,
            "GEMINI_API_KEY not configured (fallback mode active)",
        )

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]:
        is_female = prompt.gender.lower() in {"female", "woman", "girl"}
        voice = DEFAULT_FEMALE_VOICE if is_female else DEFAULT_MALE_VOICE
        return {
            "voice_id": voice,
            "gender": "female" if is_female else "male",
            "personality": prompt.personality,
            "timbre": prompt.timbre,
            "prompt_applied": True,
        }

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis:
        return analyze_voice_audio(audio_path)

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        out_wav = out_root / f"{request.utterance_id}_{request.seed}_gemini.wav"

        voice_id = str(request.voice_profile_id) if request.voice_profile_id else None
        res_path = self.adapter.synthesize_expressive_dialogue(
            text=request.text,
            output_wav=out_wav,
            voice=voice_id,
            emotion=request.emotion,
            sample_rate=request.output_sample_rate,
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
            applied_controls=[f"emotion:{request.emotion.value}", f"model:{self.adapter.model}"],
        )


__all__ = [
    "DEFAULT_FEMALE_VOICE",
    "DEFAULT_MALE_VOICE",
    "EMOTION_STYLE_PROMPTS",
    "GEMINI_TTS_MODEL",
    "GEMINI_VOICES_FEMALE",
    "GEMINI_VOICES_MALE",
    "GeminiExpressiveTTSAdapter",
    "GeminiTTSVoiceEngine",
]
