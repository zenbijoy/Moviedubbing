"""
Advanced multitrack timeline customizations: clip grouping, color tagging, track presets.

Features:
  - Clip Color Labels (Dialogue, Music, Effects, Foley, Ambience, Subtitle, Custom)
  - Clip Grouping: Group multiple clips across tracks so they move/trim in sync
  - Track Configuration Presets (Dialogue Only, M&E Only, Subtitles Only, Full Dub Mix)
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.ui.timeline.model import TimelineClip, TimelineTrack, TrackId

logger = logging.getLogger(__name__)


class ClipColorLabel(StrEnum):
    DIALOGUE = "#10B981"  # Emerald
    MUSIC = "#F59E0B"  # Amber
    EFFECTS = "#EC4899"  # Pink
    FOLEY = "#8B5CF6"  # Purple
    AMBIENCE = "#14B8A6"  # Teal
    SUBTITLE = "#06B6D4"  # Cyan
    CUSTOM = "#6366F1"  # Indigo


class ClipGroup(ContractModel):
    """A collection of timeline clip IDs grouped to move/trim synchronously."""

    group_id: Identifier
    name: str = Field(default="", max_length=128)
    clip_ids: list[str] = Field(default_factory=list)


class TrackMuteSoloPreset(ContractModel):
    """Saved track mute/solo configuration state."""

    name: str = Field(min_length=1, max_length=128)
    muted_tracks: set[TrackId] = Field(default_factory=set)
    soloed_tracks: set[TrackId] = Field(default_factory=set)


PRESET_PROFILES: dict[str, TrackMuteSoloPreset] = {
    "dialogue_only": TrackMuteSoloPreset(
        name="Dialogue Only",
        soloed_tracks={TrackId.A1, TrackId.A2},
    ),
    "me_only": TrackMuteSoloPreset(
        name="M&E Only (Music & Effects)",
        soloed_tracks={TrackId.A3, TrackId.A4, TrackId.A5},
    ),
    "subtitles_only": TrackMuteSoloPreset(
        name="Subtitles Only",
        soloed_tracks={TrackId.S1, TrackId.S2},
    ),
}


class TimelineCustomizationEngine:
    """
    Manages clip groups, color tagging, and track mute/solo preset profiles.
    """

    def __init__(self) -> None:
        self._groups: dict[str, ClipGroup] = {}
        self._presets: dict[str, TrackMuteSoloPreset] = dict(PRESET_PROFILES)

    def create_group(self, name: str, clip_ids: list[str]) -> ClipGroup:
        """Group multiple clip IDs together."""
        group = ClipGroup(
            group_id=Identifier(f"grp_{len(self._groups) + 1:03d}"),
            name=name,
            clip_ids=clip_ids,
        )
        self._groups[group.group_id] = group
        logger.info(
            "timeline_customization: created clip group %s (%d clips)",
            group.group_id,
            len(clip_ids),
        )
        return group

    def get_group_for_clip(self, clip_id: str) -> ClipGroup | None:
        """Return clip group containing clip_id, if grouped."""
        for grp in self._groups.values():
            if clip_id in grp.clip_ids:
                return grp
        return None

    def apply_color_label(self, clip: TimelineClip, label: ClipColorLabel) -> TimelineClip:
        """Apply a color tag label to a timeline clip."""
        return clip.model_copy(update={"color_hex": label.value})

    def apply_track_preset(
        self, tracks: list[TimelineTrack], preset_key: str
    ) -> list[TimelineTrack]:
        """
        Apply a saved mute/solo preset to a list of timeline tracks.
        """
        preset = self._presets.get(preset_key)
        if preset is None:
            raise KeyError(f"track preset {preset_key!r} not found")

        updated_tracks: list[TimelineTrack] = []
        for track in tracks:
            muted = track.track_id in preset.muted_tracks
            solo = track.track_id in preset.soloed_tracks
            updated_tracks.append(track.model_copy(update={"muted": muted, "solo": solo}))

        logger.info("timeline_customization: applied preset %s", preset.name)
        return updated_tracks


__all__ = [
    "PRESET_PROFILES",
    "ClipColorLabel",
    "ClipGroup",
    "TimelineCustomizationEngine",
    "TrackMuteSoloPreset",
]
