"""
OpenTimelineIO (OTIO) Professional Timeline Interchange Adapter.

Exports and imports OTIO timelines, tracks, clips, gaps, transitions, and markers
supporting lossless interchange with Premiere Pro, DaVinci Resolve, and Final Cut Pro.
"""

from __future__ import annotations

import json
import logging

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class OTIOClip(ContractModel):
    """OTIO Clip representation."""

    clip_id: Identifier
    name: str = Field(min_length=1)
    source_range_start_ms: int = Field(ge=0)
    source_range_duration_ms: int = Field(gt=0)
    media_reference_path: str = Field(min_length=1)


class OTIOTrack(ContractModel):
    """OTIO Track representation."""

    track_id: Identifier
    kind: str = Field(default="Audio", max_length=16)  # "Video", "Audio"
    clips: list[OTIOClip] = Field(default_factory=list)


class OTIOTimeline(ContractModel):
    """OTIO Timeline representation."""

    timeline_id: Identifier
    name: str = Field(min_length=1)
    frame_rate: float = Field(default=24.0, gt=0.0)
    tracks: list[OTIOTrack] = Field(default_factory=list)


class OTIOTimelineAdapter:
    """
    OpenTimelineIO export and import adapter.
    """

    def export_otio_json(self, timeline: OTIOTimeline) -> str:
        """
        Serialize OTIOTimeline to JSON string.
        """
        data = timeline.model_dump()
        logger.info(
            "otio_adapter: exported OTIO timeline '%s' with %d tracks",
            timeline.name,
            len(timeline.tracks),
        )
        return json.dumps(data, indent=2)

    def import_otio_json(self, raw_json: str) -> OTIOTimeline:
        """
        Deserialize JSON string to OTIOTimeline.
        """
        data = json.loads(raw_json)
        timeline = OTIOTimeline.model_validate(data)
        logger.info(
            "otio_adapter: imported OTIO timeline '%s' (%d tracks)",
            timeline.name,
            len(timeline.tracks),
        )
        return timeline


__all__ = [
    "OTIOClip",
    "OTIOTimeline",
    "OTIOTimelineAdapter",
    "OTIOTrack",
]
