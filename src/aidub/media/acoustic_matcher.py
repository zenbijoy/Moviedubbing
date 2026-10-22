"""
Acoustic scene matching, RT60 reverberation estimation, and room impulse presets.

Features:
  - AcousticSceneProfile: Background noise floor (dBFS), RT60 decay time (sec), wet/dry mix.
  - Room Presets: STUDIO_CLEAN, LIVING_ROOM, LARGE_HALL, STREET_EXTERIOR, VEHICLE, TELEPHONE_RADIO.
  - RIR Convolution: Generates FFmpeg acoustic impulse response convolution filter strings (aecho/afir).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class RoomPreset(StrEnum):
    STUDIO_CLEAN = "studio_clean"
    LIVING_ROOM = "living_room"
    LARGE_HALL = "large_hall"
    STREET_EXTERIOR = "street_exterior"
    VEHICLE = "vehicle"
    TELEPHONE_RADIO = "telephone_radio"


class AcousticSceneProfile(ContractModel):
    """Estimated acoustic parameters of a scene source audio track."""

    scene_id: Identifier
    noise_floor_dbfs: float = Field(default=-60.0, ge=-90.0, le=0.0)
    rt60_seconds: float = Field(default=0.2, ge=0.05, le=5.0)
    direct_to_reverberant_ratio_db: float = Field(default=12.0, ge=-12.0, le=36.0)
    preset: RoomPreset = RoomPreset.STUDIO_CLEAN


# ── Room Preset Definitions ───────────────────────────────────────────────────

_ROOM_PRESETS: dict[RoomPreset, dict[str, Any]] = {
    RoomPreset.STUDIO_CLEAN: {
        "noise_floor_dbfs": -70.0,
        "rt60_seconds": 0.15,
        "direct_to_reverberant_ratio_db": 24.0,
        "echo_delay_ms": 10,
        "echo_decay": 0.05,
    },
    RoomPreset.LIVING_ROOM: {
        "noise_floor_dbfs": -55.0,
        "rt60_seconds": 0.40,
        "direct_to_reverberant_ratio_db": 14.0,
        "echo_delay_ms": 30,
        "echo_decay": 0.20,
    },
    RoomPreset.LARGE_HALL: {
        "noise_floor_dbfs": -50.0,
        "rt60_seconds": 1.80,
        "direct_to_reverberant_ratio_db": 4.0,
        "echo_delay_ms": 80,
        "echo_decay": 0.45,
    },
    RoomPreset.STREET_EXTERIOR: {
        "noise_floor_dbfs": -40.0,
        "rt60_seconds": 0.25,
        "direct_to_reverberant_ratio_db": 10.0,
        "echo_delay_ms": 40,
        "echo_decay": 0.15,
    },
    RoomPreset.VEHICLE: {
        "noise_floor_dbfs": -35.0,
        "rt60_seconds": 0.20,
        "direct_to_reverberant_ratio_db": 8.0,
        "echo_delay_ms": 20,
        "echo_decay": 0.30,
    },
    RoomPreset.TELEPHONE_RADIO: {
        "noise_floor_dbfs": -45.0,
        "rt60_seconds": 0.10,
        "direct_to_reverberant_ratio_db": 30.0,
        "echo_delay_ms": 5,
        "echo_decay": 0.01,
    },
}


class AcousticMatcher:
    """
    Estimates acoustic scene parameters and applies room preset impulse responses.
    """

    @staticmethod
    def profile_from_preset(scene_id: str, preset: RoomPreset) -> AcousticSceneProfile:
        """Create an AcousticSceneProfile configured for a room preset."""
        data = _ROOM_PRESETS[preset]
        return AcousticSceneProfile(
            scene_id=Identifier(scene_id),
            noise_floor_dbfs=data["noise_floor_dbfs"],
            rt60_seconds=data["rt60_seconds"],
            direct_to_reverberant_ratio_db=data["direct_to_reverberant_ratio_db"],
            preset=preset,
        )

    @staticmethod
    def to_ffmpeg_reverb_filter(profile: AcousticSceneProfile) -> str:
        """
        Build an FFmpeg audio filter string (aecho/highpass/lowpass) matching the room acoustics.
        """
        data = _ROOM_PRESETS.get(profile.preset, _ROOM_PRESETS[RoomPreset.STUDIO_CLEAN])
        delay = data["echo_delay_ms"]
        decay = data["echo_decay"]

        filters: list[str] = []

        if profile.preset == RoomPreset.TELEPHONE_RADIO:
            # Bandpass 300Hz - 3400Hz for telephone effect
            filters.append("highpass=f=300,lowpass=f=3400")
        elif profile.preset == RoomPreset.LARGE_HALL:
            # Multi-tap echo for hall reverberation
            filters.append(f"aecho=0.8:0.88:{delay}|{delay * 2}:{decay}|{decay * 0.5}")
        elif decay > 0.05:
            filters.append(f"aecho=0.8:0.88:{delay}:{decay}")

        return ",".join(filters) if filters else "anull"


__all__ = [
    "AcousticMatcher",
    "AcousticSceneProfile",
    "RoomPreset",
]
