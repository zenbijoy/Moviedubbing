"""Timeline package."""

from .autoscroll import AutoScrollMode, TimelineScrollController
from .customization import (
    PRESET_PROFILES,
    ClipColorLabel,
    ClipGroup,
    TimelineCustomizationEngine,
    TrackMuteSoloPreset,
)
from .markers import (
    InOutRange,
    MarkerKind,
    TimelineMarker,
    TimelineMarkerManager,
)
from .model import (
    TRACK_KINDS,
    TimelineClip,
    TimelineLayoutEngine,
    TimelineTrack,
    TrackId,
    TrackKind,
    create_default_multitrack_timeline,
)
from .thumbnails import ThumbnailCacheManager, ThumbnailStripData, VideoThumbnailFrame
from .waveform import WaveformGenerator, WaveformPeakData

__all__ = [
    "PRESET_PROFILES",
    "TRACK_KINDS",
    "AutoScrollMode",
    "ClipColorLabel",
    "ClipGroup",
    "InOutRange",
    "MarkerKind",
    "ThumbnailCacheManager",
    "ThumbnailStripData",
    "TimelineClip",
    "TimelineCustomizationEngine",
    "TimelineLayoutEngine",
    "TimelineMarker",
    "TimelineMarkerManager",
    "TimelineScrollController",
    "TimelineTrack",
    "TrackId",
    "TrackKind",
    "TrackMuteSoloPreset",
    "VideoThumbnailFrame",
    "WaveformGenerator",
    "WaveformPeakData",
    "create_default_multitrack_timeline",
]
