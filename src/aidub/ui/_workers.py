"""UI worker classes (QThread-based)."""

from __future__ import annotations

from ._workers_common import *

from ._workers_common import _QT

if _QT:
    class VideoFrameWorker(QThread):
        """Decode one real source frame with bundled FFmpeg off the UI thread."""

        frame_decoded = Signal(bytes, float, int)
        frame_failed = Signal(str, float, int)

        def __init__(
            self,
            media_path: str | Path,
            time_sec: float,
            request_id: int,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.media_path = Path(media_path)
            self.time_sec = max(0.0, float(time_sec))
            self.request_id = request_id
            self._process_lock = threading.Lock()
            self._process: subprocess.Popen[bytes] | None = None

        def cancel(self) -> None:
            """Stop an in-flight decoder before its owner window is destroyed."""

            self.requestInterruption()
            with self._process_lock:
                process = self._process
            if process is not None and process.poll() is None:
                process.kill()

        def run(self) -> None:
            try:
                if self.isInterruptionRequested():
                    return
                from aidub.media.ffmpeg_ops import _ffmpeg_exe

                cmd = [
                    _ffmpeg_exe(),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-ss",
                    f"{self.time_sec:.3f}",
                    "-i",
                    str(self.media_path),
                    "-map",
                    "0:v:0",
                    "-frames:v",
                    "1",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "png",
                    "pipe:1",
                ]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with self._process_lock:
                    self._process = process
                    cancelled = self.isInterruptionRequested()
                if cancelled:
                    process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=45)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    stdout, stderr = process.communicate()
                    raise RuntimeError("FFmpeg frame decoding timed out") from exc
                finally:
                    with self._process_lock:
                        self._process = None
                if self.isInterruptionRequested():
                    return
                if process.returncode != 0 or not stdout:
                    message = stderr.decode("utf-8", errors="replace")[-1_000:]
                    raise RuntimeError(message or "FFmpeg did not return a video frame")
                self.frame_decoded.emit(stdout, self.time_sec, self.request_id)
            except Exception as exc:
                self.frame_failed.emit(str(exc), self.time_sec, self.request_id)

    class DubbingEngineWorker(QThread):
        """Worker thread for executing DubbingEngine end-to-end processing."""

        progress_updated = Signal(str, int, str)  # pipeline stage, percentage, message
        dubbing_completed = Signal(dict)  # output metadata
        dubbing_failed = Signal(str)  # error message
        dubbing_cancelled = Signal()

        def __init__(
            self,
            input_path: str | Path,
            target_lang: str,
            quality_profile: str,
            parent: Any = None,
            *,
            output_path: str | Path | None = None,
            voice_name: str | None = None,
            voice_engine: str = "gemini_tts",
            tts_engine: str = "edge_tts",
            chatterbox_url: str | None = None,
            character_voices: dict[str, str] | None = None,
            lipsync: bool = True,
            lipsync_tier: str = "studio_viseme",
        ) -> None:
            super().__init__(parent)
            self.input_path = Path(input_path)
            self.target_lang = target_lang
            self.quality_profile = quality_profile
            self.output_path = Path(output_path) if output_path else None
            self.voice_name = voice_name
            self.voice_engine = voice_engine
            self.tts_engine = tts_engine
            self.chatterbox_url = chatterbox_url
            self.character_voices = dict(character_voices or {})
            self.lipsync = lipsync
            self.lipsync_tier = lipsync_tier

        def _available_output_path(self) -> Path:
            language = re.sub(r"[^A-Za-z0-9_-]", "_", self.target_lang).strip("_-") or "target"
            base = self.output_path or self.input_path.parent / (
                f"{self.input_path.stem}_dubbed_{language}.mp4"
            )
            if not base.exists():
                return base
            for revision in range(2, 10_000):
                candidate = base.with_name(f"{base.stem}_{revision:02d}{base.suffix}")
                if not candidate.exists():
                    return candidate
            raise RuntimeError(f"No unused output filename is available for {base}")

        def run(self) -> None:
            try:
                from aidub.pipeline.config import PipelineConfig
                from aidub.pipeline.engine import DubbingEngine, PipelineCancelled

                out_path = self._available_output_path()
                import os

                is_fast = self.quality_profile == "fast"
                effective_lipsync = False if is_fast else self.lipsync
                if effective_lipsync:
                    if self.lipsync_tier == "cinema_quality" and not os.environ.get(
                        "AIDUB_LATENTSYNC_COMMAND"
                    ):
                        self.progress_updated.emit(
                            "lipsync_notice",
                            2,
                            "Notice: AIDUB_LATENTSYNC_COMMAND not configured; using Studio Viseme Lip-Sync.",
                        )
                        self.lipsync_tier = "studio_viseme"
                    elif self.lipsync_tier == "preview_fast" and not os.environ.get(
                        "AIDUB_MUSETALK_COMMAND"
                    ):
                        self.progress_updated.emit(
                            "lipsync_notice",
                            2,
                            "Notice: AIDUB_MUSETALK_COMMAND not configured; using Studio Viseme Lip-Sync.",
                        )
                        self.lipsync_tier = "studio_viseme"

                cfg = PipelineConfig(
                    input=self.input_path,
                    output=out_path,
                    tgt_lang=self.target_lang,
                    keep_music=not is_fast,
                    diarize=not is_fast,
                    fast=is_fast,
                    lipsync=effective_lipsync,
                    lipsync_tier=self.lipsync_tier,
                    voice_name=self.voice_name,
                    voice_engine=self.voice_engine,
                    tts_engine=self.tts_engine,
                    chatterbox_url=self.chatterbox_url,
                    character_voices=self.character_voices,
                )

                engine = DubbingEngine(
                    cfg,
                    progress_callback=lambda stage, percent, message: self.progress_updated.emit(
                        stage, percent, message
                    ),
                    cancel_requested=self.isInterruptionRequested,
                )
                try:
                    outputs = engine.run()
                except PipelineCancelled:
                    self.dubbing_cancelled.emit()
                    return

                result = {
                    "output_file": str(getattr(outputs, "dubbed_video", out_path)),
                    "audio_file": str(getattr(outputs, "dubbed_audio", "")),
                    "srt_file": str(getattr(outputs, "bilingual_srt", "")),
                    "target_srt_file": str(getattr(outputs, "target_srt", "")),
                    "transcript_file": str(getattr(outputs, "transcript_json", "")),
                    "lipsynced_video": str(getattr(outputs, "lipsynced_video", "")),
                    "work_dir": str(engine.work_dir),
                }
                self.dubbing_completed.emit(result)
            except Exception as exc:
                logger.exception("DubbingEngineWorker failed: %s", exc)
                self.dubbing_failed.emit(str(exc))

        def cancel(self) -> None:
            """Request cancellation at the engine's next safe stage boundary."""

            self.requestInterruption()

    class CharacterDetectionWorker(QThread):
        """Worker thread for running speaker diarization and movie character recognition."""

        progress_updated = Signal(int, str)  # percentage, status message
        characters_detected = Signal(list)  # list of MovieCharacter objects
        diarization_completed = Signal(list, int, dict)  # turns, n_speakers, ref_windows
        detection_failed = Signal(str)
        detection_cancelled = Signal()

        def __init__(
            self,
            audio_path: str | Path | None = None,
            parent: Any = None,
            *,
            media_path: str | Path | None = None,
            subtitle_cues: list[Any] | None = None,
            target_language: str = "bn",
            work_dir: Path | str | None = None,
        ) -> None:
            super().__init__(parent)
            path = media_path or audio_path
            self.media_path = Path(path) if path else None
            self.subtitle_cues = list(subtitle_cues or [])
            self.target_language = target_language
            self.work_dir = Path(work_dir) if work_dir else None

        def cancel(self) -> None:
            """Request cancellation of character detection."""
            self.requestInterruption()

        def run(self) -> None:
            try:
                from aidub.ai.voice.character_cloning_engine import CharacterDetectionEngine

                if self.isInterruptionRequested():
                    self.detection_cancelled.emit()
                    return

                self.progress_updated.emit(10, "Scanning subtitle cues for charactersâ€¦")
                engine = CharacterDetectionEngine()
                cue_chars = (
                    engine.detect_from_subtitle_cues(
                        self.subtitle_cues, target_language=self.target_language
                    )
                    if self.subtitle_cues
                    else []
                )

                turns: list[tuple[float, float, int]] = []
                ref_windows: dict[int, tuple[float, float]] = {}

                if self.media_path and self.media_path.is_file():
                    if self.isInterruptionRequested():
                        self.detection_cancelled.emit()
                        return
                    self.progress_updated.emit(
                        35, "Running speaker diarization & acoustic analysisâ€¦"
                    )
                    from aidub.adapters.diarization_pyannote import PyannoteDiarizationAdapter

                    adapter = PyannoteDiarizationAdapter()
                    turns, _n_speakers, ref_windows = adapter.turns(str(self.media_path))

                    self.progress_updated.emit(70, "Profiling detected character voicesâ€¦")
                    audio_chars, _ = engine.detect_from_media(
                        self.media_path,
                        target_language=self.target_language,
                        work_dir=self.work_dir,
                    )
                else:
                    audio_chars = []

                if self.isInterruptionRequested():
                    self.detection_cancelled.emit()
                    return

                # Merge cue characters and audio characters
                char_map: dict[str, Any] = {}
                for c in audio_chars:
                    char_map[c.canonical_name] = c
                for c in cue_chars:
                    char_map[c.canonical_name] = c

                all_characters = list(char_map.values())
                if not all_characters:
                    all_characters = engine.detect_movie_characters(
                        [{"speaker": "SPEAKER_00"}, {"speaker": "SPEAKER_01"}],
                        target_language=self.target_language,
                    )

                self.progress_updated.emit(
                    100, f"Identified {len(all_characters)} movie characters"
                )
                self.characters_detected.emit(all_characters)
                self.diarization_completed.emit(turns, max(1, len(all_characters)), ref_windows)
            except Exception as exc:
                logger.exception("CharacterDetectionWorker failed: %s", exc)
                self.detection_failed.emit(str(exc))

    class AudioAnalysisWorker(QThread):
        """Measure audio features in a worker thread without loading full media in RAM."""

        progress_updated = Signal(float, float)  # analyzed seconds, requested seconds
        analysis_completed = Signal(dict)
        analysis_failed = Signal(str)
        analysis_cancelled = Signal()

        def __init__(
            self,
            media_path: str | Path,
            start_seconds: float = 0.0,
            duration_seconds: float | None = None,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.media_path = Path(media_path)
            self.start_seconds = float(start_seconds)
            self.duration_seconds = duration_seconds

        def cancel(self) -> None:
            """Request cancellation; FFmpeg is stopped at the next streamed chunk."""

            self.requestInterruption()

        def run(self) -> None:
            try:
                from aidub.analysis.audio_analyzer import (
                    AudioAnalysisCancelled,
                    analyze_audio_file,
                )

                report = analyze_audio_file(
                    self.media_path,
                    start_seconds=self.start_seconds,
                    duration_seconds=self.duration_seconds,
                    progress_callback=lambda elapsed, total: self.progress_updated.emit(
                        elapsed, total
                    ),
                    cancel_requested=self.isInterruptionRequested,
                )
                self.analysis_completed.emit(report.to_dict())
            except AudioAnalysisCancelled:
                self.analysis_cancelled.emit()
            except Exception as exc:
                logger.exception("AudioAnalysisWorker failed: %s", exc)
                self.analysis_failed.emit(str(exc))

    class SpeechTranscriptionWorker(QThread):
        """Transcribe a selected media interval with the project's local Whisper adapter."""

        stage_updated = Signal(str)
        transcription_completed = Signal(str)
        transcription_failed = Signal(str)

        def __init__(
            self,
            media_path: str | Path,
            start_seconds: float,
            duration_seconds: float,
            model_size: str = "large-v3",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.media_path = Path(media_path)
            self.start_seconds = float(start_seconds)
            self.duration_seconds = float(duration_seconds)
            self.model_size = model_size

        def run(self) -> None:
            try:
                from tempfile import TemporaryDirectory

                from aidub.adapters.asr_whisper import FasterWhisperAdapter, FasterWhisperOptions
                from aidub.media.ffmpeg_ops import trim

                if self.duration_seconds <= 0 or self.duration_seconds > 300:
                    raise ValueError("Whisper transcription is limited to a 5-minute selection")
                self.stage_updated.emit("Extracting the selected audio interval...")
                with TemporaryDirectory(prefix="aidub_transcription_") as temporary_dir:
                    segment_path = Path(temporary_dir) / "selected_audio.wav"
                    trim(
                        self.media_path,
                        segment_path,
                        self.start_seconds,
                        self.start_seconds + self.duration_seconds,
                        sr=16_000,
                    )
                    self.stage_updated.emit(
                        f"Loading local Faster-Whisper {self.model_size} and transcribing..."
                    )
                    adapter = FasterWhisperAdapter(
                        FasterWhisperOptions(model_size=self.model_size, word_timestamps=False)
                    )
                    segments = adapter.transcribe_file(segment_path)

                transcript = "\n".join(
                    f"[{self.start_seconds + float(item['start']):.2f}s - "
                    f"{self.start_seconds + float(item['end']):.2f}s] {item['text']}"
                    for item in segments
                    if str(item.get("text", "")).strip()
                )
                self.transcription_completed.emit(transcript)
            except Exception as exc:
                logger.exception("SpeechTranscriptionWorker failed: %s", exc)
                self.transcription_failed.emit(str(exc))

    class EmotionAnalysisWorker(QThread):
        """Run the existing acoustic and contextual EmotionEngine on a short interval."""

        stage_updated = Signal(str)
        emotion_completed = Signal(dict)
        emotion_failed = Signal(str)

        def __init__(
            self,
            media_path: str | Path,
            start_seconds: float,
            duration_seconds: float,
            dialogue_text: str = "",
            character_name: str = "Character",
            scene_context: str = "",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.media_path = Path(media_path)
            self.start_seconds = float(start_seconds)
            self.duration_seconds = float(duration_seconds)
            self.dialogue_text = dialogue_text
            self.character_name = character_name
            self.scene_context = scene_context

        def run(self) -> None:
            try:
                from tempfile import TemporaryDirectory

                from aidub.ai.voice.emotion_engine import (
                    AcousticEmotionDetector,
                    EmotionEngine,
                )
                from aidub.media.ffmpeg_ops import trim

                if self.duration_seconds <= 0 or self.duration_seconds > 60:
                    raise ValueError("Emotion analysis is limited to a 60-second selection")
                self.stage_updated.emit("Extracting the selected dialogue interval...")
                with TemporaryDirectory(prefix="aidub_emotion_") as temporary_dir:
                    segment_path = Path(temporary_dir) / "selected_audio.wav"
                    trim(
                        self.media_path,
                        segment_path,
                        self.start_seconds,
                        self.start_seconds + self.duration_seconds,
                        sr=16_000,
                    )
                    if self.dialogue_text.strip():
                        self.stage_updated.emit(
                            "Combining acoustic features with the supplied dialogue context..."
                        )
                        result = EmotionEngine().detect_emotion(
                            utterance_id="audio_segment_analysis",
                            dialogue_text=self.dialogue_text,
                            audio_path=segment_path,
                            character_name=self.character_name or "Character",
                            scene_context=self.scene_context,
                        )
                        payload = result.model_dump(mode="json")
                    else:
                        self.stage_updated.emit("Measuring acoustic prosody locally...")
                        observation = AcousticEmotionDetector().detect_emotion(segment_path)
                        payload = {
                            "primary_emotion": observation.dominant_category,
                            "confidence": observation.confidence,
                            "valence": observation.valence,
                            "arousal": observation.arousal,
                            "dominance": observation.dominance,
                            "intensity": observation.intensity,
                            "secondary_emotions": observation.secondary_emotions,
                            "detection_source": "acoustic_prosody_heuristic",
                            "synthesis_parameters": EmotionEngine().map_synthesis_parameters(
                                observation.dominant_category,
                                intensity=observation.intensity,
                                arousal=observation.arousal,
                            ),
                        }
                self.emotion_completed.emit(payload)
            except Exception as exc:
                logger.exception("EmotionAnalysisWorker failed: %s", exc)
                self.emotion_failed.emit(str(exc))

    class AIAssistantWorker(QThread):
        """Worker thread for sending LLM prompts to LlmProviderRouter."""

        response_received = Signal(str)
        request_failed = Signal(str)

        def __init__(self, prompt: str, system_context: str = "", parent: Any = None) -> None:
            super().__init__(parent)
            self.prompt = prompt
            self.system_context = system_context

        def run(self) -> None:
            try:
                from aidub.contracts.base import Identifier
                from aidub.providers.factory import build_router_from_config
                from aidub.providers.router import LlmRequest

                router = build_router_from_config()
                full_prompt = (
                    f"{self.system_context}\n{self.prompt}" if self.system_context else self.prompt
                )
                try:
                    response = router.complete(
                        LlmRequest(
                            request_id=Identifier("studio-assistant-request"),
                            system_prompt=self.system_context,
                            user_prompt=full_prompt,
                            json_mode=False,
                            temperature=0.25,
                        )
                    )
                    result = response.content
                except Exception as exc:
                    logger.warning("AI assistant provider request failed: %s", exc)
                    self.request_failed.emit(str(exc))
                    return
                self.response_received.emit(result)
            except Exception as exc:
                logger.exception("AIAssistantWorker failed: %s", exc)
                self.request_failed.emit(str(exc))

    class TTSPreviewWorker(QThread):
        """Worker thread for synthesizing TTS preview audio."""

        synthesis_completed = Signal(str)  # output wav path
        synthesis_failed = Signal(str)

        def __init__(
            self,
            text: str,
            voice_name: str | None = None,
            output_file: str | Path = "",
            parent: Any = None,
            reference_audio: str | Path = "",
            chatterbox_url: str | None = None,
            target_lang: str = "bn",
        ) -> None:
            super().__init__(parent)
            self.text = text
            self.target_lang = target_lang
            self.voice_name = voice_name
            self.output_file = Path(output_file) if output_file else Path("preview_voice.wav")
            self.reference_audio = Path(reference_audio) if reference_audio else None
            self.chatterbox_url = chatterbox_url

        def run(self) -> None:
            try:
                import os
                from aidub.adapters.voice.edge_tts_adapter import (
                    EdgeTTSAdapter,
                    default_voice_for_language,
                    get_voice_for_language,
                )

                eff_voice = self.voice_name
                if not eff_voice:
                    try:
                        eff_voice = get_voice_for_language(self.target_lang)
                    except Exception:
                        eff_voice = default_voice_for_language("bn")

                url = (
                    self.chatterbox_url
                    or os.getenv("KAGGLE_CHATTERBOX_URL")
                    or os.getenv("CHATTERBOX_API_URL")
                )
                output = None
                if url:
                    try:
                        from aidub.adapters.voice.chatterbox_adapter import ChatterboxAdapter

                        adapter = ChatterboxAdapter(server_url=url)
                        output = adapter.synthesize_to_file(
                            self.text,
                            self.output_file,
                            reference_audio_path=self.reference_audio,
                            language=self.target_lang,
                        )
                    except Exception as exc:
                        logger.warning("TTSPreviewWorker: Chatterbox failed (%s); falling back to EdgeTTS", exc)
                        output = None

                if output is None:
                    adapter = EdgeTTSAdapter(voice_name=eff_voice)
                    output = adapter.synthesize_to_file(self.text, self.output_file)
                self.synthesis_completed.emit(str(output))
            except Exception as exc:
                logger.exception("TTSPreviewWorker failed: %s", exc)
                self.synthesis_failed.emit(str(exc))

    class TimingFitWorker(QThread):
        """Fit a selected audio take to a measured dialogue slot in the background."""

        fit_completed = Signal(str, float)
        fit_failed = Signal(str)

        def __init__(
            self,
            input_audio: str | Path,
            target_duration: float,
            output_audio: str | Path,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.input_audio = Path(input_audio)
            self.target_duration = target_duration
            self.output_audio = Path(output_audio)

        def run(self) -> None:
            try:
                from aidub.media.assemble import fit_to_slot
                from aidub.media.ffmpeg_ops import duration

                fit_to_slot(self.input_audio, self.target_duration, self.output_audio)
                fitted_duration = duration(self.output_audio)
                if fitted_duration > self.target_duration * 1.02:
                    raise RuntimeError(
                        f"Take remains {fitted_duration:.2f}s after fitting into a "
                        f"{self.target_duration:.2f}s slot; human timing review is required."
                    )
                self.fit_completed.emit(str(self.output_audio), fitted_duration)
            except Exception as exc:
                logger.exception("TimingFitWorker failed: %s", exc)
                self.fit_failed.emit(str(exc))

    class LipSyncRenderWorker(QThread):
        """Worker thread for running LatentSync / MuseTalk lip-sync render."""

        lipsync_progress = Signal(int, str)
        lipsync_completed = Signal(str)
        lipsync_failed = Signal(str)

        def __init__(
            self,
            video_path: str | Path,
            audio_path: str | Path,
            output_file: str | Path,
            model_name: str = "latentsync",
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.video_path = Path(video_path)
            self.audio_path = Path(audio_path)
            self.output_file = Path(output_file)
            self.model_name = model_name

        def run(self) -> None:
            try:
                self.lipsync_progress.emit(10, f"Initializing {self.model_name} model...")
                if "latentsync" in self.model_name.lower():
                    from aidub.adapters.lipsync_latentsync import LatentSyncLipSyncEngine
                    from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine

                    adapter: LatentSyncLipSyncEngine | MuseTalkLipSyncEngine = (
                        LatentSyncLipSyncEngine()
                    )
                else:
                    from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine

                    adapter = MuseTalkLipSyncEngine()
                self.lipsync_progress.emit(
                    40, "Conditioning facial landmarks & warping video frames..."
                )
                result = adapter.synthesize_lip_sync(
                    shot_id=self.output_file.stem,
                    source_video_path=str(self.video_path),
                    target_audio_path=str(self.audio_path),
                    output_directory=str(self.output_file.parent),
                )
                produced_path = Path(result.output_video_path)
                if self.output_file != produced_path and produced_path.is_file():
                    import shutil

                    shutil.copy2(produced_path, self.output_file)
                    final_path = str(self.output_file)
                else:
                    final_path = str(produced_path)
                self.lipsync_progress.emit(100, "Lip-sync rendering completed!")
                self.lipsync_completed.emit(final_path)
            except Exception as exc:
                logger.exception("LipSyncRenderWorker failed: %s", exc)
                self.lipsync_failed.emit(str(exc))

    class RenderExportWorker(QThread):
        """Worker thread for running FFmpeg render pipeline and distribution export."""

        render_progress = Signal(int, str)  # percent, stage message
        render_completed = Signal(str)  # final export path
        render_failed = Signal(str)

        def __init__(
            self,
            input_video: str | Path,
            audio_track: str | Path,
            output_file: str | Path,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.input_video = Path(input_video)
            self.audio_track = Path(audio_track)
            self.output_file = Path(output_file)

        def run(self) -> None:
            try:
                from aidub.media.ffmpeg_ops import mux

                self.render_progress.emit(20, "Extracting video streams...")
                self.render_progress.emit(50, "Muxing dubbed audio tracks...")
                mux(self.input_video, self.audio_track, self.output_file)
                self.render_progress.emit(100, "Export completed successfully!")
                self.render_completed.emit(str(self.output_file))
            except Exception as exc:
                logger.exception("RenderExportWorker failed: %s", exc)
                self.render_failed.emit(str(exc))

    class UtteranceRetakeWorker(QThread):
        """Worker thread for running targeted single-utterance ADR retake and ripple edit."""

        retake_progress = Signal(int, str)  # percent, status message
        retake_completed = Signal(object)  # RetakeResult
        retake_failed = Signal(str)  # error message

        def __init__(
            self,
            work_dir: Path | str,
            utterance_index: int,
            new_target_text: str,
            *,
            target_language: str = "bn",
            voice_name: str | None = None,
            rate_percent: int = 0,
            pitch_hz: int = 0,
            optimize_isometric: bool = False,
            acoustic_preset: str | None = None,
            ripple_edit: bool = False,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.work_dir = Path(work_dir)
            self.utterance_index = utterance_index
            self.new_target_text = new_target_text
            self.target_language = target_language
            self.voice_name = voice_name
            self.rate_percent = rate_percent
            self.pitch_hz = pitch_hz
            self.optimize_isometric = optimize_isometric
            self.acoustic_preset = acoustic_preset
            self.ripple_edit = ripple_edit

        def run(self) -> None:
            try:
                from aidub.pipeline.retake import UtteranceRetakeService

                service = UtteranceRetakeService(
                    self.work_dir, target_language=self.target_language
                )

                def _cb(pct: int, msg: str) -> None:
                    self.retake_progress.emit(pct, msg)

                result = service.retake_utterance(
                    utterance_index=self.utterance_index,
                    new_target_text=self.new_target_text,
                    voice_name=self.voice_name,
                    rate_percent=self.rate_percent,
                    pitch_hz=self.pitch_hz,
                    optimize_isometric=self.optimize_isometric,
                    acoustic_preset=self.acoustic_preset,
                    ripple_edit=self.ripple_edit,
                    progress_cb=_cb,
                )
                self.retake_completed.emit(result)
            except Exception as exc:
                logger.exception("UtteranceRetakeWorker failed: %s", exc)
                self.retake_failed.emit(str(exc))

    class ModularExtractionWorker(QThread):
        """Worker thread for extracting dialogue audio from source video."""

        progress_updated = Signal(int, str)
        extraction_completed = Signal(str, float)
        extraction_failed = Signal(str)
        extraction_cancelled = Signal()

        def __init__(
            self,
            video_path: str | Path,
            output_audio_path: str | Path,
            sample_rate: int = 16_000,
            parent: Any = None,
            service: Any = None,
        ) -> None:
            super().__init__(parent)
            self.video_path = Path(video_path)
            self.output_audio_path = Path(output_audio_path)
            self.sample_rate = sample_rate
            self.service = service

        def run(self) -> None:
            try:
                from aidub.application.modular_pipeline import (
                    ModularDubbingPipelineService,
                    PipelineCancelledError,
                )

                service = self.service or ModularDubbingPipelineService()
                dur_s, out_p = service.extract_dialogue_audio(
                    self.video_path,
                    self.output_audio_path,
                    sample_rate=self.sample_rate,
                    cancel_check=self.isInterruptionRequested,
                    progress_cb=self.progress_updated.emit,
                )
                self.extraction_completed.emit(str(out_p), dur_s)
            except PipelineCancelledError:
                self.extraction_cancelled.emit()
            except Exception as exc:
                logger.exception("ModularExtractionWorker failed: %s", exc)
                self.extraction_failed.emit(str(exc))

        def cancel(self) -> None:
            self.requestInterruption()

    class ModularTranscriptionWorker(QThread):
        """Worker thread for transcribing speech audio into structured cues."""

        progress_updated = Signal(int, str)
        transcription_completed = Signal(list)
        transcription_failed = Signal(str)
        transcription_cancelled = Signal()

        def __init__(
            self,
            audio_path: str | Path,
            language: str | None = None,
            model_size: str = "base",
            parent: Any = None,
            service: Any = None,
        ) -> None:
            super().__init__(parent)
            self.audio_path = Path(audio_path)
            self.language = language
            self.model_size = model_size
            self.service = service

        def run(self) -> None:
            try:
                from aidub.application.modular_pipeline import (
                    ModularDubbingPipelineService,
                    PipelineCancelledError,
                )

                service = self.service or ModularDubbingPipelineService()
                cues = service.transcribe_audio(
                    self.audio_path,
                    language=self.language,
                    model_size=self.model_size,
                    cancel_check=self.isInterruptionRequested,
                    progress_cb=self.progress_updated.emit,
                )
                self.transcription_completed.emit(cues)
            except PipelineCancelledError:
                self.transcription_cancelled.emit()
            except Exception as exc:
                logger.exception("ModularTranscriptionWorker failed: %s", exc)
                self.transcription_failed.emit(str(exc))

        def cancel(self) -> None:
            self.requestInterruption()

    class ModularTranslationWorker(QThread):
        """Worker thread for translating dialogue cues into target language."""

        progress_updated = Signal(int, str)
        translation_completed = Signal(list)
        translation_failed = Signal(str)
        translation_cancelled = Signal()

        def __init__(
            self,
            cues: list[Any],
            source_lang: str,
            target_lang: str,
            parent: Any = None,
            service: Any = None,
        ) -> None:
            super().__init__(parent)
            self.cues = cues
            self.source_lang = source_lang
            self.target_lang = target_lang
            self.service = service

        def run(self) -> None:
            try:
                from aidub.application.modular_pipeline import (
                    ModularDubbingPipelineService,
                    PipelineCancelledError,
                )
                from aidub.providers.factory import build_router_from_config

                router = None
                try:
                    router = build_router_from_config()
                except Exception:
                    router = None

                service = self.service or ModularDubbingPipelineService()
                translated = service.translate_cues(
                    self.cues,
                    self.source_lang,
                    self.target_lang,
                    router=router,
                    cancel_check=self.isInterruptionRequested,
                    progress_cb=self.progress_updated.emit,
                )
                self.translation_completed.emit(translated)
            except PipelineCancelledError:
                self.translation_cancelled.emit()
            except Exception as exc:
                logger.exception("ModularTranslationWorker failed: %s", exc)
                self.translation_failed.emit(str(exc))

        def cancel(self) -> None:
            self.requestInterruption()

    class ModularBatchSynthesisWorker(QThread):
        """Worker thread for synthesizing all translated cues into placed voice takes."""

        progress_updated = Signal(int, str)
        synthesis_completed = Signal(list)
        synthesis_failed = Signal(str)
        synthesis_cancelled = Signal()

        def __init__(
            self,
            cues: list[Any],
            target_lang: str,
            output_dir: str | Path,
            voice_name: str | None = None,
            parent: Any = None,
            service: Any = None,
        ) -> None:
            super().__init__(parent)
            self.cues = cues
            self.target_lang = target_lang
            self.output_dir = Path(output_dir)
            self.voice_name = voice_name
            self.service = service

        def run(self) -> None:
            try:
                from aidub.application.modular_pipeline import (
                    ModularDubbingPipelineService,
                    PipelineCancelledError,
                )

                service = self.service or ModularDubbingPipelineService()
                takes = service.synthesize_cues(
                    self.cues,
                    self.target_lang,
                    self.output_dir,
                    voice_name=self.voice_name,
                    cancel_check=self.isInterruptionRequested,
                    progress_cb=self.progress_updated.emit,
                )
                self.synthesis_completed.emit(takes)
            except PipelineCancelledError:
                self.synthesis_cancelled.emit()
            except Exception as exc:
                logger.exception("ModularBatchSynthesisWorker failed: %s", exc)
                self.synthesis_failed.emit(str(exc))

        def cancel(self) -> None:
            self.requestInterruption()

    class ModularRenderWorker(QThread):
        """Worker thread for rendering and muxing the final master video."""

        progress_updated = Signal(int, str)
        render_completed = Signal(str)
        render_failed = Signal(str)
        render_cancelled = Signal()

        def __init__(
            self,
            video_path: str | Path,
            audio_path: str | Path,
            output_video_path: str | Path,
            parent: Any = None,
            service: Any = None,
        ) -> None:
            super().__init__(parent)
            self.video_path = Path(video_path)
            self.audio_path = Path(audio_path)
            self.output_video_path = Path(output_video_path)
            self.service = service

        def run(self) -> None:
            try:
                from aidub.application.modular_pipeline import (
                    ModularDubbingPipelineService,
                    PipelineCancelledError,
                )

                service = self.service or ModularDubbingPipelineService()
                out_v = service.render_master_timeline(
                    self.video_path,
                    self.audio_path,
                    self.output_video_path,
                    cancel_check=self.isInterruptionRequested,
                    progress_cb=self.progress_updated.emit,
                )
                self.render_completed.emit(str(out_v))
            except PipelineCancelledError:
                self.render_cancelled.emit()
            except Exception as exc:
                logger.exception("ModularRenderWorker failed: %s", exc)
                self.render_failed.emit(str(exc))

        def cancel(self) -> None:
            self.requestInterruption()



__all__ = [
    "VideoFrameWorker",
    "DubbingEngineWorker",
    "CharacterDetectionWorker",
    "AudioAnalysisWorker",
    "SpeechTranscriptionWorker",
    "EmotionAnalysisWorker",
    "AIAssistantWorker",
    "TTSPreviewWorker",
    "TimingFitWorker",
    "LipSyncRenderWorker",
    "RenderExportWorker",
    "UtteranceRetakeWorker",
    "ModularExtractionWorker",
    "ModularTranscriptionWorker",
    "ModularTranslationWorker",
    "ModularBatchSynthesisWorker",
    "ModularRenderWorker",
]
