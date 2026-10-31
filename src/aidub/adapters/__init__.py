"""Engine adapters for AI models, media runtimes, and external providers."""

from .asr_whisper import FasterWhisperAdapter, FasterWhisperOptions
from .diarization_pyannote import (
    DiarizedSpeakerSegment,
    PyannoteDiarizationAdapter,
    PyannoteDiarizationOptions,
    SpeakerDiarizationResult,
    cluster_speaker_embeddings,
)
from .separation_demucs import (
    DemucsSeparationAdapter,
    DemucsSeparationOptions,
    SeparatedStem,
    SourceSeparationResult,
    StemKind,
)
from .voice import (
    ChatterboxAdapter,
    ChatterboxVoiceEngine,
    EdgeTTSAdapter,
    EdgeTTSVoiceEngine,
)

__all__ = [
    "ChatterboxAdapter",
    "ChatterboxVoiceEngine",
    "DemucsSeparationAdapter",
    "DemucsSeparationOptions",
    "DiarizedSpeakerSegment",
    "EdgeTTSAdapter",
    "EdgeTTSVoiceEngine",
    "FasterWhisperAdapter",
    "FasterWhisperOptions",
    "PyannoteDiarizationAdapter",
    "PyannoteDiarizationOptions",
    "SeparatedStem",
    "SourceSeparationResult",
    "SpeakerDiarizationResult",
    "StemKind",
    "cluster_speaker_embeddings",
]
