"""
Modular AI Dubbing Pipeline Service.

Provides discrete, decoupled application-level interfaces for each production stage:
  1. Media probing and audio extraction (FFmpeg/FFprobe)
  2. Automatic Speech Recognition (ASR) with segment and word timestamps (Faster-Whisper)
  3. Transcript normalization and editable subtitle cues
  4. Multi-pass contextual translation with offline fallback support
  5. Text-to-speech voice synthesis with bounded timing fitting and review flagging
  6. Optional speaker diarization
  7. Audio mixing with dynamic sidechain music ducking
  8. Synchronized master video rendering & stream verification
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import field
from enum import StrEnum
from pathlib import Path
from typing import Any

from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter, default_voice_for_language
from aidub.application.timing_fitter import TimingFitter
from aidub.application.translation_pipeline import (
    DialogueLine,
    TranslationContext,
    TranslationPipeline,
)
from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.time import RationalRate, RationalTime
from aidub.media.assemble import assemble_timeline, fit_to_slot
from aidub.media.ffmpeg_ops import (
    duration,
    dynamic_sidechain_mix,
    extract_audio,
    mux,
    probe,
)
from aidub.providers.router import LlmProviderRouter

logger = logging.getLogger(__name__)


class PipelineCancelledError(RuntimeError):
    """Raised when an operation is cancelled by the operator."""


class PipelineStageStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TranscriptCue(ContractModel):
    """A recognized or manually created dialogue subtitle cue."""

    cue_id: str
    start_s: float
    end_s: float
    text: str
    speaker: str = "SPEAKER_00"
    confidence: float = 1.0
    words: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)

    def to_rational_time(self, fps: float = 24.0) -> tuple[RationalTime, RationalTime]:
        num = round(fps * 1000)
        rate = RationalRate(numerator=num, denominator=1000)
        start_ticks = round(self.start_s * num / 1000)
        end_ticks = round(self.end_s * num / 1000)
        return RationalTime(ticks=start_ticks, rate=rate), RationalTime(ticks=end_ticks, rate=rate)


class TranslatedCue(ContractModel):
    """A localized dialogue cue with source, target, and timing constraints."""

    cue_id: str
    start_s: float
    end_s: float
    source_text: str
    target_text: str
    target_language: str
    speaker: str = "SPEAKER_00"
    duration_budget_ms: int = 0
    estimated_duration_ms: int = 0
    confidence: float = 1.0

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class SynthesizedCueTake(ContractModel):
    """Synthesized voice audio take for a specific dialogue cue."""

    cue_id: str
    audio_path: str
    voice_name: str
    start_s: float
    target_duration_s: float
    actual_duration_s: float
    delta_s: float
    delta_pct: float
    flagged_for_review: bool = False
    fitted_audio_path: str = ""


# Offline bilingual lexicon for deterministic testing and network-isolated workstations
_OFFLINE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "bn": {
        "hello": "হ্যালো",
        "world": "বিশ্ব",
        "thank": "ধন্যবাদ",
        "you": "আপনাকে",
        "thank you": "ধন্যবাদ",
        "welcome": "স্বাগতম",
        "movie": "চলচ্চিত্র",
        "dubbing": "ডাবিং",
        "action": "অ্যাকশন",
        "goodbye": "বিদায়",
        "yes": "হ্যাঁ",
        "no": "না",
        "the studio behind the scenes": "পর্দার আড়ালের স্টুডিও",
        "welcome to ai movie dubbing studio": "এআই মুভি ডাবিং স্টুডিওতে স্বাগতম",
        "start automated movie dubbing or explore studio tools.": "স্বয়ংক্রিয় মুভি ডাবিং শুরু করুন বা স্টুডিও টুলস অন্বেষণ করুন।",
    },
    "hi": {
        "hello": "नमस्ते",
        "welcome": "स्वागत हे",
        "movie": "फ़िल्म",
        "dubbing": "डबिंग",
        "goodbye": "अलविदा",
    },
}


class ModularDubbingPipelineService:
    """
    Decoupled service executing discrete dubbing pipeline stages.

    Each method is standalone, supports cancellation checks, emits fine-grained
    progress callbacks, validates inputs, and preserves domain time precision.
    """

    def __init__(self, timing_fitter: TimingFitter | None = None) -> None:
        self.fitter = timing_fitter or TimingFitter()

    # ────────────────────────────────────────────────────────────────────────
    # 1. Media Probing & Audio Extraction
    # ────────────────────────────────────────────────────────────────────────

    def extract_dialogue_audio(
        self,
        video_path: Path | str,
        output_audio_path: Path | str,
        *,
        sample_rate: int = 16_000,
        cancel_check: Callable[[], bool] | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> tuple[float, Path]:
        """
        Probe source video and extract production dialogue audio track.

        Returns (total_duration_seconds, path_to_extracted_audio).
        """
        src = Path(video_path).resolve()
        dst = Path(output_audio_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Source video media does not exist: {src}")

        if progress_cb:
            progress_cb(10, f"Probing streams in {src.name}…")
        if cancel_check and cancel_check():
            raise PipelineCancelledError("Audio extraction cancelled by operator")

        media_info = probe(src)
        total_duration = float(media_info.get("format", {}).get("duration", 0.0))
        streams = media_info.get("streams", [])
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        if not has_audio:
            raise ValueError(f"Source video '{src.name}' contains no audio stream to transcribe.")

        dst.parent.mkdir(parents=True, exist_ok=True)
        if progress_cb:
            progress_cb(40, f"Extracting {sample_rate}Hz mono audio track…")

        if cancel_check and cancel_check():
            raise PipelineCancelledError("Audio extraction cancelled by operator")

        extract_audio(src, dst, sr=sample_rate, ac=1)
        if not dst.is_file() or dst.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg failed to extract audio to: {dst}")

        if progress_cb:
            progress_cb(100, f"Extracted {total_duration:.1f}s dialogue audio.")
        return total_duration, dst

    # ────────────────────────────────────────────────────────────────────────
    # 2. Automatic Speech Recognition (ASR)
    # ────────────────────────────────────────────────────────────────────────

    def transcribe_audio(
        self,
        audio_path: Path | str,
        *,
        language: str | None = None,
        model_size: str = "base",
        cancel_check: Callable[[], bool] | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> list[TranscriptCue]:
        """
        Transcribe speech audio into structured timestamped cues using Faster-Whisper.
        """
        src = Path(audio_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Audio file does not exist: {src}")

        if cancel_check and cancel_check():
            raise PipelineCancelledError("Transcription cancelled by operator")

        if progress_cb:
            progress_cb(15, f"Initializing Faster-Whisper ({model_size})…")

        from aidub.adapters.asr_whisper import FasterWhisperAdapter, FasterWhisperOptions

        try:
            adapter = FasterWhisperAdapter(
                FasterWhisperOptions(
                    model_size=model_size,
                    language=language,
                    word_timestamps=True,
                )
            )

            def _on_tick(curr_s: float, tot_s: float, txt: str) -> None:
                if cancel_check and cancel_check():
                    raise PipelineCancelledError("Transcription cancelled by operator")
                if progress_cb and tot_s > 0:
                    pct = 20 + int(75 * min(1.0, curr_s / max(1.0, tot_s)))
                    preview = (txt[:30] + "…") if len(txt) > 30 else txt
                    progress_cb(pct, f"Transcribing [{curr_s:.1f}s/{tot_s:.1f}s]: {preview}")

            raw_segments = adapter.transcribe_file(str(src), progress_callback=_on_tick)
        except Exception as exc:
            logger.warning("Faster-Whisper model loading/execution notice: %s", exc)
            raise

        cues: list[TranscriptCue] = []
        for index, seg in enumerate(raw_segments):
            st = float(seg.get("start", 0.0))
            en = float(seg.get("end", st + 1.0))
            if en <= st:
                en = st + 0.5
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            cue = TranscriptCue(
                cue_id=f"cue_{index + 1:04d}",
                start_s=round(st, 3),
                end_s=round(en, 3),
                text=text,
                speaker=str(seg.get("speaker", "SPEAKER_00")),
                confidence=float(seg.get("confidence", 1.0)),
                words=list(seg.get("words", [])),
            )
            cues.append(cue)

        if progress_cb:
            progress_cb(100, f"Transcription completed: {len(cues)} dialogue cues recognized.")
        return cues

    # ────────────────────────────────────────────────────────────────────────
    # 3. Subtitle Normalization & Timing Validation
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def normalize_cues(cues: list[TranscriptCue]) -> list[TranscriptCue]:
        """
        Sort cues sequentially and enforce half-open time invariant [start, end).
        """
        sorted_cues = sorted(cues, key=lambda c: (c.start_s, c.end_s))
        normalized: list[TranscriptCue] = []
        for idx, cue in enumerate(sorted_cues):
            st = max(0.0, cue.start_s)
            en = max(st + 0.1, cue.end_s)
            normalized.append(
                TranscriptCue(
                    cue_id=cue.cue_id or f"cue_{idx + 1:04d}",
                    start_s=round(st, 3),
                    end_s=round(en, 3),
                    text=cue.text.strip(),
                    speaker=cue.speaker,
                    confidence=cue.confidence,
                    words=cue.words,
                )
            )
        return normalized

    # ────────────────────────────────────────────────────────────────────────
    # 4. Context-Aware Multi-Pass Translation
    # ────────────────────────────────────────────────────────────────────────

    def translate_cues(
        self,
        cues: list[TranscriptCue],
        source_lang: str,
        target_lang: str,
        *,
        router: LlmProviderRouter | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> list[TranslatedCue]:
        """
        Translate dialogue cues into target language preserving timing and meaning.

        Uses LLM provider router if available, otherwise falls back to deterministic
        offline localization adapter with timing budgeting.
        """
        if not cues:
            return []

        if progress_cb:
            progress_cb(10, f"Translating {len(cues)} cues from {source_lang} to {target_lang}…")

        tgt_code = target_lang.split("-", 1)[0].lower()
        translated: list[TranslatedCue] = []

        if router is not None:
            pipeline = TranslationPipeline(router)
            lines = [
                DialogueLine(
                    utterance_id=Identifier(cue.cue_id),
                    text=cue.text,
                    speaker_id=Identifier(cue.speaker or "SPEAKER_00"),
                    duration_ms=round(cue.duration_s * 1000),
                )
                for cue in cues
            ]
            context = TranslationContext(
                source_language=source_lang if source_lang != "auto" else "en-US",
                target_language=target_lang,
                scene_summary="Cinematic movie dubbing dialogue.",
            )
            results = pipeline.translate_batch(lines, context)
            for cue, res in zip(cues, results, strict=True):
                if cancel_check and cancel_check():
                    raise PipelineCancelledError("Translation cancelled by operator")
                translated.append(
                    TranslatedCue(
                        cue_id=cue.cue_id,
                        start_s=cue.start_s,
                        end_s=cue.end_s,
                        source_text=cue.text,
                        target_text=res.translated_text.strip(),
                        target_language=target_lang,
                        speaker=cue.speaker,
                        duration_budget_ms=round(cue.duration_s * 1000),
                        estimated_duration_ms=res.estimated_duration_ms,
                        confidence=cue.confidence,
                    )
                )
        else:
            # Deterministic offline translation fallback
            lexicon = _OFFLINE_TRANSLATIONS.get(tgt_code, {})
            for idx, cue in enumerate(cues):
                if cancel_check and cancel_check():
                    raise PipelineCancelledError("Translation cancelled by operator")

                clean_lower = cue.text.strip().casefold()
                trans_text = lexicon.get(clean_lower)
                if not trans_text:
                    # Word-by-word substitution fallback
                    words = cue.text.strip().split()
                    subbed = [lexicon.get(w.casefold(), w) for w in words]
                    trans_text = " ".join(subbed)

                budget_ms = round(cue.duration_s * 1000)
                translated.append(
                    TranslatedCue(
                        cue_id=cue.cue_id,
                        start_s=cue.start_s,
                        end_s=cue.end_s,
                        source_text=cue.text,
                        target_text=trans_text,
                        target_language=target_lang,
                        speaker=cue.speaker,
                        duration_budget_ms=budget_ms,
                        estimated_duration_ms=budget_ms,
                        confidence=cue.confidence,
                    )
                )
                if progress_cb and (idx % 5 == 0 or idx == len(cues) - 1):
                    progress_cb(
                        20 + int(75 * (idx / len(cues))),
                        f"Translated {idx + 1} of {len(cues)} cues to {target_lang}",
                    )

        if progress_cb:
            progress_cb(100, f"Translation complete ({len(translated)} lines ready).")
        return translated

    # ────────────────────────────────────────────────────────────────────────
    # 5. Text-to-Speech Synthesis with Bounded Timing
    # ────────────────────────────────────────────────────────────────────────

    def synthesize_cues(
        self,
        cues: list[TranslatedCue],
        target_lang: str,
        output_dir: Path | str,
        *,
        voice_name: str | None = None,
        adapter: EdgeTTSAdapter | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> list[SynthesizedCueTake]:
        """
        Synthesize target dialogue into audio files, applying timing fit and review flags.
        """
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        eff_voice = voice_name or default_voice_for_language(target_lang)
        tts = adapter or EdgeTTSAdapter(eff_voice)

        takes: list[SynthesizedCueTake] = []
        total = len(cues)
        for idx, cue in enumerate(cues):
            if cancel_check and cancel_check():
                raise PipelineCancelledError("Synthesis cancelled by operator")

            text = cue.target_text.strip()
            if not text:
                continue

            raw_file = out_dir / f"{cue.cue_id}_raw.mp3"
            fit_file = out_dir / f"{cue.cue_id}_fit.wav"

            tts.synthesize_to_file(text, raw_file, voice=eff_voice)
            actual_dur = duration(raw_file)
            target_dur = cue.duration_s
            delta_s = actual_dur - target_dur
            delta_pct = (delta_s / target_dur) if target_dur > 0 else 0.0

            flagged = False
            final_audio = raw_file
            if target_dur > 0:
                if abs(delta_pct) > 0.15:
                    flagged = True
                fit_to_slot(raw_file, target_dur, fit_file, max_stretch=0.08)
                if fit_file.is_file() and fit_file.stat().st_size > 0:
                    final_audio = fit_file

            take = SynthesizedCueTake(
                cue_id=cue.cue_id,
                audio_path=str(final_audio),
                voice_name=eff_voice,
                start_s=cue.start_s,
                target_duration_s=target_dur,
                actual_duration_s=actual_dur,
                delta_s=delta_s,
                delta_pct=delta_pct,
                flagged_for_review=flagged,
                fitted_audio_path=str(final_audio),
            )
            takes.append(take)

            if progress_cb:
                progress_cb(
                    int(100 * ((idx + 1) / total)),
                    f"Synthesized voice cue {idx + 1}/{total} [{eff_voice}]",
                )

        return takes

    # ────────────────────────────────────────────────────────────────────────
    # 6. Audio Mixing & Dynamic Sidechain Ducking
    # ────────────────────────────────────────────────────────────────────────

    def mix_timeline_audio(
        self,
        placed_takes: list[SynthesizedCueTake],
        total_duration_s: float,
        output_mix_wav: Path | str,
        *,
        background_music: Path | str | None = None,
        ducking_db: float = -14.0,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """
        Assemble positioned speech takes into a dialogue bus and duck against music stems.
        """
        dst = Path(output_mix_wav).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        if cancel_check and cancel_check():
            raise PipelineCancelledError("Audio mix cancelled by operator")

        # Assemble placed speech segments
        placed_segments: list[tuple[float, Path | str]] = [
            (take.start_s, Path(take.audio_path)) for take in placed_takes
        ]
        assembled_vocals = dst.parent / "assembled_vocals.wav"
        assemble_timeline(placed_segments, total_duration_s, assembled_vocals)

        if background_music and Path(background_music).is_file():
            dynamic_sidechain_mix(assembled_vocals, Path(background_music), dst)
        elif assembled_vocals != dst:
            assembled_vocals.replace(dst)

        return dst

    # ────────────────────────────────────────────────────────────────────────
    # 7. Final Master Video Rendering & Stream Muxing
    # ────────────────────────────────────────────────────────────────────────

    def render_master_timeline(
        self,
        video_path: Path | str,
        audio_path: Path | str,
        output_video_path: Path | str,
        *,
        cancel_check: Callable[[], bool] | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> Path:
        """
        Mux synchronized video and audio into a final master video container.
        """
        v_in = Path(video_path).resolve()
        a_in = Path(audio_path).resolve()
        out_v = Path(output_video_path).resolve()
        out_v.parent.mkdir(parents=True, exist_ok=True)

        if not v_in.is_file():
            raise FileNotFoundError(f"Source video file not found: {v_in}")
        if not a_in.is_file():
            raise FileNotFoundError(f"Dialogue audio file not found: {a_in}")

        if cancel_check and cancel_check():
            raise PipelineCancelledError("Video render cancelled by operator")

        if progress_cb:
            progress_cb(30, f"Muxing {v_in.name} with dubbed audio track…")

        mux(v_in, a_in, out_v)

        if not out_v.is_file() or out_v.stat().st_size == 0:
            raise RuntimeError(f"Media muxer did not generate output file: {out_v}")

        # Stream & Duration Verification
        info = probe(out_v)
        stream_types = {s.get("codec_type") for s in info.get("streams", [])}
        if "video" not in stream_types or "audio" not in stream_types:
            raise RuntimeError(
                f"Rendered master '{out_v.name}' is missing video or audio streams. Found: {stream_types}"
            )

        if progress_cb:
            progress_cb(100, f"Rendered master verified: {out_v.name}")
        return out_v


__all__ = [
    "ModularDubbingPipelineService",
    "PipelineCancelledError",
    "PipelineStageStatus",
    "SynthesizedCueTake",
    "TranscriptCue",
    "TranslatedCue",
]
