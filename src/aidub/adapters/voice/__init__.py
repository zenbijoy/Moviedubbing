"""Voice engine adapters and speaker reference extraction."""

from aidub.adapters.voice.chatterbox_adapter import (
    ChatterboxAdapter,
    ChatterboxVoiceEngine,
)
from aidub.adapters.voice.edge_tts_adapter import (
    BENGALI_VOICES,
    DEFAULT_BENGALI_VOICE,
    EDGE_STYLES,
    LANGUAGE_VOICES_BY_GENDER,
    EdgeTTSAdapter,
    EdgeTTSVoiceEngine,
    available_voices_for_language,
    default_voice_for_language,
    get_voice_for_language,
)
from aidub.adapters.voice.reference_extractor import pick_reference

__all__ = [
    "BENGALI_VOICES",
    "ChatterboxAdapter",
    "ChatterboxVoiceEngine",
    "DEFAULT_BENGALI_VOICE",
    "EDGE_STYLES",
    "EdgeTTSAdapter",
    "EdgeTTSVoiceEngine",
    "LANGUAGE_VOICES_BY_GENDER",
    "available_voices_for_language",
    "default_voice_for_language",
    "get_voice_for_language",
    "pick_reference",
]
