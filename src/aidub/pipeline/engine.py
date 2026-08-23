"""DubbingEngine — Master End-to-End Production Pipeline Orchestrator."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypedDict

from aidub.adapters.asr_whisper import FasterWhisperAdapter, FasterWhisperOptions, _has_speech
from aidub.adapters.diarization_pyannote import PyannoteDiarizationAdapter
from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter
from aidub.application.timing_fitter import TimingFitter
from aidub.application.translation_pipeline import (
    DialogueLine,
    TranslationContext,
    TranslationPipeline,
)
from aidub.contracts.base import Identifier
from aidub.media.assemble import assemble_timeline, fit_to_slot
from aidub.media.ffmpeg_ops import duration, extract_audio, mix, mux, probe, to_16k_mono
from aidub.media.stem_separator import separate_stems
from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.errors import ErrorKind, PipelineError
from aidub.pipeline.manifest import PipelineManifest, PipelineOutputs
from aidub.pipeline.utterance_store import UtteranceStore
from aidub.providers.factory import build_router_from_config
from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt

logger = logging.getLogger(__name__)


class _TimingSample(TypedDict):
    stage: str
    duration_ms: int


@contextmanager
def _timed(
    stage_name: str,
    bench: list[_TimingSample],
) -> Iterator[_TimingSample]:
    """Context manager for timing pipeline execution stages."""
    t0 = time.monotonic()
    sample = {"stage": stage_name, "duration_ms": 0}
    bench.append(sample)
    logger.info(">>> STAGE START: %s", stage_name)
    try:
        yield sample
    finally:
        dur_ms = int((time.monotonic() - t0) * 1000)
        logger.info("<<< STAGE END: %s [%d ms]", stage_name, dur_ms)
        sample["duration_ms"] = dur_ms


class PipelineCancelled(RuntimeError):
    """Raised at a cancellation-safe stage boundary."""


class DubbingEngine:
    """
    Master Production Movie Dubbing Engine.
    
    Orchestrates all 9 stages: Audio Extraction -> Separation -> Diarization ->
    ASR -> Translation -> Voice Cloning -> Timeline Assembly -> Mixing -> Muxing.
    
    Integrates checkpointing (resumable runs via manifest & UtteranceStore),
    benchmarking, VRAM stage management, and bilingual subtitle export.
    """

    def __init__(
        self,
        config: PipelineConfig,
        *,
        progress_callback: Callable[[str, int, str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.cfg = config
        self.work_dir = Path(config.work_dir or config.output.parent / f"{config.output.stem}_work")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = PipelineManifest.load(self.work_dir)
        self.router = None
        self.fitter = TimingFitter()
        self._progress_callback = progress_callback
        self._cancel_requested = cancel_requested

    def _progress(self, stage: str, percent: int, message: str) -> None:
        if self._cancel_requested is not None and self._cancel_requested():
            raise PipelineCancelled("dubbing job cancelled by operator")
        if self._progress_callback is not None:
            self._progress_callback(stage, percent, message)

    def run(self) -> PipelineOutputs:  # noqa: PLR0915
        """Execute complete end-to-end dubbing job."""
        bench: list[_TimingSample] = []
        if not self.cfg.input.is_file():
            raise PipelineError(
                ErrorKind.USAGE,
                "input_not_found",
                f"input media does not exist: {self.cfg.input}",
            )
        self._progress("ingest", 2, "Validating source media")
        info = probe(self.cfg.input)
        total_dur = float(info["format"]["duration"])

        # Stage 1: Audio Extraction
        wav_hq = self.work_dir / "origin_audio.wav"
        if not self.manifest.is_stage_completed("extract_audio"):
            self._progress("extract_audio", 8, "Extracting production audio")
            with _timed("extract_audio", bench) as timing:
                extract_audio(self.cfg.input, wav_hq, sr=44100, ac=2)
            self.manifest.mark_stage("extract_audio", True, duration_ms=timing["duration_ms"])
            self.manifest.save()
        else:
            self._progress("extract_audio", 12, "Reusing validated source audio")

        # Stage 2: Stem Separation
        if self.cfg.keep_music:
            if not self.manifest.is_stage_completed("separate_stems"):
                self._progress("separate_stems", 16, "Separating dialogue, music and effects")
                with _timed("separate_stems", bench) as timing:
                    vocals, music = separate_stems(wav_hq, self.work_dir)
                self.manifest.mark_stage("separate_stems", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                vocals = self.work_dir / "vocals.wav"
                music = self.work_dir / "music.wav"
        else:
            vocals, music = wav_hq, None

        vocals16 = to_16k_mono(vocals, self.work_dir / "vocals16.wav")

        # Stage 3: Diarization
        spk_turns: list[tuple[float, float, int]] = []
        n_speakers = 1
        _ref_windows: dict[int, tuple[float, float]] = {}

        if self.cfg.diarize:
            if not self.manifest.is_stage_completed("diarize"):
                self._progress("diarize", 27, "Detecting speakers and reference windows")
                with _timed("diarize", bench) as timing:
                    adapter = PyannoteDiarizationAdapter()
                    spk_turns, n_speakers, _ref_windows = adapter.turns(str(vocals16))
                self.manifest.mark_stage("diarize", True, duration_ms=timing["duration_ms"])
                self.manifest.save()

        # Stage 4: ASR Transcription
        segs: list[dict[str, Any]] = []
        asr_cache = self.work_dir / "asr_segments.json"
        if not self.manifest.is_stage_completed("asr"):
            self._progress("asr", 36, "Transcribing dialogue with timestamps")
            with _timed("asr", bench) as timing:
                asr = FasterWhisperAdapter(
                    FasterWhisperOptions(model_size=self.cfg.asr_model)
                )
                if spk_turns and n_speakers > 1:
                    segs = asr.transcribe_turns(str(vocals16), spk_turns, str(self.work_dir))
                else:
                    segs = asr.transcribe_file(str(vocals16))

                if not _has_speech(segs, total_dur):
                    logger.warning("No speech detected by ASR hallucination guard — falling back to nodub mode")
                    self.cfg.dub = False
                asr_cache.write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
            self.manifest.mark_stage("asr", True, duration_ms=timing["duration_ms"])
            self.manifest.save()
        elif asr_cache.is_file():
            segs = json.loads(asr_cache.read_text(encoding="utf-8"))

        # Stage 5: Translation & Utterance Storage
        store = UtteranceStore(self.cfg.tgt_lang, self.work_dir)

        if self.cfg.dub and segs:
            if not self.manifest.is_stage_completed("translate"):
                self._progress("translate", 49, f"Localizing dialogue to {self.cfg.tgt_lang}")
                with _timed("translate", bench) as timing:
                    lines = [
                        DialogueLine(
                            utterance_id=Identifier(f"utt-{index:06d}"),
                            text=str(segment.get("text", "")).strip() or "…",
                            speaker_id=Identifier(f"spk-{segment.get('speaker', 0)}"),
                            duration_ms=max(
                                1,
                                round(
                                    (float(segment.get("end", 0)) - float(segment.get("start", 0)))
                                    * 1_000
                                ),
                            ),
                        )
                        for index, segment in enumerate(segs)
                    ]
                    if self.router is None:
                        self.router = build_router_from_config()
                    translated = TranslationPipeline(self.router).translate_batch(
                        lines,
                        TranslationContext(
                            source_language=(
                                self.cfg.src_lang if self.cfg.src_lang != "auto" else "en-US"
                            ),
                            target_language=self.cfg.tgt_lang,
                            scene_summary="Feature-film dialogue requiring natural spoken localization.",
                        ),
                    )
                    for segment, result in zip(segs, translated, strict=True):
                        segment["tgt"] = result.translated_text
                        segment["translation_passes"] = list(result.passes_completed)
                        segment["timing_within_tolerance"] = result.within_tolerance

                    store.save_utterances(segs)
                self.manifest.mark_stage("translate", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                stored, _metadata = store.load_utterances()
                if stored:
                    segs = stored

        # Stage 6: Voice Synthesis (Edge-TTS Bengali default)
        placed_segments: list[tuple[float, Path | str]] = []
        if self.cfg.dub and segs:
            if not self.manifest.is_stage_completed("tts"):
                self._progress("tts", 61, "Synthesizing consent-approved character voices")
                with _timed("tts", bench) as timing:
                    tts = EdgeTTSAdapter()
                    cursor = 0.0

                    for i, seg in enumerate(segs):
                        self._progress(
                            "tts",
                            61 + round(13 * (i / max(1, len(segs)))),
                            f"Synthesizing dialogue {i + 1} of {len(segs)}",
                        )
                        tgt_text = seg.get("tgt", "").strip()
                        if not tgt_text:
                            continue

                        raw_seg_wav = self.work_dir / f"seg_{i:03d}.mp3"
                        tts.synthesize_to_file(tgt_text, raw_seg_wav)

                        at_s = max(float(seg["start"]), cursor)
                        nxt_s = float(segs[i + 1]["start"]) if (i + 1) < len(segs) else total_dur
                        room_s = max(0.3, nxt_s - at_s)

                        fit_wav = fit_to_slot(raw_seg_wav, room_s, self.work_dir / f"seg_{i:03d}_fit.wav", self.cfg.max_stretch)
                        placed_segments.append((at_s, fit_wav))
                        cursor = at_s + duration(fit_wav)

                self.manifest.mark_stage("tts", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                for index, seg in enumerate(segs):
                    fit_wav = self.work_dir / f"seg_{index:03d}_fit.wav"
                    if fit_wav.is_file():
                        placed_segments.append((float(seg["start"]), fit_wav))

        # Stage 7: Timeline Assembly & Loudness Normalization
        dub_vocals = self.work_dir / "dubbed_vocals.wav"
        if self.cfg.dub and placed_segments:
            if not self.manifest.is_stage_completed("assemble"):
                self._progress("assemble", 77, "Fitting dialogue to editorial timing")
                with _timed("assemble", bench) as timing:
                    assemble_timeline(placed_segments, total_dur, dub_vocals)
                self.manifest.mark_stage("assemble", True, duration_ms=timing["duration_ms"])
                self.manifest.save()

        # Stage 8: Audio Mixing & Muxing
        final_audio = self.work_dir / "dubbed_audio.m4a"
        if music and music.exists() and dub_vocals.exists():
            self._progress("mix", 86, "Mixing dialogue against original stems")
            with _timed("mix", bench):
                mix(dub_vocals, music, final_audio)
        elif dub_vocals.exists():
            final_audio = dub_vocals
        else:
            final_audio = wav_hq

        final_video = self.cfg.output
        self._progress("mux", 94, "Packaging localized master")
        with _timed("mux", bench) as timing:
            mux(self.cfg.input, final_audio, final_video)
        self.manifest.mark_stage("mux", True, duration_ms=timing["duration_ms"])
        self.manifest.save()

        # Stage 9: Subtitle Export
        origin_srt = write_srt(segs, self.work_dir / "origin_language.srt", translated=False)
        target_srt = write_srt(segs, self.work_dir / "target_language.srt", translated=True)
        bilingual_srt = write_bilingual_srt(segs, self.work_dir / "bilingual.srt", LineMode.BILINGUAL_TARGET_BOTTOM)

        # Benchmarks export
        bench_file = self.work_dir / "bench.json"
        bench_file.write_text(json.dumps(bench, indent=2), encoding="utf-8")
        self._progress("complete", 100, "Localized master and delivery assets are ready")

        return PipelineOutputs(
            origin_video=str(self.cfg.input),
            origin_audio=str(wav_hq),
            origin_srt=str(origin_srt),
            target_srt=str(target_srt),
            bilingual_srt=str(bilingual_srt),
            dubbed_vocals=str(dub_vocals),
            dubbed_audio=str(final_audio),
            dubbed_video=str(final_video),
            bench_json=str(bench_file),
            transcript_json=str(self.work_dir / "utterance_metadata_bn.json"),
        )


__all__ = ["DubbingEngine", "PipelineCancelled"]
