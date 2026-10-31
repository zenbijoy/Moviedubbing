"""Voice engine adapters and speaker reference extraction."""

from aidub.adapters.voice.chatterbox_adapter import (
    ChatterboxAdapter,
    ChatterboxVoiceEngine,
)
from aidub.adapters.voice.edge_tts_adapter import (
    BENGALI_VOICES,
    DEFAULT_BENGALI_VOICE,
    EdgeTTSAdapter,
    EdgeTTSVoiceEngine,
)
from aidub.adapters.voice.reference_extractor import pick_reference

__all__ = [
    "BENGALI_VOICES",
    "ChatterboxAdapter",
    "ChatterboxVoiceEngine",
    "DEFAULT_BENGALI_VOICE",
    "EdgeTTSAdapter",
    "EdgeTTSVoiceEngine",
    "pick_reference",
]

