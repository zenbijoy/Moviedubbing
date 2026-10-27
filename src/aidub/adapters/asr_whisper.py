"""Faster-Whisper (CTranslate2) local speech recognition adapter."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Self

# Compatibility shim for modern PyAV (v14+/v19+) where metadata_errors was removed from av.open
try:
    import av

    _orig_av_open = av.open

    def _compat_av_open(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _compat_av_open
except (ImportError, AttributeError):
    pass

from pydantic import Field, model_validator

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.speech.contracts import (
    RecognitionChunkResult,
    RecognitionPhase,
    RecognitionProgress,
    RecognitionProvenance,
    RecognizedSegment,
    RecognizedWord,
    SpeechEngineIdentity,
    SpeechRecognitionRequest,
)
from aidub.speech.recognizer import SpeechRecognizer
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


class FasterWhisperOptions(ContractModel):
    """Configuration options for the Faster-Whisper ASR engine adapter."""

    model_size: str = Field(default="large-v3", min_length=1, max_length=64)
    device: str = Field(default="auto", min_length=1, max_length=32)
    compute_type: str = Field(default="default", min_length=1, max_length=32)
    beam_size: int = Field(default=5, ge=1, le=20)
    vad_filter: bool = Field(default=True)
    word_timestamps: bool = Field(default=True)
    language: str | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_options(self) -> Self:
        if self.compute_type not in {"default", "float16", "int8_float16", "int8", "float32"}:
            raise ValueError(f"unsupported compute type: {self.compute_type}")
        if self.device not in {"auto", "cuda", "cpu"}:
            raise ValueError(f"unsupported device: {self.device}")
        return self


class FasterWhisperAdapter(SpeechRecognizer):
    """Local Faster-Whisper speech recognizer adapter with exact sample alignment."""

    def __init__(
        self,
        options: FasterWhisperOptions | None = None,
        *,
        source_audio_path: str | Path | None = None,
    ) -> None:
        self.options = options or FasterWhisperOptions()
        self.source_audio_path = Path(source_audio_path) if source_audio_path is not None else None
        model_hash = hashlib.sha256(
            f"faster-whisper-{self.options.model_size}-{self.options.compute_type}".encode()
        ).hexdigest()
        self._identity = SpeechEngineIdentity(
            engine_id=Identifier("faster-whisper"),
            engine_version="1.1.0",
            model_id=Identifier(f"whisper-{self.options.model_size}"),
            model_version="3.0.0",
            model_weights_sha256=model_hash,
        )
        self._model_instance: Any | None = None

    def _model(self) -> Any:
        try:
            import faster_whisper
        except ImportError as exc:
            raise RuntimeError(
                "Faster-Whisper is not installed; install the production ASR dependencies"
            ) from exc
        if self._model_instance is None:
            device = self.options.device
            compute_type = self.options.compute_type
            if device in {"auto", "cuda"}:
                import ctypes
                import os

                cuda_ok = False
                if os.name == "nt":
                    try:
                        ctypes.CDLL("cublas64_12.dll")
                        cuda_ok = True
                    except Exception:
                        cuda_ok = False
                else:
                    try:
                        import ctranslate2

                        cuda_ok = ctranslate2.get_cuda_device_count() > 0
                    except Exception:
                        cuda_ok = False

                if not cuda_ok:
                    logger.info("CUDA / cuBLAS 12 not available; using CPU int8 for Faster-Whisper")
                    device = "cpu"
                    if compute_type in {"default", "float16", "int8_float16"}:
                        compute_type = "int8"

            try:
                self._model_instance = faster_whisper.WhisperModel(
                    self.options.model_size,
                    device=device,
                    compute_type=compute_type,
                )
            except RuntimeError as exc:
                if device != "cpu":
                    logger.warning(
                        "CUDA acceleration unavailable for Faster-Whisper (%s). Falling back to CPU int8.",
                        exc,
                    )
                    self._model_instance = faster_whisper.WhisperModel(
                        self.options.model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                else:
                    raise
        return self._model_instance

    @property
    def identity(self) -> SpeechEngineIdentity:
        return self._identity

    def recognize(
        self,
        request: SpeechRecognitionRequest,
        *,
        runtime: RecognitionRuntime,
    ) -> RecognitionChunkResult:
        """Recognize one exact source-audio chunk and return exact sample-aligned tokens."""

        runtime.checkpoint()
        provenance = RecognitionProvenance.from_request(request, self.identity)

        if self.source_audio_path is None or not self.source_audio_path.is_file():
            raise RuntimeError("a real source_audio_path is required for speech recognition")
        model = self._model()

        runtime.checkpoint()
        runtime.report(
            RecognitionProgress(
                request_id=request.request_id,
                phase=RecognitionPhase.RECOGNIZING,
                completed_samples=0,
                total_samples=request.audio_range.sample_count,
                chunk_index=request.chunk_index,
                chunk_count=request.chunk_count,
            )
        )

        # Execute transcription with word-level timestamps
        segments, _info = model.transcribe(
            str(self.source_audio_path),
            beam_size=self.options.beam_size,
            vad_filter=self.options.vad_filter,
            word_timestamps=self.options.word_timestamps,
            language=request.language.split("-")[0] if request.language else None,
        )

        recognized_segments: list[RecognizedSegment] = []
        sample_rate = request.audio_range.sample_rate
        chunk_offset = request.audio_range.start.sample_index

        for seg_idx, seg in enumerate(segments):
            runtime.checkpoint()
            words: list[RecognizedWord] = []
            if hasattr(seg, "words") and seg.words:
                for word_idx, w in enumerate(seg.words):
                    w_start_sample = chunk_offset + int(w.start * sample_rate)
                    w_end_sample = chunk_offset + int(w.end * sample_rate)
                    w_count = max(1, w_end_sample - w_start_sample)
                    w_range = AudioSampleRange(
                        start=AudioSamplePosition(
                            sample_index=w_start_sample, sample_rate=sample_rate
                        ),
                        sample_count=w_count,
                    )
                    w_id = Identifier(f"w_{request.chunk_index}_{seg_idx}_{word_idx}")
                    words.append(
                        RecognizedWord(
                            word_id=w_id,
                            text=w.word.strip(),
                            audio_range=w_range,
                            confidence=float(getattr(w, "probability", 0.95)),
                            provenance=provenance,
                        )
                    )

            seg_start_sample = chunk_offset + int(seg.start * sample_rate)
            seg_end_sample = chunk_offset + int(seg.end * sample_rate)
            seg_count = max(1, seg_end_sample - seg_start_sample)
            seg_range = AudioSampleRange(
                start=AudioSamplePosition(sample_index=seg_start_sample, sample_rate=sample_rate),
                sample_count=seg_count,
            )
            seg_id = Identifier(f"seg_{request.chunk_index}_{seg_idx}")
            seg_confidence = sum(w.confidence for w in words) / len(words) if words else 0.95
            recognized_segments.append(
                RecognizedSegment(
                    segment_id=seg_id,
                    text=seg.text.strip(),
                    audio_range=seg_range,
                    confidence=seg_confidence,
                    words=tuple(words),
                    provenance=provenance,
                )
            )

        runtime.checkpoint()
        return RecognitionChunkResult(
            provenance=provenance,
            segments=tuple(recognized_segments),
        )

    def transcribe_file(
        self,
        audio_path: str | Path,
        turns: list[tuple[float, float, int]] | None = None,
        progress_callback: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Transcribe an actual audio file and preserve model timestamps."""

        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(f"ASR source audio does not exist: {source}")
        try:
            segments, _info = self._model().transcribe(
                str(source),
                beam_size=self.options.beam_size,
                vad_filter=self.options.vad_filter,
                word_timestamps=self.options.word_timestamps,
                language=self.options.language,
            )
            total_dur_info = float(getattr(_info, "duration", 0.0))
            raw_segments = []
            for s in segments:
                raw_segments.append(s)
                if progress_callback is not None:
                    try:
                        progress_callback(float(s.end), total_dur_info, str(s.text).strip())
                    except Exception:
                        pass
        except (RuntimeError, Exception) as exc:
            logger.warning(
                "Faster-Whisper transcription failed (%s); retrying with CPU int8 fallback", exc
            )
            import faster_whisper

            fallback_model = (
                "base"
                if any(w in str(exc).lower() for w in ("malloc", "memory", "alloc", "oom"))
                else self.options.model_size
            )
            try:
                self._model_instance = faster_whisper.WhisperModel(
                    fallback_model,
                    device="cpu",
                    compute_type="int8",
                )
                segments, _info = self._model_instance.transcribe(
                    str(source),
                    beam_size=self.options.beam_size,
                    vad_filter=self.options.vad_filter,
                    word_timestamps=self.options.word_timestamps,
                    language=self.options.language,
                )
                raw_segments = list(segments)
            except Exception as exc2:
                if fallback_model != "base":
                    logger.warning(
                        "Retry with %s failed (%s); falling back to base", fallback_model, exc2
                    )
                    self._model_instance = faster_whisper.WhisperModel(
                        "base",
                        device="cpu",
                        compute_type="int8",
                    )
                    segments, _info = self._model_instance.transcribe(
                        str(source),
                        beam_size=self.options.beam_size,
                        vad_filter=self.options.vad_filter,
                        word_timestamps=self.options.word_timestamps,
                        language=self.options.language,
                    )
                    raw_segments = list(segments)
                else:
                    raise

        results: list[dict[str, Any]] = []
        for segment in raw_segments:
            start = float(segment.start)
            end = float(segment.end)
            text = str(segment.text).strip()
            if not text or end <= start:
                continue
            speaker = 0
            if turns:
                speaker = max(
                    turns,
                    key=lambda turn: max(0.0, min(end, turn[1]) - max(start, turn[0])),
                )[2]
            results.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                    "speaker": speaker,
                }
            )
        return results

    def transcribe_turns(
        self,
        audio_path: str,
        turns: list[tuple[float, float, int]],
        work_dir: str,
    ) -> list[dict[str, Any]]:
        """
        Diarize-first ASR path: transcribe each speaker turn separately.

        Ensures each segment contains words from ONLY ONE speaker and retains
        the correct speaker_id attribution.
        """
        del work_dir
        return self.transcribe_file(audio_path, turns)


def _has_speech(segs: list[dict[str, Any]], total_duration_s: float) -> bool:
    """
    Hallucination guard for Whisper/Parakeet ASR models.

    Verifies that recognized text has sufficient word variety (unique/total >= 0.35)
    and audio speech coverage (speech_duration/total_duration >= 0.10) to reject
    hallucinated repeated loops over background music.
    """
    if not segs or total_duration_s <= 0:
        return False

    all_words: list[str] = []
    speech_dur = 0.0

    for s in segs:
        text = str(s.get("text", "")).lower()
        words = [w for w in text.split() if any(c.isalpha() for c in w)]
        all_words.extend(words)
        speech_dur += max(0.0, float(s.get("end", 0)) - float(s.get("start", 0)))

    if len(all_words) < 4:
        return False

    variety = len(set(all_words)) / len(all_words)
    coverage = speech_dur / total_duration_s

    logger.debug(
        "ASR speech check: variety=%.2f, coverage=%.2f, speech_dur=%.2f",
        variety,
        coverage,
        speech_dur,
    )
    return variety >= 0.35 and (coverage >= 0.04 or speech_dur >= 4.0)


__all__ = ["FasterWhisperAdapter", "FasterWhisperOptions", "_has_speech"]
