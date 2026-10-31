"""
Domain contracts for frame-accurate Viseme Timelines, Keyframes, and Geometric Blendshapes.

Compatible with Disney / MPEG-4 visual mouth phonetics and ITU-R BT.1359 audio-to-video synchronization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from aidub.media.lipsync_viseme_engine import (
    VISEME_GEOMETRIES,
    VisemeGeometry,
    VisemeGroup,
)


@dataclass
class LipSyncOffset:
    """Manual audio-to-video lead/lag offset adjustment."""

    offset_ms: float = 0.0
    reason: str = ""
    applied_at_s: float = 0.0


@dataclass
class VisemeKeyframe:
    """Represents a discrete viseme mouth pose over a time interval."""

    viseme: VisemeGroup
    start_s: float
    end_s: float
    label: str = ""
    geometry: VisemeGeometry | None = None
    confidence: float = 1.0
    is_manual_override: bool = False

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.viseme.value.upper()[:4]
        if self.geometry is None:
            self.geometry = VISEME_GEOMETRIES.get(
                self.viseme, VISEME_GEOMETRIES[VisemeGroup.SILENCE]
            )

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass
class VisemeTimeline:
    """Complete viseme performance timeline for an utterance or track."""

    utterance_id: str
    duration_s: float
    keyframes: list[VisemeKeyframe] = field(default_factory=list)
    lead_lag_offset_ms: float = 0.0
    shot_eligible_for_lipsync: bool = True
    quality_tier: str = "preview"  # "preview" (MuseTalk) or "cinema" (LatentSync)

    def add_keyframe(self, kf: VisemeKeyframe) -> None:
        """Appends a new viseme keyframe to the timeline."""
        self.keyframes.append(kf)

    def nudge_offset(self, delta_ms: float) -> float:
        """Nudges the audio/video lead-lag offset by delta_ms."""
        self.lead_lag_offset_ms += delta_ms
        return self.lead_lag_offset_ms

    def get_viseme_at(self, time_s: float) -> VisemeKeyframe | None:
        """Finds the active viseme keyframe at playhead position time_s (accounting for offset)."""
        offset_s = self.lead_lag_offset_ms / 1000.0
        adjusted_t = time_s - offset_s
        for kf in self.keyframes:
            if kf.start_s <= adjusted_t <= kf.end_s:
                return kf
        return None

    def get_active_viseme_at(self, time_s: float) -> VisemeKeyframe | None:
        """Finds the active viseme keyframe at playhead position time_s (accounting for offset)."""
        return self.get_viseme_at(time_s)

    def override_viseme_at(
        self, time_s: float, viseme: VisemeGroup
    ) -> VisemeKeyframe | None:
        """Manually overrides the viseme pose at time_s."""
        kf = self.get_viseme_at(time_s)
        if kf is not None:
            kf.viseme = viseme
            kf.label = viseme.value.upper()[:4]
            kf.geometry = VISEME_GEOMETRIES.get(
                viseme, VISEME_GEOMETRIES[VisemeGroup.SILENCE]
            )
            kf.is_manual_override = True
            return kf
        return None

    def evaluate_itu_compliance(self) -> tuple[bool, str, float]:
        """
        Evaluates ITU-R BT.1359 broadcast synchronization standard:
        - Audio leading video: up to +45 ms is acceptable
        - Audio lagging video: up to -125 ms is acceptable
        Returns: (is_compliant, status_string, offset_ms)
        """
        offset = self.lead_lag_offset_ms
        if -125.0 <= offset <= 45.0:
            return True, "Broadcast Compliant (ITU-R BT.1359)", offset
        elif offset > 45.0:
            return False, f"Audio Leads Video (+{offset:.1f}ms > +45ms threshold)", offset
        else:
            return False, f"Audio Lags Video ({offset:.1f}ms < -125ms threshold)", offset

    def to_mocap_dict(self) -> dict[str, Any]:
        """Exports timeline to standard 3D animation mocap JSON representation."""
        offset_s = self.lead_lag_offset_ms / 1000.0
        return {
            "utterance_id": self.utterance_id,
            "duration_s": round(self.duration_s, 4),
            "lead_lag_offset_ms": round(self.lead_lag_offset_ms, 2),
            "quality_tier": self.quality_tier,
            "keyframe_count": len(self.keyframes),
            "keyframes": [
                {
                    "viseme": kf.viseme.value,
                    "label": kf.label,
                    "start_s": round(kf.start_s + offset_s, 3),
                    "end_s": round(kf.end_s + offset_s, 3),
                    "is_manual_override": kf.is_manual_override,
                    "geometry": {
                        "openness": kf.geometry.openness,
                        "width": kf.geometry.width,
                        "lip_protrusion": kf.geometry.lip_protrusion,
                        "teeth_visible": kf.geometry.teeth_visible,
                    },
                }
                for kf in self.keyframes
            ],
        }


__all__ = [
    "LipSyncOffset",
    "VISEME_GEOMETRIES",
    "VisemeGeometry",
    "VisemeGroup",
    "VisemeKeyframe",
    "VisemeTimeline",
]
