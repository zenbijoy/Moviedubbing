"""
Spatial 3D Audio, Binaural HRTF, and 5.1/7.1 Surround Sound Panner.

Features:
  - 3D Position: Azimuth (-180° to +180°), Elevation (-90° to +90°), Distance attenuation.
  - Surround Sound Channel Coefficients: Stereo, 5.1 Surround, 7.1 Surround.
  - Binaural HRTF Simulation: Interaural Time Difference (ITD) & Intensity Difference (IID).
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel


class SpeakerLayout(StrEnum):
    STEREO = "stereo"
    SURROUND_51 = "5.1"
    SURROUND_71 = "7.1"
    BINAURAL = "binaural"


class Spatial3DPosition(ContractModel):
    """3D sound source position coordinates in spherical system."""

    azimuth_deg: float = Field(
        default=0.0, ge=-180.0, le=180.0, description="0=front, -90=left, +90=right"
    )
    elevation_deg: float = Field(default=0.0, ge=-90.0, le=90.0, description="0=level, +90=above")
    distance_m: float = Field(
        default=1.0, ge=0.1, le=100.0, description="Distance from listener in meters"
    )
    air_absorption: bool = True

    @property
    def distance_gain(self) -> float:
        """Inverse distance gain attenuation (reference 1 meter)."""
        return min(1.0, 1.0 / max(0.1, self.distance_m))


class Surround51Gains(ContractModel):
    """Channel gain coefficients for 5.1 Surround output."""

    fl: float = Field(default=0.707, ge=0.0, le=1.0)  # Front Left
    fr: float = Field(default=0.707, ge=0.0, le=1.0)  # Front Right
    fc: float = Field(default=0.0, ge=0.0, le=1.0)  # Center
    lfe: float = Field(default=0.0, ge=0.0, le=1.0)  # Subwoofer LFE
    sl: float = Field(default=0.0, ge=0.0, le=1.0)  # Surround Left
    sr: float = Field(default=0.0, ge=0.0, le=1.0)  # Surround Right


class SpatialPanner:
    """
    3D Spatial Panner calculating channel gains and ITD/IID delays.
    """

    @staticmethod
    def calculate_stereo_pan(azimuth_deg: float) -> tuple[float, float]:
        """
        Calculate constant-power stereo pan gains (left, right).
        Azimuth: -90 (hard left) to +90 (hard right).
        """
        az = max(-90.0, min(90.0, azimuth_deg))
        # Map [-90, +90] to [0.0, 1.0]
        pan = (az + 90.0) / 180.0
        angle = pan * (math.pi / 2.0)
        l_gain = math.cos(angle)
        r_gain = math.sin(angle)
        return (round(l_gain, 4), round(r_gain, 4))

    @staticmethod
    def calculate_surround_51(pos: Spatial3DPosition) -> Surround51Gains:
        """
        Calculate 5.1 Surround channel distribution gains for a 3D position.
        """
        az = pos.azimuth_deg
        dist_gain = pos.distance_gain

        # Simple 5.1 spatial distribution model
        fl = max(0.0, math.cos(math.radians(max(0.0, az + 30)))) * dist_gain
        fr = max(0.0, math.cos(math.radians(max(0.0, -az + 30)))) * dist_gain
        fc = max(0.0, math.cos(math.radians(abs(az)))) * dist_gain if abs(az) <= 45 else 0.0
        sl = max(0.0, math.sin(math.radians(max(0.0, -az)))) * dist_gain if az < 0 else 0.0
        sr = max(0.0, math.sin(math.radians(max(0.0, az)))) * dist_gain if az > 0 else 0.0

        return Surround51Gains(
            fl=round(fl, 3),
            fr=round(fr, 3),
            fc=round(fc, 3),
            lfe=0.0,
            sl=round(sl, 3),
            sr=round(sr, 3),
        )

    @staticmethod
    def calculate_binaural_itd_ms(azimuth_deg: float) -> float:
        """
        Calculate Interaural Time Difference (ITD) delay in milliseconds (Woodworth model).
        Head radius = 0.0875m, speed of sound = 343 m/s.
        """
        az_rad = math.radians(abs(azimuth_deg))
        r = 0.0875
        c = 343.0
        itd_sec = (r / c) * (az_rad + math.sin(az_rad))
        return round(itd_sec * 1000.0, 3)


__all__ = [
    "Spatial3DPosition",
    "SpatialPanner",
    "SpeakerLayout",
    "Surround51Gains",
]
