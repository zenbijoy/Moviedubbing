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
from aidub.adapters.voice.edge_tts_adapter import (
    EdgeTTSAdapter,
    default_voice_for_language,
    get_voice_for_language,
)
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


def _estimate_pitch(audio: Any, sr: int) -> float:
    """
    Estimate fundamental frequency (pitch) dynamically across voiced frames
    using autocorrelation to distinguish male vs female speech characteristics.
    """
    import numpy as np

    if audio is None:
        return 0.0

    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)

    min_samples = int(sr * 0.05)
    if len(arr) < min_samples:
        return 0.0

    # Search for highest energy voiced window to avoid silent regions
    win_size = min(2048, max(512, len(arr) // 4))
    hop_size = win_size // 2

    best_frame: np.ndarray | None = None
    best_energy = 0.0

    for i in range(0, max(1, len(arr) - win_size), hop_size):
        sub = arr[i : i + win_size]
        energy = float(np.sum(sub**2))
        if energy > best_energy:
            best_energy = energy
            best_frame = sub

    if best_frame is None or best_energy < 1e-4:
        # Fallback to middle frame
        center = len(arr) // 2
        half_win = min(1024, max(256, len(arr) // 4))
        best_frame = arr[max(0, center - half_win) : min(len(arr), center + half_win)]

    if len(best_frame) < 512:
        return 0.0

    frame = best_frame - np.mean(best_frame)
    corr = np.correlate(frame, frame, mode="full")
    corr = corr[len(corr) // 2 :]

    # Vocal pitch range: 65 Hz (deep male) to 400 Hz (high female/child)
    min_lag = int(sr / 400)
    max_lag = int(sr / 65)
    if max_lag >= len(corr) or min_lag >= max_lag:
        return 0.0

    peak_lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
    if peak_lag == 0:
        return 0.0

    f0 = float(sr / peak_lag)
    if 60.0 <= f0 <= 400.0:
        return f0
    return 0.0


def _translate_to_target(text: str, target_lang: str = "bn") -> str:
    """Translate dialogue text to target language using Google GTX API with MyMemory fallback."""
    cleaned = text.strip()
    if not cleaned or cleaned == "…":
        return cleaned

    target_lang_clean = str(target_lang or "bn").strip()
    norm_lang = target_lang_clean.split("-")[0].split("_")[0].lower()

    try:
        import json
        import urllib.parse
        import urllib.request

        q = urllib.parse.quote(cleaned)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={norm_lang}&dt=t&q={q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        res = json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
        translated = "".join([part[0] for part in res[0] if part and part[0]])
        if translated.strip():
            return translated.strip()
    except Exception:
        pass

    try:
        from deep_translator import MyMemoryTranslator

        dialect_map = {
            "bn": "bn-BD",
            "en": "en-US",
            "es": "es-ES",
            "pt": "pt-BR",
            "zh": "zh-CN",
        }
        m_tgt = dialect_map.get(norm_lang, target_lang_clean)
        tr = MyMemoryTranslator(source="auto", target=m_tgt).translate(cleaned)
        if tr and tr.strip():
            return tr.strip()
    except Exception:
        pass

    return cleaned
