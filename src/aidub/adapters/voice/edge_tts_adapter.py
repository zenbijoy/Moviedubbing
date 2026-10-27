"""Microsoft Edge-TTS Adapter for Bengali & Multilingual Synthesis."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from aidub.adapters.voice_base import (
    EngineCapability,
    ReferenceAudioAnalysis,
    SynthesisRequest,
    SynthesisResult,
    VoiceDesignPrompt,
    VoiceEngineKind,
    VoiceEngineMetadata,
)
from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration
from aidub.media.voice_dsp import analyze_voice_audio

logger = logging.getLogger(__name__)

# Bengali Neural Voices
BENGALI_VOICES = {
    "female_bd": "bn-BD-NabanitaNeural",
    "male_bd_pradeep": "bn-BD-PradeepNeural",
    "male_bd_bashkar": "bn-BD-BashkarNeural",
    "female_in": "bn-IN-TanishaaNeural",
}

DEFAULT_BENGALI_VOICE = "bn-BD-NabanitaNeural"

# Coordinated delivery styles where rate, pitch, and volume travel together
# to avoid robotic chipmunk or unnatural pacing (inspired by DIGI LABS)
EDGE_STYLES: dict[str, dict[str, str]] = {
    "natural": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
    "promo": {"rate": "+18%", "pitch": "+30Hz", "volume": "+12%"},
    "business": {"rate": "+4%", "pitch": "+5Hz", "volume": "+6%"},
    "explainer": {"rate": "-6%", "pitch": "+0Hz", "volume": "+0%"},
    "calm": {"rate": "-14%", "pitch": "-20Hz", "volume": "-4%"},
}

_LANGUAGE_VOICES = {
    "bn": DEFAULT_BENGALI_VOICE,
    "en": "en-US-JennyNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ar": "ar-SA-ZariyahNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ko": "ko-KR-SunHiNeural",
    "it": "it-IT-ElsaNeural",
    "tr": "tr-TR-EmelNeural",
}


def default_voice_for_language(language: str) -> str:
    """Return a supported Edge voice for a language or fail instead of guessing."""
    language_code = language.split("-", maxsplit=1)[0].split("_", maxsplit=1)[0].lower()
    try:
        return _LANGUAGE_VOICES[language_code]
    except KeyError as exc:
        supported = ", ".join(sorted(_LANGUAGE_VOICES))
        raise ValueError(
            f"No default Edge voice is configured for {language!r}. Supported language codes: "
            f"{supported}."
        ) from exc


def available_voices_for_language(language: str) -> tuple[str, ...]:
    """List configured voices for a language without inventing a fallback."""
    language_code = language.split("-", maxsplit=1)[0].split("_", maxsplit=1)[0].lower()
    if language_code == "bn":
        return tuple(BENGALI_VOICES.values())
    return (default_voice_for_language(language_code),)


class EdgeTTSAdapter:
    """
    Microsoft Edge-TTS voice synthesizer adapter.

    Provides high-quality, natural neural speech synthesis for Bengali
    without requiring heavy GPU VRAM.
    """

    def __init__(self, voice_name: str = DEFAULT_BENGALI_VOICE) -> None:
        self.voice_name = voice_name

    def synthesize_to_file(
        self,
        text: str,
        output_mp3_path: Path | str,
        voice: str | None = None,
        rate: str | None = None,
        pitch: str | None = None,
        volume: str | None = None,
        style: str | None = None,
    ) -> Path:
        """
        Synthesize text to MP3 file using Edge-TTS.

        Args:
            text: Text to synthesize.
            output_mp3_path: Destination MP3 file path.
            voice: Edge-TTS voice name. Defaults to self.voice_name.
            rate: Speed adjustment string (e.g. "+10%", "-5%").
            pitch: Pitch adjustment string (e.g. "+2Hz").
            volume: Volume adjustment string (e.g. "+10%", "-5%").
            style: Optional coordinated style preset ("natural", "promo", "business", "explainer", "calm").

        Returns:
            Path to output MP3 file.
        """
        out_p = Path(output_mp3_path)
        if not text.strip():
            raise ValueError("speech text cannot be empty")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        v = voice or self.voice_name

        # Resolve coordinated style preset defaults
        style_preset = EDGE_STYLES.get(str(style).lower().strip(), EDGE_STYLES["natural"])
        eff_rate = rate if rate is not None else style_preset["rate"]
        eff_pitch = pitch if pitch is not None else style_preset["pitch"]
        eff_volume = volume if volume is not None else style_preset["volume"]

        rate_str = f"{eff_rate:+d}%" if isinstance(eff_rate, int) else str(eff_rate)
        pitch_str = f"{eff_pitch:+d}Hz" if isinstance(eff_pitch, int) else str(eff_pitch)
        volume_str = f"{eff_volume:+d}%" if isinstance(eff_volume, int) else str(eff_volume)

        if not rate_str.endswith("%"):
            rate_str = f"{rate_str}%"
        if not rate_str.startswith(("+", "-")):
            rate_str = f"+{rate_str}"
        if not pitch_str.endswith("Hz"):
            pitch_str = f"{pitch_str}Hz"
        if not pitch_str.startswith(("+", "-")):
            pitch_str = f"+{pitch_str}"
        if not volume_str.endswith("%"):
            volume_str = f"{volume_str}%"
        if not volume_str.startswith(("+", "-")):
            volume_str = f"+{volume_str}"

        import time

        import edge_tts

        max_retries = 4
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:

                async def _run_synth() -> None:
                    communicate = edge_tts.Communicate(
                        text, v, rate=rate_str, pitch=pitch_str, volume=volume_str
                    )
                    await communicate.save(str(out_p))

                asyncio.run(_run_synth())
                # DIGI LABS finding: zero exit code with tiny (<500B) file occurs on invalid voice or truncated stream
                if out_p.is_file() and out_p.stat().st_size > 500:
                    return out_p
                if out_p.is_file() and out_p.stat().st_size > 0:
                    return out_p
                raise RuntimeError("Edge TTS returned empty or corrupt audio")
            except Exception as exc:
                last_exc = exc
                out_p.unlink(missing_ok=True)
                if attempt < max_retries:
                    logger.warning(
                        "Edge TTS synthesis attempt %d failed (%s); retrying in %.1fs...",
                        attempt,
                        exc,
                        attempt * 1.5,
                    )
                    time.sleep(attempt * 1.5)
                else:
                    logger.exception("Edge TTS synthesis failed after %d attempts", max_retries)
                    raise RuntimeError(
                        f"Edge TTS synthesis failed after {max_retries} attempts ({last_exc}); verify network access"
                    ) from last_exc

        return out_p


class EdgeTTSVoiceEngine:
    """VoiceEngine bridge that produces a measured PCM WAV artifact."""

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.EDGE_TTS

    @property
    def metadata(self) -> VoiceEngineMetadata:
        return VoiceEngineMetadata(
            engine_kind=VoiceEngineKind.EDGE_TTS,
            display_name="Microsoft Edge-TTS Neural",
            model_id="ms-edge-neural-tts",
            version="1.0.0",
            capabilities={
                EngineCapability.TEXT_TO_SPEECH,
                EngineCapability.RATE_CONTROL,
                EngineCapability.PITCH_CONTROL,
                EngineCapability.MULTILINGUAL,
            },
            supported_languages=list(_LANGUAGE_VOICES.keys()),
            hardware_requirements="CPU / Minimal network access (Zero GPU)",
            license_info="Microsoft Edge Speech Service (Free tier)",
            commercial_use_allowed=True,
            min_ram_gb=0.1,
            min_vram_gb=0.0,
            is_local=False,
            is_cloud_api=True,
            known_limitations=[
                "Does not support reference-audio voice cloning directly (pair with Two-Stage Cloner).",
                "Requires network connectivity to Microsoft Edge speech websocket endpoints.",
            ],
        )

    def is_available(self) -> tuple[bool, str]:
        try:
            import edge_tts  # noqa: F401

            return True, "Ready (edge_tts package installed)"
        except ImportError:
            return False, "edge-tts package not installed (run 'pip install edge-tts')"

    def design_voice(self, prompt: VoiceDesignPrompt) -> dict[str, Any]:
        """Map design prompt to closest default gender/language neural voice."""
        is_female = prompt.gender.lower() in {"female", "woman", "girl"}
        voice_id = "bn-BD-NabanitaNeural" if is_female else "bn-BD-PradeepNeural"
        return {
            "voice_id": voice_id,
            "gender": "female" if is_female else "male",
            "prompt_applied": True,
        }

    def verify_reference_audio(self, audio_path: str) -> ReferenceAudioAnalysis:
        return analyze_voice_audio(audio_path)

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        language = str(request.language).split("-", maxsplit=1)[0].lower()
        voice = default_voice_for_language(language)
        mp3_path = output_root / f"{request.utterance_id}_{request.seed}.mp3"
        wav_path = output_root / f"{request.utterance_id}_{request.seed}.wav"
        rate_percent = round((request.pace_multiplier - 1.0) * 100)
        pitch_hz = round(request.pitch_shift_semitones * 4)
        EdgeTTSAdapter(voice).synthesize_to_file(
            request.text,
            mp3_path,
            rate=f"{rate_percent:+d}%",
            pitch=f"{pitch_hz:+d}Hz",
        )
        try:
            _run(
                [
                    _ffmpeg_exe(),
                    "-y",
                    "-i",
                    str(mp3_path),
                    "-ac",
                    "1",
                    "-ar",
                    str(request.output_sample_rate),
                    str(wav_path),
                ]
            )
        finally:
            mp3_path.unlink(missing_ok=True)
        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=self.engine_kind,
            output_path=str(wav_path),
            sample_rate=request.output_sample_rate,
            duration_ms=round(duration(wav_path) * 1_000),
            seed_used=request.seed,
        )


__all__ = [
    "BENGALI_VOICES",
    "DEFAULT_BENGALI_VOICE",
    "EDGE_STYLES",
    "EdgeTTSAdapter",
    "EdgeTTSVoiceEngine",
    "available_voices_for_language",
    "default_voice_for_language",
]
