"""
Frame-accurate playback clock, shuttle control, and dual-viewer display modes.

Provides:
  - PlaybackState: play/pause, speed (J/K/L shuttle multiplier), position in ms & frames
  - DualViewerMode: SOURCE, DUB, SPLIT_COMPARE, OVERLAY_COMPARE
  - FrameClock: frame-accurate PTS calculator based on RationalTime/rate
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel

logger = logging.getLogger(__name__)


class DualViewerMode(StrEnum):
    SOURCE = "source"  # Source Video Only
    DUB = "dub"  # Dubbed/Lipsynced Video Only
    SPLIT_COMPARE = "split_compare"  # Side-by-Side Split View
    OVERLAY_COMPARE = "overlay"  # Alpha Overlay Comparison


class PlaybackState(ContractModel):
    """Runtime state of the frame-accurate playback engine."""

    playing: bool = False
    shuttle_speed: float = Field(default=1.0, ge=-16.0, le=16.0)
    position_ms: int = Field(default=0, ge=0)
    fps: float = Field(default=24.0, gt=0.0)
    viewer_mode: DualViewerMode = DualViewerMode.SPLIT_COMPARE
    audio_master_clock: bool = True

    @property
    def current_frame(self) -> int:
        """Calculate current frame index from position_ms and fps."""
        return int((self.position_ms / 1000.0) * self.fps)

    def seek_frame(self, frame_index: int) -> int:
        """Seek to target frame index, returning new position_ms."""
        return max(0, int((frame_index / self.fps) * 1000.0))


class PlaybackController:
    """
    Frame-accurate playback engine controller.

    Manages J/K/L shuttle speed transitions, playhead seeking,
    and dual-viewer mode switches.
    """

    def __init__(self, fps: float = 24.0) -> None:
        self._state = PlaybackState(fps=fps)

    @property
    def state(self) -> PlaybackState:
        return self._state

    def play(self) -> None:
        self._state = self._state.model_copy(update={"playing": True, "shuttle_speed": 1.0})

    def pause(self) -> None:
        self._state = self._state.model_copy(update={"playing": False, "shuttle_speed": 0.0})

    def toggle_play_pause(self) -> None:
        if self._state.playing:
            self.pause()
        else:
            self.play()

    def shuttle_j(self) -> None:
        """J key: Reverse playback at 1x, 2x, 4x, 8x speed."""
        speed = self._state.shuttle_speed
        new_speed = -1.0 if speed >= 0 else max(-16.0, speed * 2.0)
        self._state = self._state.model_copy(update={"playing": True, "shuttle_speed": new_speed})

    def shuttle_k(self) -> None:
        """K key: Pause playback immediately."""
        self.pause()

    def shuttle_l(self) -> None:
        """L key: Forward playback at 1x, 2x, 4x, 8x speed."""
        speed = self._state.shuttle_speed
        new_speed = 1.0 if speed <= 0 else min(16.0, speed * 2.0)
        self._state = self._state.model_copy(update={"playing": True, "shuttle_speed": new_speed})

    def seek_ms(self, position_ms: int) -> None:
        self._state = self._state.model_copy(update={"position_ms": max(0, position_ms)})

    def set_viewer_mode(self, mode: DualViewerMode) -> None:
        self._state = self._state.model_copy(update={"viewer_mode": mode})


__all__ = [
    "DualViewerMode",
    "PlaybackController",
    "PlaybackState",
]
