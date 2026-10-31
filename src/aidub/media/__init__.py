"""Safe media runtime adapters."""

from .commands import ProxySpec, ThumbnailSpec, WaveformSpec
from .derivatives import DerivativeGenerator, DerivativeResult, FFprobeDerivativeValidator
from .fingerprint import SourceFingerprint, fast_fingerprint, full_fingerprint
from .importer import MediaImportService
from .probe import (
    AudioStreamInfo,
    ContainerInfo,
    MediaProbe,
    MediaProbeError,
    SubtitleStreamInfo,
    VideoStreamInfo,
)
from .runtime import MediaRuntime, MediaRuntimeInfo, ensure_media_runtime_on_path
from .stems import StemSelectionPolicy, StemSelector, StudioStemSelection
from .thumbnail_extractor import ThumbnailExtractor, get_thumbnail_extractor
from .waveform_cache import DEFAULT_PEAKS_PER_SECOND, WaveformCache, get_waveform_cache

__all__ = [
    "AudioStreamInfo",
    "ContainerInfo",
    "DEFAULT_PEAKS_PER_SECOND",
    "DerivativeGenerator",
    "DerivativeResult",
    "FFprobeDerivativeValidator",
    "MediaImportService",
    "MediaProbe",
    "MediaProbeError",
    "MediaRuntime",
    "MediaRuntimeInfo",
    "ProxySpec",
    "SourceFingerprint",
    "StemSelectionPolicy",
    "StemSelector",
    "StudioStemSelection",
    "SubtitleStreamInfo",
    "ThumbnailExtractor",
    "ThumbnailSpec",
    "VideoStreamInfo",
    "WaveformCache",
    "WaveformSpec",
    "ensure_media_runtime_on_path",
    "fast_fingerprint",
    "full_fingerprint",
    "get_thumbnail_extractor",
    "get_waveform_cache",
]
