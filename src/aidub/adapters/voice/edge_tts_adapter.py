"""Microsoft Edge-TTS Adapter for Bengali & Multilingual Synthesis."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aidub.adapters.voice_base import (
    SynthesisRequest,
    SynthesisResult,
    VoiceEngineKind,
)
from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration

logger = logging.getLogger(__name__)

# Bengali Neural Voices
BENGALI_VOICES = {
    "female_bd": "bn-BD-NabanitaNeural",
    "male_bd": "bn-BD-PradeepNeural",
    "female_in": "bn-IN-TanishaaNeural",
}

DEFAULT_BENGALI_VOICE = "bn-BD-NabanitaNeural"

_LANGUAGE_VOICES = {
    "bn": DEFAULT_BENGALI_VOICE,
    "en": "en-US-JennyNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "ja": "ja-JP-NanamiNeural",
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
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> Path:
        """
        Synthesize text to MP3 file using Edge-TTS.

        Args:
            text: Text to synthesize.
            output_mp3_path: Destination MP3 file path.
            voice: Edge-TTS voice name. Defaults to self.voice_name.
            rate: Speed adjustment string (e.g. "+10%", "-5%").
            pitch: Pitch adjustment string (e.g. "+2Hz").

        Returns:
            Path to output MP3 file.
        """
        out_p = Path(output_mp3_path)
        if not text.strip():
            raise ValueError("speech text cannot be empty")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        v = voice or self.voice_name

        rate_str = f"{rate:+d}%" if isinstance(rate, int) else str(rate)
        pitch_str = f"{pitch:+d}Hz" if isinstance(pitch, int) else str(pitch)
        if not rate_str.endswith("%"):
            rate_str = f"{rate_str}%"
        if not (rate_str.startswith("+") or rate_str.startswith("-")):
            rate_str = f"+{rate_str}"
        if not pitch_str.endswith("Hz"):
            pitch_str = f"{pitch_str}Hz"
        if not (pitch_str.startswith("+") or pitch_str.startswith("-")):
            pitch_str = f"+{pitch_str}"

        import time

        import edge_tts

        max_retries = 4
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:

                async def _run_synth() -> None:
                    communicate = edge_tts.Communicate(text, v, rate=rate_str, pitch=pitch_str)
                    await communicate.save(str(out_p))

                asyncio.run(_run_synth())
                if out_p.is_file() and out_p.stat().st_size > 0:
                    return out_p
                raise RuntimeError("Edge TTS returned empty audio")
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
    "EdgeTTSAdapter",
    "EdgeTTSVoiceEngine",
    "available_voices_for_language",
    "default_voice_for_language",
]
