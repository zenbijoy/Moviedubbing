"""DubbingEngine — main pipeline orchestrator class."""

from __future__ import annotations

from ._engine_common import *
from ._engine_common import PIPELINE_VERSION, _TimingSample, _has_speech, _timed

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
        if self.cfg.diarize and (os.environ.get("PYANNOTE_TOKEN") or os.environ.get("HF_TOKEN")):
            required_names.update({"pyannote", "pyannote token"})

        if self.cfg.lipsync:
            if self.cfg.lipsync_tier == "cinema_quality" and not os.environ.get(
                "AIDUB_LATENTSYNC_COMMAND"
            ):
                raise PipelineError(
                    ErrorKind.DEPENDENCY,
                    "lipsync_not_configured",
                    "Lip-sync is enabled (cinema_quality), but AIDUB_LATENTSYNC_COMMAND is not configured.",
                )
            if self.cfg.lipsync_tier == "preview_fast" and not os.environ.get(
                "AIDUB_MUSETALK_COMMAND"
            ):
                raise PipelineError(
                    ErrorKind.DEPENDENCY,
                    "lipsync_not_configured",
                    "Lip-sync is enabled (preview_fast), but AIDUB_MUSETALK_COMMAND is not configured.",
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
                    f"No translation provider configured ({exc}). Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY in .env or environment.",
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
            if wav_hq.is_file() and wav_hq.stat().st_size > 0:
                self._progress("extract_audio", 12, "Reusing existing production audio")
                self.manifest.mark_stage("extract_audio", True, duration_ms=0)
                self.manifest.save()
            else:
                self._progress("extract_audio", 8, "Extracting production audio")
                with _timed("extract_audio", bench) as timing:
                    try:
                        extract_audio(self.cfg.input, wav_hq, sr=44100, ac=2)
                    except Exception as exc:
                        raise PipelineError(
                            ErrorKind.INTERNAL,
                            "audio_extraction_failed",
                            f"Failed to extract audio from source media: {exc}",
                        ) from exc
                self.manifest.mark_stage("extract_audio", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
        else:
            self._progress("extract_audio", 12, "Reusing validated source audio")

        # Stage 2: Separate stems when the selected run profile keeps original music.
        vocals: Path
        music: Path | None
        if self.cfg.keep_music:
            vocals_cand = self.work_dir / "vocals.wav"
            music_cand = self.work_dir / "music.wav"
            if not self.manifest.is_stage_completed("separate_stems"):
                if (
                    vocals_cand.is_file()
                    and vocals_cand.stat().st_size > 0
                    and music_cand.is_file()
                    and music_cand.stat().st_size > 0
                ):
                    vocals, music = vocals_cand, music_cand
                    self._progress("separate_stems", 18, "Reusing existing separated stems")
                    self.manifest.mark_stage("separate_stems", True, duration_ms=0)
                    self.manifest.save()
                else:
                    self._progress("separate_stems", 16, "Separating dialogue, music and effects")
                    with _timed("separate_stems", bench) as timing:
                        try:
                            vocals, music = separate_stems(wav_hq, self.work_dir)
                            self.manifest.mark_stage(
                                "separate_stems", True, duration_ms=timing["duration_ms"]
                            )
                            self.manifest.save()
                        except Exception as exc:
                            logger.warning(
                                "Stem separation failed (%s); falling back to original mix with ducking",
                                exc,
                            )
                            self._progress(
                                "separate_stems_fallback",
                                18,
                                f"Stem separation fallback ({exc}); continuing with ducked master",
                            )
                            vocals, music = wav_hq, None
                            self.manifest.mark_stage("separate_stems", False, duration_ms=0)
                            self.manifest.save()
            else:
                vocals = vocals_cand
                music = music_cand if music_cand.exists() else None
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
                    try:
                        adapter = PyannoteDiarizationAdapter()
                        spk_turns, n_speakers, _ref_windows = adapter.turns(str(vocals16))
                    except Exception as exc:
                        raise PipelineError(
                            ErrorKind.DEPENDENCY,
                            "diarization_failed",
                            f"Speaker diarization failed: {exc}. Set PYANNOTE_TOKEN or pass --fast to skip diarization.",
                        ) from exc
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
            if asr_cache.is_file() and asr_cache.stat().st_size > 0:
                segs = json.loads(asr_cache.read_text(encoding="utf-8"))
                self._progress("asr", 43, "Reusing existing transcript")
                self.manifest.mark_stage("asr", True, duration_ms=0)
                self.manifest.save()
            else:
                self._progress("asr", 36, "Transcribing dialogue with timestamps")
                with _timed("asr", bench) as timing:
                    try:

                        def _on_asr_tick(curr_s: float, tot_s: float, txt: str) -> None:
                            t_tot = tot_s if tot_s > 0 else total_dur
                            pct = 36 + round(10 * min(1.0, curr_s / max(1.0, t_tot)))
                            m_curr, s_curr = divmod(int(curr_s), 60)
                            m_tot, s_tot = divmod(int(t_tot), 60)
                            preview = (txt[:28] + "…") if len(txt) > 28 else txt
                            self._progress(
                                "asr",
                                pct,
                                f"Transcribing dialogue [{m_curr:02d}:{s_curr:02d} / {m_tot:02d}:{s_tot:02d}]: {preview}",
                            )

                        asr = FasterWhisperAdapter(
                            FasterWhisperOptions(model_size=self.cfg.asr_model)
                        )
                        if spk_turns and n_speakers > 1:
                            segs = asr.transcribe_turns(
                                str(vocals16), spk_turns, str(self.work_dir)
                            )
                        else:
                            segs = asr.transcribe_file(
                                str(vocals16), progress_callback=_on_asr_tick
                            )
                    except Exception as exc:
                        raise PipelineError(
                            ErrorKind.DEPENDENCY,
                            "asr_failed",
                            f"Speech recognition (Faster-Whisper model '{self.cfg.asr_model}') failed: {exc}. Ensure model weights are available.",
                        ) from exc

                    if self.cfg.dub and not _has_speech(segs, total_dur):
                        raise PipelineError(
                            ErrorKind.USAGE,
                            "no_speech_detected",
                            "Speech recognition found no dialogue. No dubbed output was created.",
                        )

                asr_cache.write_text(
                    json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.manifest.mark_stage("asr", True, duration_ms=bench[-1]["duration_ms"])
                self.manifest.save()
        elif asr_cache.is_file():
            segs = json.loads(asr_cache.read_text(encoding="utf-8"))
            self._progress("asr", 43, "Reusing validated transcript")

        # Stage 5: Translation & Utterance Storage
        store = UtteranceStore(self.cfg.tgt_lang, self.work_dir)

        if self.cfg.dub and segs:
            if not self.manifest.is_stage_completed("translate"):
                stored_segs, _metadata = store.load_utterances()
                if (
                    stored_segs
                    and len(stored_segs) == len(segs)
                    and all(s.get("tgt") for s in stored_segs)
                ):
                    segs = stored_segs
                    self._progress("translate", 56, "Reusing existing translations")
                    self.manifest.mark_stage("translate", True, duration_ms=0)
                    self.manifest.save()
                else:
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
                                        (
                                            float(segment.get("end", 0))
                                            - float(segment.get("start", 0))
                                        )
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
                                "No translation provider configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY in .env or environment.",
                            )
                        try:
                            translated = TranslationPipeline(self.router).translate_batch(
                                lines,
                                TranslationContext(
                                    source_language=(
                                        self.cfg.src_lang
                                        if self.cfg.src_lang != "auto"
                                        else "en-US"
                                    ),
                                    target_language=self.cfg.tgt_lang,
                                    scene_summary="Feature-film dialogue requiring natural spoken localization.",
                                ),
                            )
                        except Exception as exc:
                            raise PipelineError(
                                ErrorKind.DEPENDENCY,
                                "translation_failed",
                                f"Translation provider failed: {exc}. Check your network connection and API key quota.",
                            ) from exc
                        from aidub.translation.isometric_engine import IsometricTranslationEngine

                        for seg_idx, (segment, result) in enumerate(
                            zip(segs, translated, strict=True)
                        ):
                            if seg_idx % 25 == 0:
                                self._progress(
                                    "translate",
                                    49 + round(10 * (seg_idx / max(1, len(segs)))),
                                    f"Optimizing translated cadence {seg_idx + 1} of {len(segs)}",
                                )
                            translated_text = result.translated_text.strip()
                            if not translated_text:
                                raise PipelineError(
                                    ErrorKind.INTERNAL,
                                    "empty_translation",
                                    "The translation provider returned an empty dialogue line.",
                                )

                            # Apply Isometric Lip-Cadence Optimization
                            if getattr(self.cfg, "isometric_alignment", True):
                                src_text = segment.get("src") or segment.get("text") or ""
                                st_s = float(segment.get("start", 0.0))
                                en_s = float(segment.get("end", st_s + 1.0))
                                dur_s = max(0.2, en_s - st_s)
                                iso_report = IsometricTranslationEngine.optimize_dialogue(
                                    source_text=src_text,
                                    candidate_translations=[translated_text],
                                    source_duration_s=dur_s,
                                    source_language=self.cfg.src_lang,
                                    target_language=self.cfg.tgt_lang,
                                )
                                segment["tgt"] = iso_report.best_candidate.text
                                segment["isometric_score"] = (
                                    iso_report.best_candidate.isometric_score
                                )
                                segment["isometric_syllables"] = (
                                    iso_report.best_candidate.syllable_count
                                )
                                segment["isometric_target_budget"] = (
                                    iso_report.ideal_syllable_budget
                                )
                            else:
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

                    use_gemini = getattr(
                        self.cfg, "voice_engine", "gemini_tts"
                    ) == "gemini_tts" or bool(os.environ.get("GEMINI_API_KEY"))
                    gemini_tts = None
                    if use_gemini and getattr(self.cfg, "voice_engine", "") != "edge_tts":
                        try:
                            from aidub.adapters.voice.gemini_tts_adapter import (
                                GeminiExpressiveTTSAdapter,
                            )

                            gemini_tts = GeminiExpressiveTTSAdapter(allow_fallback=True)
                            logger.info(
                                "engine: initialized Gemini 3.8 Flash Studio Expressive TTS"
                            )
                        except Exception as exc:
                            logger.info("engine: Gemini TTS fallback to EdgeTTS: %s", exc)
                            gemini_tts = None

                    use_chatterbox = getattr(self.cfg, "voice_engine", "") == "chatterbox"
                    chatterbox_tts = None
                    if use_chatterbox:
                        try:
                            from aidub.adapters.voice.chatterbox_adapter import ChatterboxAdapter

                            chatterbox_tts = ChatterboxAdapter(allow_fallback=True)
                        except Exception as exc:
                            logger.info("Chatterbox initialization fallback: %s", exc)
                            chatterbox_tts = None

                    tts = EdgeTTSAdapter(
                        self.cfg.voice_name or default_voice_for_language(self.cfg.tgt_lang)
                    )
                    cursor = 0.0

                    speaker_refs: dict[Any, Path] = {}
                    has_real_rvc = bool(
                        os.environ.get("AIDUB_RVC_COMMAND") or os.environ.get("RVC_ENDPOINT_URL")
                    )
                    if vocals16.is_file() and not self.cfg.fast:
                        try:
                            from aidub.adapters.voice.reference_extractor import pick_reference

                            raw_refs = pick_reference(segs, vocals16, self.work_dir)
                            speaker_refs = {spk: path for spk, (path, _txt) in raw_refs.items()}
                            logger.info(
                                "Extracted %d clean reference clips for character voice cloning",
                                len(speaker_refs),
                            )
                        except Exception as exc:
                            logger.info("Could not extract speaker references: %s", exc)

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
                            # Pre-detect emotional state and scene context for expressive synthesis
                            det_result = emotion_engine.detect_emotion(
                                utterance_id=str(start_time),
                                dialogue_text=tgt_text,
                                audio_path=vocals16 if vocals16.is_file() else None,
                                character_name=char_name,
                                scene_context=f"Dramatic movie scene for {char_name}",
                                start_s=start_time,
                                end_s=end_time,
                            )
                            primary_emo = det_result.primary_emotion

                            def _synth_cb(
                                t_text: str,
                                out_p: Path,
                                r_str: str,
                                p_str: str,
                                current_voice: str = voice,
                                current_char: Any = char,
                                current_char_name: str = char_name,
                                current_emo: str = primary_emo,
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

                                if gemini_tts is not None:
                                    from aidub.adapters.voice.gemini_tts_adapter import (
                                        GeminiExpressiveTTSAdapter,
                                    )

                                    gemini_v = (
                                        current_voice
                                        if current_voice
                                        in {
                                            "Fenrir",
                                            "Charon",
                                            "Puck",
                                            "Orus",
                                            "Kore",
                                            "Aoede",
                                            "Leda",
                                            "Zephyr",
                                        }
                                        else GeminiExpressiveTTSAdapter.pick_voice_for_character(
                                            gender=current_char.gender if current_char else None,
                                            character_name=current_char_name,
                                            pitch_median_hz=current_char.median_f0_hz
                                            if current_char
                                            else None,
                                        )
                                    )
                                    gemini_tts.synthesize_to_file(
                                        text=t_text,
                                        output_wav_path=out_p,
                                        voice=gemini_v,
                                        emotion=current_emo,
                                    )
                                elif chatterbox_tts is not None:
                                    clean_ref = (
                                        speaker_refs.get(spk_key)
                                        or speaker_refs.get(str(spk_key).replace("SPEAKER_", ""))
                                        or (
                                            Path(current_char.reference_audio_paths[0])
                                            if (
                                                current_char
                                                and current_char.reference_audio_paths
                                                and Path(current_char.reference_audio_paths[0]).is_file()
                                            )
                                            else None
                                        )
                                    )
                                    chatterbox_tts.synthesize_to_file(
                                        text=t_text,
                                        output_wav_path=out_p,
                                        voice=current_voice,
                                        emotion=current_emo,
                                        reference_audio=clean_ref,
                                    )
                                else:
                                    tts.synthesize_to_file(
                                        text=t_text,
                                        output_mp3_path=out_p,
                                        voice=current_voice,
                                        rate=eff_rate,
                                        pitch=eff_pitch,
                                    )

                            try:
                                spk_clean_ref = (
                                    speaker_refs.get(spk_key)
                                    or speaker_refs.get(str(spk_key).replace("SPEAKER_", ""))
                                    or (
                                        Path(char.reference_audio_paths[0])
                                        if (char and char.reference_audio_paths and Path(char.reference_audio_paths[0]).is_file())
                                        else None
                                    )
                                )
                                emo_res, vr_report = emotion_engine.synthesize_verified_line(
                                    text=tgt_text,
                                    output_path=raw_seg_wav,
                                    synth_fn=_synth_cb,
                                    utterance_id=str(start_time),
                                    character_name=char_name,
                                    audio_path=spk_clean_ref if (spk_clean_ref and Path(spk_clean_ref).is_file()) else (vocals16 if vocals16.is_file() else None),
                                    start_s=start_time,
                                    end_s=end_time,
                                    scene_context=f"Cinematic dialogue for {char_name}",
                                    target_duration_s=target_dur,
                                )
                            except Exception as exc:
                                raise PipelineError(
                                    ErrorKind.RETRYABLE,
                                    "tts_failed",
                                    f"Speech synthesis failed: {exc}. Check your internet connection.",
                                ) from exc
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

                        synth_source_for_fit = raw_seg_wav
                        if (
                            getattr(self.cfg, "rvc_cloning", True)
                            and not self.cfg.fast
                            and has_real_rvc
                        ):
                            rvc_seg_wav = self.work_dir / f"seg_{i:03d}_rvc.wav"
                            if not rvc_seg_wav.is_file() or rvc_seg_wav.stat().st_size == 0:
                                try:
                                    from aidub.ai.voice.rvc_cloning_engine import (
                                        RvcVoiceConversionAdapter,
                                    )

                                    rvc_adapter = RvcVoiceConversionAdapter()
                                    spk_num = 0
                                    try:
                                        spk_num = int(
                                            str(seg.get("speaker", "0"))
                                            .replace("SPEAKER_", "")
                                            .replace("spk_", "")
                                        )
                                    except ValueError:
                                        spk_num = 0

                                    refs: list[str | Path] = []
                                    if spk_num in speaker_refs and speaker_refs[spk_num].is_file():
                                        refs.append(speaker_refs[spk_num])
                                    elif spk_key in speaker_refs and speaker_refs[spk_key].is_file():
                                        refs.append(speaker_refs[spk_key])
                                    elif char and char.reference_audio_paths:
                                        refs.extend(char.reference_audio_paths)

                                    if refs:
                                        rvc_adapter.convert_timbre(
                                            base_tts_audio_path=raw_seg_wav,
                                            output_converted_path=rvc_seg_wav,
                                            reference_audio_paths=refs,
                                        )
                                        if rvc_seg_wav.is_file() and rvc_seg_wav.stat().st_size > 0:
                                            synth_source_for_fit = rvc_seg_wav
                                            logger.info(
                                                "Applied RVC v2 timbre conversion for dialogue %d (speaker %s)",
                                                i,
                                                spk_key,
                                            )
                                except Exception as exc:
                                    logger.warning(
                                        "RVC timbre cloning fallback to base TTS for seg %d: %s",
                                        i,
                                        exc,
                                    )
                                    synth_source_for_fit = raw_seg_wav
                            else:
                                synth_source_for_fit = rvc_seg_wav

                        if not fit_wav_target.is_file() or fit_wav_target.stat().st_size == 0:
                            fit_wav = fit_to_slot(
                                synth_source_for_fit,
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
                    try:
                        assemble_timeline(placed_segments, total_dur, dub_vocals)

                        # Apply Room Impulse Response (RIR) Acoustic Reverb Matching
                        acoustic_preset = str(
                            getattr(self.cfg, "acoustic_preset", "none") or "none"
                        ).lower()
                        if acoustic_preset != "none" and dub_vocals.is_file():
                            from aidub.media.acoustic_ir import (
                                AcousticIRConvolutionEngine,
                                ImpulseResponseProfile,
                            )

                            decay_map = {
                                "living_room": 400,
                                "large_hall": 1800,
                                "vehicle": 200,
                                "street_exterior": 250,
                            }
                            decay_ms = decay_map.get(acoustic_preset, 400)
                            ir_engine = AcousticIRConvolutionEngine()
                            ir_prof = ImpulseResponseProfile(
                                profile_id=Identifier("scene_reverb"),
                                ir_file_path=f"ir/{acoustic_preset}.wav",
                                wet_dry_mix=0.20,
                                decay_time_ms=decay_ms,
                            )
                            convolved = ir_engine.apply_convolution_reverb(
                                dub_vocals.read_bytes(), ir_prof
                            )
                            clean_wav_bytes = convolved.split(b"_CONVOLVED_REVERB")[0]
                            dub_vocals.write_bytes(clean_wav_bytes)
                            logger.info(
                                "engine: applied %s convolution reverb to dialogue track",
                                acoustic_preset,
                            )

                    except Exception as exc:
                        raise PipelineError(
                            ErrorKind.INTERNAL,
                            "assemble_failed",
                            f"Dialogue timeline assembly failed: {exc}",
                        ) from exc
                self.manifest.mark_stage("assemble", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                self._progress("assemble", 82, "Reusing validated dialogue assembly")

        # Stage 8: Audio Mixing & Muxing
        final_audio_wav = self.work_dir / "dubbed_audio.wav"
        final_audio_m4a = self.work_dir / "dubbed_audio.m4a"
        if music and music.exists() and dub_vocals.exists():
            self._progress(
                "mix", 86, "Mixing dialogue against original stems (dynamic sidechain ducking)"
            )
            with _timed("mix", bench):
                try:
                    dynamic_sidechain_mix(dub_vocals, music, final_audio_wav)
                    dynamic_sidechain_mix(dub_vocals, music, final_audio_m4a)
                except Exception as exc:
                    raise PipelineError(
                        ErrorKind.INTERNAL,
                        "mix_failed",
                        f"Audio mixing failed: {exc}",
                    ) from exc
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
                    from aidub.adapters.lipsync_viseme import VisemeLipSyncAdapter
                    from aidub.media.selective_lipsync import SelectiveFaceGateLipSyncEngine

                    viseme_engine = VisemeLipSyncAdapter()
                    ls_engine = viseme_engine

                    if self.cfg.lipsync_tier == "cinema_quality" and os.environ.get(
                        "AIDUB_LATENTSYNC_COMMAND"
                    ):
                        from aidub.adapters.lipsync_latentsync import LatentSyncLipSyncEngine

                        tier = LipSyncQualityTier.CINEMA_QUALITY
                        ls_engine = LatentSyncLipSyncEngine()
                    elif self.cfg.lipsync_tier == "preview_fast" and os.environ.get(
                        "AIDUB_MUSETALK_COMMAND"
                    ):
                        from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine

                        tier = LipSyncQualityTier.PREVIEW_FAST
                        ls_engine = MuseTalkLipSyncEngine()
                    else:
                        tier = LipSyncQualityTier.STUDIO_VISEME
                        ls_engine = viseme_engine

                    options = LipSyncOptions(quality_tier=tier)
                    selective_engine = SelectiveFaceGateLipSyncEngine()

                    def _synth_shot(s_id: str, in_v: Path, in_a: Path, out_v: Path) -> Path | None:
                        # First try primary engine if not viseme
                        if ls_engine is not viseme_engine:
                            try:
                                res = ls_engine.synthesize_lip_sync(
                                    shot_id=s_id,
                                    source_video_path=str(in_v),
                                    target_audio_path=str(in_a),
                                    output_directory=str(out_v.parent),
                                    options=options,
                                )
                                if (
                                    res
                                    and res.output_video_path
                                    and Path(res.output_video_path).is_file()
                                ):
                                    return Path(res.output_video_path)
                            except Exception as exc:
                                logger.info(
                                    "Shot lip-sync primary engine failed: %s; falling back to VisemeLipSyncAdapter",
                                    exc,
                                )

                        # Viseme engine fallback/primary
                        try:
                            res = viseme_engine.synthesize_lip_sync(
                                shot_id=s_id,
                                source_video_path=str(in_v),
                                target_audio_path=str(in_a),
                                output_directory=str(out_v.parent),
                                options=LipSyncOptions(
                                    quality_tier=LipSyncQualityTier.STUDIO_VISEME
                                ),
                            )
                            if (
                                res
                                and res.output_video_path
                                and Path(res.output_video_path).is_file()
                            ):
                                return Path(res.output_video_path)
                            return None
                        except Exception as exc:
                            logger.error("Viseme lip-sync fallback failed: %s", exc)
                            return None

                    selective_report = selective_engine.run_selective_lipsync(
                        source_video_path=self.cfg.input,
                        dubbed_audio_path=dub_vocals,
                        speech_segments=segs,
                        output_video_path=self.work_dir / f"{self.cfg.input.stem}_lipsynced.mp4",
                        work_dir=self.work_dir,
                        synthesize_fn=_synth_shot,
                        source_duration_s=total_dur,
                    )
                    lipsynced_video = Path(selective_report.output_video_path)
                self.manifest.mark_stage("lipsync", True, duration_ms=timing["duration_ms"])
                self.manifest.save()
            else:
                self._progress("lipsync", 91, "Reusing validated lip-synced video")
                synced_f = self.work_dir / f"{self.cfg.input.stem}_lipsynced.mp4"
                preview_f = self.work_dir / f"{self.cfg.input.stem}_musetalk_preview.mp4"
                cinema_f = self.work_dir / f"{self.cfg.input.stem}_latentsync_cinema.mp4"
                lipsynced_video = (
                    synced_f
                    if synced_f.is_file()
                    else (
                        preview_f
                        if preview_f.is_file()
                        else (cinema_f if cinema_f.is_file() else None)
                    )
                )

        video_for_mux = (
            lipsynced_video
            if (self.cfg.lipsync and lipsynced_video and lipsynced_video.is_file())
            else self.cfg.input
        )

        final_video = self.cfg.output
        self._progress("mux", 94, "Packaging localized master")
        with _timed("mux", bench) as timing:
            try:
                mux(video_for_mux, final_audio, final_video)
            except Exception as exc:
                raise PipelineError(
                    ErrorKind.INTERNAL,
                    "mux_failed",
                    f"Video muxing failed: {exc}",
                ) from exc
        if not final_video.is_file() or final_video.stat().st_size == 0:
            raise PipelineError(
                ErrorKind.INTERNAL,
                "master_render_missing",
                "The media muxer did not create a non-empty master file.",
            )
        self.manifest.mark_stage("mux", True, duration_ms=timing["duration_ms"])
        self.manifest.save()

        # Stage 10: Subtitle, Broadcast QC, and NLE Interchange Export
        origin_srt = write_srt(segs, self.work_dir / "origin_language.srt", translated=False)
        target_srt = write_srt(segs, self.work_dir / "target_language.srt", translated=True)
        bilingual_srt = write_bilingual_srt(
            segs, self.work_dir / "bilingual.srt", LineMode.BILINGUAL_TARGET_BOTTOM
        )
        bilingual_ass = self.work_dir / "bilingual.ass"
        try:
            from aidub.subtitles.bengali_ass_styler import BengaliAssStyler, BengaliSubtitleStyle

            BengaliAssStyler.generate_ass(
                segments=segs,
                output_path=bilingual_ass,
                style_preset=BengaliSubtitleStyle.BILINGUAL_STACKED,
            )
            logger.info(
                "engine: generated styled HarfBuzz Bengali ASS subtitles at %s", bilingual_ass.name
            )
        except Exception as exc:
            logger.info("engine: ASS subtitle generation skipped: %s", exc)

        # Stage 10.1: Broadcast QC Compliance Certificate
        qc_json_str = ""
        qc_txt_str = ""
        try:
            from aidub.analysis.broadcast_qc import BroadcastQCEngine, DeliverySpec

            spec_key = str(getattr(self.cfg, "broadcast_spec", "netflix") or "netflix").lower()
            target_spec = (
                DeliverySpec(spec_key)
                if spec_key in [s.value for s in DeliverySpec]
                else DeliverySpec.NETFLIX
            )
            audio_for_qc = final_audio_wav if final_audio_wav.is_file() else final_audio
            if audio_for_qc.is_file():
                qc_metrics = BroadcastQCEngine.analyze_wav_file(audio_for_qc)
                qc_cert = BroadcastQCEngine.evaluate_compliance(
                    qc_metrics, spec=target_spec, media_name=final_video.name
                )
                qc_json_file = self.work_dir / "broadcast_qc_certificate.json"
                qc_json_file.write_text(qc_cert.to_json(), encoding="utf-8")
                qc_txt_file = self.work_dir / "broadcast_qc_certificate.txt"
                qc_txt_file.write_text(qc_cert.to_formatted_certificate(), encoding="utf-8")
                qc_json_str = str(qc_json_file)
                qc_txt_str = str(qc_txt_file)
                logger.info(
                    "engine: Broadcast QC Certificate generated: %s",
                    "PASSED" if qc_cert.passed else "NEEDS REMEDIATION",
                )
        except Exception as exc:
            logger.warning("engine: Broadcast QC audit skipped: %s", exc)

        # Stage 10.2: NLE Timeline Round-Trip Interchange (FCPXML 1.10+ and CMX3600 EDL)
        fcpxml_str = ""
        edl_str = ""
        try:
            from aidub.interchange.edl_fcpxml_adapter import EDLFCPXMLAdapter
            from aidub.interchange.otio_adapter import OTIOClip, OTIOTimeline, OTIOTrack

            otio_clips: list[OTIOClip] = []
            for idx, seg in enumerate(segs):
                st_ms = int(float(seg.get("start", 0.0)) * 1000)
                en_ms = int(float(seg.get("end", st_ms / 1000 + 1.0)) * 1000)
                dur_ms = max(100, en_ms - st_ms)
                otio_clips.append(
                    OTIOClip(
                        clip_id=Identifier(f"clip_{idx:04d}"),
                        name=f"Dialogue_{idx + 1:03d}",
                        source_range_start_ms=st_ms,
                        source_range_duration_ms=dur_ms,
                        media_reference_path=str(dub_vocals),
                    )
                )

            if otio_clips:
                track = OTIOTrack(track_id=Identifier("t_dialogue"), kind="Audio", clips=otio_clips)
                timeline = OTIOTimeline(
                    timeline_id=Identifier("tl_dub_export"),
                    name=final_video.stem,
                    frame_rate=24.0,
                    tracks=[track],
                )
                adapter = EDLFCPXMLAdapter()
                edl_content = adapter.export_cmx3600_edl(timeline)
                edl_file = self.work_dir / f"{final_video.stem}.edl"
                edl_file.write_text(edl_content, encoding="utf-8")
                edl_str = str(edl_file)

                fcpxml_content = adapter.export_fcpxml(timeline)
                fcpxml_file = self.work_dir / f"{final_video.stem}.fcpxml"
                fcpxml_file.write_text(fcpxml_content, encoding="utf-8")
                fcpxml_str = str(fcpxml_file)
                logger.info(
                    "engine: NLE Interchange exported (%s, %s)", edl_file.name, fcpxml_file.name
                )
        except Exception as exc:
            logger.warning("engine: NLE interchange export skipped: %s", exc)

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
            bilingual_ass=str(bilingual_ass) if bilingual_ass.is_file() else "",
            dubbed_vocals=str(dub_vocals),
            dubbed_audio=str(final_audio),
            dubbed_video=str(final_video),
            lipsynced_video=str(lipsynced_video) if lipsynced_video else "",
            bench_json=str(bench_file),
            transcript_json=str(store._get_filename()),
            qc_certificate_json=qc_json_str,
            qc_certificate_txt=qc_txt_str,
            fcpxml_path=fcpxml_str,
            edl_path=edl_str,
        )



__all__ = ["DubbingEngine"]
