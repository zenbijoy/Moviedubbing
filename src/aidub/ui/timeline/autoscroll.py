"""
Dynamic timeline zoom & playhead auto-scroll controller.

Modes:
  - PAGE: Flips the viewport scroll by one page when playhead reaches right edge
  - SMOOTH_CENTER: Dynamically scrolls timeline to keep playhead centered during playback
  - OFF: Manual scroll only
"""

from __future__ import annotations

from enum import StrEnum

from aidub.ui.timeline.model import TimelineLayoutEngine


class AutoScrollMode(StrEnum):
    PAGE = "page"
    SMOOTH_CENTER = "smooth_center"
    OFF = "off"


class TimelineScrollController:
    """
    Manages timeline viewport scrolling and playhead tracking during playback.
    """

    def __init__(
        self,
        engine: TimelineLayoutEngine,
        mode: AutoScrollMode = AutoScrollMode.SMOOTH_CENTER,
    ) -> None:
        self.engine = engine
        self.mode = mode

    def update_playhead(self, playhead_ms: int) -> int:
        """
        Update viewport scroll_x_ms based on current playhead_ms and AutoScrollMode.

        Returns updated scroll_x_ms.
        """
        if self.mode == AutoScrollMode.OFF:
            return self.engine.scroll_x_ms

        viewport_dur_ms = (
            self.engine.px_to_time(self.engine.viewport_width_px) - self.engine.scroll_x_ms
        )
        if viewport_dur_ms <= 0:
            return self.engine.scroll_x_ms

        if self.mode == AutoScrollMode.SMOOTH_CENTER:
            # Center playhead at viewport mid-point
            new_scroll = max(0, playhead_ms - (viewport_dur_ms // 2))
            self.engine.scroll_x_ms = new_scroll
            return new_scroll

        if self.mode == AutoScrollMode.PAGE:
            # Flip page when playhead moves past right edge
            visible_end = self.engine.scroll_x_ms + viewport_dur_ms
            if playhead_ms >= visible_end:
                self.engine.scroll_x_ms = playhead_ms
            elif playhead_ms < self.engine.scroll_x_ms:
                self.engine.scroll_x_ms = max(0, playhead_ms - (viewport_dur_ms // 2))

        return self.engine.scroll_x_ms

    def zoom_at_point(self, focal_px: float, zoom_factor: float) -> float:
        """
        Zoom timeline in/out anchored around focal_px cursor position.
        """
        focal_time = self.engine.px_to_time(focal_px)
        new_zoom = max(1.0, min(5000.0, self.engine.zoom_px_per_sec * zoom_factor))
        self.engine.zoom_px_per_sec = new_zoom

        # Adjust scroll so focal_time remains under focal_px
        new_scroll = max(0, int(focal_time - (focal_px / (new_zoom / 1000.0))))
        self.engine.scroll_x_ms = new_scroll
        return new_zoom


__all__ = [
    "AutoScrollMode",
    "TimelineScrollController",
]
