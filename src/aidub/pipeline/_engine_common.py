"""Common imports, constants, and helpers for the Dubbing engine modules."""

from __future__ import annotations


import json
import logging
import os
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
    duration,
    dynamic_sidechain_mix,
    extract_audio,
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



