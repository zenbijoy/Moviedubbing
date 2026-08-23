"""
Qt Worker Threads for executing asynchronous backend pipeline operations.
Integrates PySide6 UI screens with DubbingEngine, Pyannote Diarization,
LLM Provider Router, and FFmpeg Render Exporter without blocking the main event loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    from PySide6.QtCore import QThread, Signal
    _QT = True
except ImportError:
    _QT = False

logger = logging.getLogger(__name__)

if _QT:

    class DubbingEngineWorker(QThread):
        """Worker thread for executing DubbingEngine end-to-end processing."""

        progress_updated = Signal(str, int)  # stage_name, percentage (0-100)
        dubbing_completed = Signal(dict)    # output metadata
        dubbing_failed = Signal(str)        # error message
        dubbing_cancelled = Signal()

        def __init__(self, input_path: str | Path, target_lang: str, quality_profile: str, parent: Any = None) -> None:
            super().__init__(parent)
            self.input_path = Path(input_path)
            self.target_lang = target_lang
            self.quality_profile = quality_profile

        def run(self) -> None:
            try:
                from aidub.pipeline.config import PipelineConfig
                from aidub.pipeline.engine import DubbingEngine, PipelineCancelled

                out_path = self.input_path.parent / f"{self.input_path.stem}_dubbed_{self.target_lang}.mp4"
                cfg = PipelineConfig(
                    input=self.input_path,
                    output=out_path,
                    tgt_lang=self.target_lang,
                    keep_music=self.quality_profile != "fast",
                    diarize=self.quality_profile != "fast",
                )

                engine = DubbingEngine(
                    cfg,
                    progress_callback=lambda _stage, percent, message: self.progress_updated.emit(
                        message, percent
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
        """Worker thread for running speaker diarization and reference audio mining."""

        diarization_completed = Signal(list, int, dict)  # turns, n_speakers, ref_windows
        detection_failed = Signal(str)

        def __init__(self, audio_path: str | Path, parent: Any = None) -> None:
            super().__init__(parent)
            self.audio_path = Path(audio_path)

        def run(self) -> None:
            try:
                from aidub.adapters.diarization_pyannote import PyannoteDiarizationAdapter
                adapter = PyannoteDiarizationAdapter()
                turns, n_speakers, ref_windows = adapter.turns(str(self.audio_path))
                self.diarization_completed.emit(turns, n_speakers, ref_windows)
            except Exception as exc:
                logger.exception("CharacterDetectionWorker failed: %s", exc)
                self.detection_failed.emit(str(exc))

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
                full_prompt = f"{self.system_context}\n{self.prompt}" if self.system_context else self.prompt
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

        def __init__(self, text: str, voice_name: str = "bn-IN-TanishaaNeural", output_file: str | Path = "", parent: Any = None) -> None:
            super().__init__(parent)
            self.text = text
            self.voice_name = voice_name
            self.output_file = Path(output_file) if output_file else Path("preview_voice.mp3")

        def run(self) -> None:
            try:
                from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter
                adapter = EdgeTTSAdapter(voice_name=self.voice_name)
                output = adapter.synthesize_to_file(self.text, self.output_file)
                self.synthesis_completed.emit(str(output))
            except Exception as exc:
                logger.exception("TTSPreviewWorker failed: %s", exc)
                self.synthesis_failed.emit(str(exc))

    class LipSyncRenderWorker(QThread):
        """Worker thread for running LatentSync / MuseTalk lip-sync render."""

        lipsync_progress = Signal(int, str)
        lipsync_completed = Signal(str)
        lipsync_failed = Signal(str)

        def __init__(self, video_path: str | Path, audio_path: str | Path, output_file: str | Path, model_name: str = "latentsync", parent: Any = None) -> None:
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
                    adapter = LatentSyncLipSyncEngine()
                else:
                    from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine
                    adapter = MuseTalkLipSyncEngine()
                self.lipsync_progress.emit(40, "Conditioning facial landmarks & warping video frames...")
                result = adapter.synthesize_lip_sync(
                    shot_id=self.output_file.stem,
                    source_video_path=str(self.video_path),
                    target_audio_path=str(self.audio_path),
                    output_directory=str(self.output_file.parent),
                )
                self.lipsync_progress.emit(100, "Lip-sync rendering completed!")
                self.lipsync_completed.emit(result.output_video_path)
            except Exception as exc:
                logger.exception("LipSyncRenderWorker failed: %s", exc)
                self.lipsync_failed.emit(str(exc))

    class RenderExportWorker(QThread):
        """Worker thread for running FFmpeg render pipeline and distribution export."""

        render_progress = Signal(int, str)  # percent, stage message
        render_completed = Signal(str)      # final export path
        render_failed = Signal(str)

        def __init__(self, input_video: str | Path, audio_track: str | Path, output_file: str | Path, parent: Any = None) -> None:
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

__all__ = [
    "DubbingEngineWorker",
    "CharacterDetectionWorker",
    "AIAssistantWorker",
    "TTSPreviewWorker",
    "LipSyncRenderWorker",
    "RenderExportWorker",
]
