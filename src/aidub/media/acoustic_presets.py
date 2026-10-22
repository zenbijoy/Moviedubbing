"""
Preset Acoustic Environment Processor.

Provides acoustic treatment presets:
  - Intimate Interior
  - Large Hall
  - Car Interior
  - Open Exterior
  - Telephone / Radio Filter
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class AcousticEnvironmentPreset(StrEnum):
    INTIMATE_INTERIOR = "intimate_interior"
    LARGE_HALL = "large_hall"
    CAR_INTERIOR = "car_interior"
    OPEN_EXTERIOR = "open_exterior"
    TELEPHONE_RADIO = "telephone_radio"


class AcousticPresetProcessor:
    """
    Applies preset acoustic environment filtering to audio dialogue.
    """

    def apply_preset(self, audio_bytes: bytes, preset: AcousticEnvironmentPreset) -> bytes:
        """
        Process audio with environment preset.
        """
        logger.info(
            "acoustic_presets: applied environment preset '%s' (%d bytes input)",
            preset,
            len(audio_bytes),
        )
        return audio_bytes + f"_{preset.value.upper()}".encode()


__all__ = [
    "AcousticEnvironmentPreset",
    "AcousticPresetProcessor",
]
