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
from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter, default_voice_for_language
from aidub.application.timing_fitter import TimingFitter
from aidub.application.translation_pipeline import (
    DialogueLine,
    TranslationContext,
    TranslationPipeline,
)
from aidub.contracts.base import Identifier
from aidub.media.assemble import assemble_timeline, fit_to_slot
from aidub.media.ffmpeg_ops import (
    _ffmpeg_exe,
    _run,
    duration,
    extract_audio,
    mix,
    mux,
    probe,
    to_16k_mono,
)
from aidub.media.stem_separator import separate_stems
from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.errors import ErrorKind, PipelineError
from aidub.pipeline.manifest import PipelineManifest, PipelineOutputs
from aidub.pipeline.utterance_store import UtteranceStore
from aidub.providers.factory import build_router_from_config
from aidub.providers.router import LlmProviderRouter
from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt

logger = logging.getLogger(__name__)
PIPELINE_VERSION = 2


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
    sample: _TimingSample = {"stage": stage_name, "duration_ms": 0}
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
    ASR -> Translation -> Target-Language TTS -> Timeline Assembly -> Mixing -> Muxing.

    Integrates checkpointing (resumable runs via manifest & UtteranceStore),
    benchmarking, VRAM stage management, and bilingual subtitle export.

    Required production stages fail closed when their model, provider, or media
    runtime is unavailable. A rendered source passthrough is never reported as a dub.
    """

    def __init__(
        self,
        config: PipelineConfig,
        *,
        progress_callback: Callable[[str, int, str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.cfg = config
        self.cfg.output.parent.mkdir(parents=True, exist_ok=True)
        self.work_dir = Path(config.work_dir or config.output.parent / f"{config.output.stem}_work")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = PipelineManifest.load(self.work_dir)
        self.router: LlmProviderRouter | None = None
        self.fitter = TimingFitter()
        self._progress_callback = progress_callback
        self._cancel_requested = cancel_requested

    def _progress(self, stage: str, percent: int, message: str) -> None:
        if self._cancel_requested is not None and self._cancel_requested():
            raise PipelineCancelled("dubbing job cancelled by operator")
        if self._progress_callback is not None:
            self._progress_callback(stage, percent, message)

    def _validate_prerequisites(self) -> None:
        """Validate the real components selected for this run before media work starts."""
        import os

        from aidub.adapters.voice.edge_tts_adapter import default_voice_for_language
        from aidub.diagnostics.dubbing import collect_dubbing_diagnostics

        report = collect_dubbing_diagnostics()
        required_names = {"ffmpeg", "ffmpeg/ffprobe", "faster-whisper"}
        if self.cfg.dub:
            required_names.update(
                {"edge-tts", "edge-tts reachability", "llm provider", "llm_provider"}
            )
        if self.cfg.keep_music:
            required_names.add("demucs")
        # Check pyannote if explicitly configured with an auth token
        if self.cfg.diarize and (os.environ.get("PYANNOTE_TOKEN") or os.environ.get("HF_TOKEN")):
            required_names.update({"pyannote", "pyannote token"})

        if self.cfg.lipsync:
            env_var = (
                "AIDUB_LATENTSYNC_COMMAND"
                if self.cfg.lipsync_tier == "cinema_quality"
                else "AIDUB_MUSETALK_COMMAND"
            )
            if not os.environ.get(env_var):
                raise PipelineError(
                    ErrorKind.DEPENDENCY,
                    "lipsync_not_configured",
                    f"Lip-sync is enabled ({self.cfg.lipsync_tier}), but {env_var} is not configured. "
                    f"Set {env_var} to the installed model command using {{video}}, {{audio}}, and {{output}} placeholders.",
                )

        missing = [
            check for check in report.checks if check.name in required_names and not check.ok
        ]
        if missing:
            details = "\n".join(
                f"{check.name}: {check.detail}" + (f". {check.fix}" if check.fix else "")
                for check in missing
            )
            raise PipelineError(
                ErrorKind.DEPENDENCY,
                "dubbing_dependencies_missing",
                "Dubbing stopped before media processing because required components are missing:\n"
                + details,
            )

        if self.cfg.dub and self.cfg.voice_name is None:
            try:
                default_voice_for_language(self.cfg.tgt_lang)
            except ValueError as exc:
                raise PipelineError(
                    ErrorKind.DEPENDENCY,
                    "unsupported_target_voice",
                    str(exc),
                ) from exc

        if self.cfg.dub:
            try:
                self.router = build_router_from_config()
            except Exception as exc:
                raise PipelineError(
                    ErrorKind.DEPENDENCY,
                    "translation_provider_unavailable",
                    f"The configured translation provider is unavailable: {exc}",
                ) from exc

    def _prepare_manifest(self) -> None:
        """Discard completion claims from old code, inputs, or run settings."""
        source = self.cfg.input.resolve()
        stat = source.stat()
        source_signature = f"{stat.st_size}:{stat.st_mtime_ns}"
        config_signature = json.dumps(
            {
                "src_lang": self.cfg.src_lang,
                "tgt_lang": self.cfg.tgt_lang,
                "dub": self.cfg.dub,
                "keep_music": self.cfg.keep_music,
                "diarize": self.cfg.diarize,
                "lipsync": self.cfg.lipsync,
                "lipsync_tier": self.cfg.lipsync_tier,
                "asr_model": self.cfg.asr_model,
                "voice_name": self.cfg.voice_name,
                "max_stretch": self.cfg.max_stretch,
            },
            sort_keys=True,
        )
        stale = (
            self.manifest.pipeline_version != PIPELINE_VERSION
            or self.manifest.input_url != str(source)
            or self.manifest.target_language != self.cfg.tgt_lang
            or self.manifest.source_signature != source_signature
            or self.manifest.config_signature != config_signature
        )
        if stale:
            if self.manifest.stages:
                logger.warning(
                    "Invalidating cached stages because the pipeline version, input, or settings changed"
                )
            self.manifest.stages.clear()
            self.manifest.pipeline_version = PIPELINE_VERSION
            self.manifest.input_url = str(source)
            self.manifest.target_language = self.cfg.tgt_lang
            self.manifest.source_signature = source_signature
            self.manifest.config_signature = config_signature
            self.manifest.save()

    def run(self) -> PipelineOutputs:
        """Execute complete end-to-end dubbing job."""
        bench: list[_TimingSample] = []
        if not self.cfg.input.is_file():
            raise PipelineError(
                ErrorKind.USAGE,
                "input_not_found",
                f"input media does not exist: {self.cfg.input}",
            )
        self._progress("ingest", 2, "Validating source media")
        if self.cfg.output.resolve() == self.cfg.input.resolve():
            raise PipelineError(
                ErrorKind.USAGE,
                "output_matches_input",
                "The output path must not point to the original source movie.",
            )
        if self.cfg.output.exists():
            if getattr(self.cfg, "overwrite", False):
                self.cfg.output.unlink()
            else:
                raise PipelineError(
                    ErrorKind.USAGE,
                    "output_already_exists",
                    f"Refusing to replace an existing output file: {self.cfg.output}. Pass --overwrite to replace it.",
                )
        self._validate_prerequisites()
        self._prepare_manifest()
        info = probe(self.cfg.input)
        total_dur = float(info["format"]["duration"])
        stream_types = {stream.get("codec_type") for stream in info.get("streams", [])}
        if "video" not in stream_types or "audio" not in stream_types:
            raise PipelineError(
                ErrorKind.USAGE,
                "source_missing_audio_or_video",
                "The source movie must contain at least one video stream and one audio stream.",
            )

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

        # Stage 2: Separate stems when the selected run profile keeps original music.
        vocals: Path
        music: Path | None
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
                if not music.exists():
                    music = None
                self._progress("separate_stems", 18, "Reusing validated separated stems")
        else:
            vocals, music = wav_hq, None
            self._progress("separate_stems_skipped", 18, "Stem separation disabled by run profile")

        vocals16 = to_16k_mono(vocals, self.work_dir / "vocals16.wav")

        # Stage 3: Run speaker diarization when enabled in the selected run profile.
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
            else:
                self._progress("diarize", 32, "Reusing validated speaker analysis")
        else:
            self._progress("diarize_skipped", 32, "Speaker diarization disabled by run profile")

        # Stage 4: ASR transcription. Never replace missing recognition with scripted text.
        segs: list[dict[str, Any]] = []
        asr_cache = self.work_dir / "asr_segments.json"
        if not self.manifest.is_stage_completed("asr"):
            self._progress("asr", 36, "Transcribing dialogue with timestamps")
            with _timed("asr", bench) as timing:
                asr = FasterWhisperAdapter(FasterWhisperOptions(model_size=self.cfg.asr_model))
                if spk_turns and n_speakers > 1:
                    segs = asr.transcribe_turns(str(vocals16), spk_turns, str(self.work_dir))
                else:
                    segs = asr.transcribe_file(str(vocals16))

                if self.cfg.dub and not _has_speech(segs, total_dur):
                    raise PipelineError(
                        ErrorKind.USAGE,
                        "no_speech_detected",
                        "Speech recognition found no dialogue. No dubbed output was created.",
                    )

            asr_cache.write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
            self.manifest.mark_stage("asr", True, duration_ms=bench[-1]["duration_ms"])
            self.manifest.save()
        elif asr_cache.is_file():
            segs = json.loads(asr_cache.read_text(encoding="utf-8"))
            self._progress("asr", 43, "Reusing validated transcript")

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
                        raise PipelineError(
                            ErrorKind.DEPENDENCY,
                            "translation_provider_missing",
                            "A real translation provider is required before translating dialogue.",
                        )
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
                        translated_text = result.translated_text.strip()
                        if not translated_text:
                            raise PipelineError(
                                ErrorKind.INTERNAL,
                                "empty_translation",
                                "The translation provider returned an empty dialogue line.",
                            )
                        segment["tgt"] = translated_text
                        segment["translation_passes"] = list(result.passes_completed)
                        segment["timing_within_tolerance"] = result.within_tolerance

                    store.save_utterances(segs)
                self.manifest.mark_stage("translate", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                stored, _metadata = store.load_utterances()
                if stored:
                    segs = stored
                self._progress("translate", 56, "Reusing validated translations")

        # Stage 6: Voice Synthesis (Edge-TTS Bengali default)
        placed_segments: list[tuple[float, Path | str]] = []
        if self.cfg.dub and segs:
            if not self.manifest.is_stage_completed("tts"):
                self._progress("tts", 61, "Synthesizing consent-approved character voices")
                with _timed("tts", bench) as timing:
                    from aidub.ai.voice.character_cloning_engine import CharacterDetectionEngine
                    from aidub.ai.voice.emotion_engine import EmotionEngine

                    emotion_engine = EmotionEngine()
                    char_engine = CharacterDetectionEngine()
                    characters = char_engine.detect_movie_characters(
                        diarization_segments=segs,
                        target_language=self.cfg.tgt_lang,
                    )
                    char_map = {str(c.character_id): c for c in characters}

                    tts = EdgeTTSAdapter(
                        self.cfg.voice_name or default_voice_for_language(self.cfg.tgt_lang)
                    )
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

                        spk_key = str(seg.get("speaker", "SPEAKER_00"))
                        char = char_map.get(spk_key) or (characters[0] if characters else None)
                        char_voices = self.cfg.character_voices or {}
                        voice = (
                            char_voices.get(spk_key)
                            or (char_voices.get(char.canonical_name) if char else None)
                            or self.cfg.voice_name
                            or (char.recommended_base_voice if char else None)
                            or default_voice_for_language(self.cfg.tgt_lang)
                        )

                        start_time = float(seg.get("start", 0.0))
                        end_time = float(seg.get("end", start_time + 1.0))
                        target_dur = max(0.2, end_time - start_time)
                        char_name = char.canonical_name if char else f"Speaker {spk_key}"

                        raw_seg_wav = self.work_dir / f"seg_{i:03d}.mp3"
                        fit_wav_target = self.work_dir / f"seg_{i:03d}_fit.wav"

                        if not raw_seg_wav.is_file() or raw_seg_wav.stat().st_size == 0:

                            def _synth_cb(
                                t_text: str,
                                out_p: Path,
                                r_str: str,
                                p_str: str,
                                current_voice: str = voice,
                                current_char: Any = char,
                            ) -> None:
                                eff_rate = r_str
                                eff_pitch = p_str
                                if current_char and current_char.timbre_rate_offset:
                                    c_rate = int(
                                        current_char.timbre_rate_offset.replace("%", "").replace(
                                            "+", ""
                                        )
                                        or 0
                                    )
                                    e_rate = int(r_str.replace("%", "").replace("+", "") or 0)
                                    eff_rate = f"{c_rate + e_rate:+d}%"
                                if current_char and current_char.timbre_pitch_offset:
                                    c_pitch = int(
                                        current_char.timbre_pitch_offset.replace("Hz", "").replace(
                                            "+", ""
                                        )
                                        or 0
                                    )
                                    e_pitch = int(p_str.replace("Hz", "").replace("+", "") or 0)
                                    eff_pitch = f"{c_pitch + e_pitch:+d}Hz"

                                tts.synthesize_to_file(
                                    text=t_text,
                                    output_mp3_path=out_p,
                                    voice=current_voice,
                                    rate=eff_rate,
                                    pitch=eff_pitch,
                                )

                            emo_res, vr_report = emotion_engine.synthesize_verified_line(
                                text=tgt_text,
                                output_path=raw_seg_wav,
                                synth_fn=_synth_cb,
                                utterance_id=str(start_time),
                                character_name=char_name,
                                audio_path=vocals16 if vocals16.is_file() else None,
                                start_s=start_time,
                                end_s=end_time,
                                scene_context=f"Cinematic dialogue for {char_name}",
                                target_duration_s=target_dur,
                            )
                            logger.info(
                                "Dubbed seg %d: Emotion=%s, Accuracy=%.2f, Pitch=%+dHz, Rate=%+d%%",
                                i,
                                emo_res.primary_emotion,
                                vr_report.accuracy_score,
                                vr_report.corrective_pitch_applied_hz,
                                vr_report.corrective_rate_applied_percent,
                            )

                        at_s = max(float(seg["start"]), cursor)
                        nxt_s = float(segs[i + 1]["start"]) if (i + 1) < len(segs) else total_dur
                        room_s = max(0.3, nxt_s - at_s)

                        if not fit_wav_target.is_file() or fit_wav_target.stat().st_size == 0:
                            fit_wav = fit_to_slot(
                                raw_seg_wav,
                                room_s,
                                fit_wav_target,
                                self.cfg.max_stretch,
                            )
                        else:
                            fit_wav = fit_wav_target
                        placed_segments.append((at_s, fit_wav))
                        cursor = at_s + duration(fit_wav)

                self.manifest.mark_stage("tts", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                for index, seg in enumerate(segs):
                    fit_wav = self.work_dir / f"seg_{index:03d}_fit.wav"
                    if fit_wav.is_file():
                        placed_segments.append((float(seg["start"]), fit_wav))
                self._progress("tts", 75, "Reusing validated synthesized dialogue")

        # Stage 7: Timeline Assembly & Loudness Normalization
        dub_vocals = self.work_dir / "dubbed_vocals.wav"
        if self.cfg.dub and placed_segments:
            if not self.manifest.is_stage_completed("assemble"):
                self._progress("assemble", 77, "Fitting dialogue to editorial timing")
                with _timed("assemble", bench) as timing:
                    assemble_timeline(placed_segments, total_dur, dub_vocals)
                self.manifest.mark_stage("assemble", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                self._progress("assemble", 82, "Reusing validated dialogue assembly")

        # Stage 8: Audio Mixing & Muxing
        final_audio_wav = self.work_dir / "dubbed_audio.wav"
        final_audio_m4a = self.work_dir / "dubbed_audio.m4a"
        if music and music.exists() and dub_vocals.exists():
            self._progress("mix", 86, "Mixing dialogue against original stems")
            with _timed("mix", bench):
                mix(dub_vocals, music, final_audio_wav)
                mix(dub_vocals, music, final_audio_m4a)
            final_audio = final_audio_wav
        elif dub_vocals.exists():
            final_audio = dub_vocals
        else:
            final_audio = wav_hq

        if self.cfg.dub and not dub_vocals.is_file():
            raise PipelineError(
                ErrorKind.INTERNAL,
                "dubbed_vocals_missing",
                "Voice synthesis completed without a dubbed dialogue track; no master was created.",
            )
        if not final_audio.is_file() or final_audio.stat().st_size == 0:
            raise PipelineError(
                ErrorKind.INTERNAL,
                "final_audio_missing",
                "Audio mixing produced no playable output; no master was created.",
            )

        # Stage 9: Selective Lip-Sync Rendering
        lipsynced_video: Path | None = None
        if self.cfg.lipsync:
            if not self.manifest.is_stage_completed("lipsync"):
                self._progress(
                    "lipsync", 89, f"Synthesizing {self.cfg.lipsync_tier} lip synchronization"
                )
                with _timed("lipsync", bench) as timing:
                    from aidub.adapters.lipsync_base import LipSyncOptions, LipSyncQualityTier
                    from aidub.adapters.lipsync_latentsync import LatentSyncLipSyncEngine
                    from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine

                    tier = (
                        LipSyncQualityTier.CINEMA_QUALITY
                        if self.cfg.lipsync_tier == "cinema_quality"
                        else LipSyncQualityTier.PREVIEW_FAST
                    )
                    ls_engine: LatentSyncLipSyncEngine | MuseTalkLipSyncEngine = (
                        LatentSyncLipSyncEngine()
                        if tier == LipSyncQualityTier.CINEMA_QUALITY
                        else MuseTalkLipSyncEngine()
                    )
                    options = LipSyncOptions(quality_tier=tier)
                    ls_res = ls_engine.synthesize_lip_sync(
                        shot_id=self.cfg.input.stem,
                        source_video_path=str(self.cfg.input),
                        target_audio_path=str(dub_vocals),
                        output_directory=str(self.work_dir),
                        options=options,
                    )
                    lipsynced_video = Path(ls_res.output_video_path)
                self.manifest.mark_stage("lipsync", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                self._progress("lipsync", 91, "Reusing validated lip-synced video")
                preview_f = self.work_dir / f"{self.cfg.input.stem}_musetalk_preview.mp4"
                cinema_f = self.work_dir / f"{self.cfg.input.stem}_latentsync_cinema.mp4"
                lipsynced_video = (
                    preview_f if preview_f.is_file() else (cinema_f if cinema_f.is_file() else None)
                )

        video_for_mux = (
            lipsynced_video
            if (self.cfg.lipsync and lipsynced_video and lipsynced_video.is_file())
            else self.cfg.input
        )

        final_video = self.cfg.output
        self._progress("mux", 94, "Packaging localized master")
        with _timed("mux", bench) as timing:
            mux(video_for_mux, final_audio, final_video)
        if not final_video.is_file() or final_video.stat().st_size == 0:
            raise PipelineError(
                ErrorKind.INTERNAL,
                "master_render_missing",
                "The media muxer did not create a non-empty master file.",
            )
        self.manifest.mark_stage("mux", True, duration_ms=timing["duration_ms"])
        self.manifest.save()

        # Stage 10: Subtitle Export
        origin_srt = write_srt(segs, self.work_dir / "origin_language.srt", translated=False)
        target_srt = write_srt(segs, self.work_dir / "target_language.srt", translated=True)
        bilingual_srt = write_bilingual_srt(
            segs, self.work_dir / "bilingual.srt", LineMode.BILINGUAL_TARGET_BOTTOM
        )

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
            lipsynced_video=str(lipsynced_video) if lipsynced_video else "",
            bench_json=str(bench_file),
            transcript_json=str(store._get_filename()),
        )


__all__ = ["DubbingEngine", "PipelineCancelled"]
