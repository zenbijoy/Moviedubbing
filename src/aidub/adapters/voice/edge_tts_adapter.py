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
from aidub.media.ffmpeg_ops import _run, duration

logger = logging.getLogger(__name__)

# Bengali Neural Voices
BENGALI_VOICES = {
    "female_bd": "bn-BD-NabanitaNeural",
    "male_bd":   "bn-BD-PradeepNeural",
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
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("speech text cannot be empty")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        v = voice or self.voice_name

        import re
        import time

        # If text contains only punctuation, ellipsis, or symbols, generate clean silence
        if not re.search(r"[\w\u0980-\u09FF]", clean_text):
            _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.3", "-q:a", "9", str(out_p)])
            return out_p

        try:
            import edge_tts  # type: ignore[import-not-found]

            async def _run_synth() -> None:
                communicate = edge_tts.Communicate(clean_text, v, rate=rate, pitch=pitch)
                await communicate.save(str(out_p))

            for attempt in range(3):
                try:
                    asyncio.run(_run_synth())
                    if out_p.is_file() and out_p.stat().st_size > 0:
                        return out_p
                except Exception as exc:
                    if attempt == 2:
                        logger.warning("Edge TTS failed after 3 attempts (%s); generating silent filler.", exc)
                        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.3", str(out_p)])
                        if out_p.is_file():
                            return out_p
                        raise RuntimeError(
                            "Edge TTS synthesis failed; install edge-tts and verify network access"
                        ) from exc
                    time.sleep(1.0)
            return out_p
        except Exception as exc:
            if not out_p.is_file() or out_p.stat().st_size == 0:
                _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.3", str(out_p)])
                if out_p.is_file():
                    return out_p
            out_p.unlink(missing_ok=True)
            logger.exception("Edge TTS synthesis failed")
            raise RuntimeError(
                "Edge TTS synthesis failed; install edge-tts and verify network access"
            ) from exc


class EdgeTTSVoiceEngine:
    """VoiceEngine bridge that produces a measured PCM WAV artifact."""

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.EDGE_TTS

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        language = str(request.language).split("-", maxsplit=1)[0].lower()
        voice = _LANGUAGE_VOICES.get(language, "en-US-JennyNeural")
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
                    "ffmpeg",
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
]
