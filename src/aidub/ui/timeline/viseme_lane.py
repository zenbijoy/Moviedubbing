"""
Viseme Lane Timeline Widget.

Renders colored phoneme/viseme blocks along an utterance timeline:
  - Bilabials (Blue), Labiodentals (Cyan), Vowels (Gold), Dental (Purple)
  - Interactive scrubbing and playhead alignment.
  - Headless safe for environments without PySide6.
"""

from __future__ import annotations

import logging
from typing import Any

from aidub.domain.viseme import VisemeGroup, VisemeKeyframe, VisemeTimeline

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import QFrame, QWidget

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


VISEME_COLORS: dict[VisemeGroup, str] = {
    VisemeGroup.SILENCE: "#334155",
    VisemeGroup.BILABIAL: "#3B82F6",
    VisemeGroup.LABIODENTAL: "#06B6D4",
    VisemeGroup.DENTAL_ALVEOLAR: "#8B5CF6",
    VisemeGroup.VELAR_PALATAL: "#EC4899",
    VisemeGroup.OPEN_VOWEL: "#F59E0B",
    VisemeGroup.ROUNDED_VOWEL: "#10B981",
    VisemeGroup.SPREAD_VOWEL: "#6366F1",
}


if _QT_AVAILABLE:

    class VisemeLaneWidget(QFrame):
        """Timeline track lane visualizing phoneme and viseme mouth keyframes."""

        playhead_scrubbed = Signal(float)  # current time in seconds

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(48)
            self.setStyleSheet("background-color: #0F172A; border-top: 1px solid #1E293B; border-bottom: 1px solid #1E293B;")
            self.timeline: VisemeTimeline | None = None
            self._playhead_s: float = 0.0

        def set_timeline(self, timeline: VisemeTimeline) -> None:
            self.timeline = timeline
            self.update()

        def set_playhead(self, playhead_s: float) -> None:
            self._playhead_s = playhead_s
            self.update()

        def paintEvent(self, event: Any) -> None:
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()

            if not self.timeline or self.timeline.duration_s <= 0.0:
                painter.setPen(QColor("#64748B"))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Viseme Cues")
                return

            dur = self.timeline.duration_s
            offset_s = self.timeline.lead_lag_offset_ms / 1000.0

            # Draw viseme blocks
            font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(font)

            for kf in self.timeline.keyframes:
                start_t = kf.start_s + offset_s
                end_t = kf.end_s + offset_s
                x1 = int((start_t / dur) * w)
                x2 = int((end_t / dur) * w)
                block_w = max(2, x2 - x1)

                color_hex = VISEME_COLORS.get(kf.viseme, "#64748B")
                color = QColor(color_hex)
                if kf.is_manual_override:
                    color = color.lighter(130)

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor("#0F172A"), 1))
                rect = QRectF(x1, 4, block_w, h - 8)
                painter.drawRoundedRect(rect, 3, 3)

                if block_w > 20:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, kf.label)

            # Draw playhead
            px = int((self._playhead_s / dur) * w)
            painter.setPen(QPen(QColor("#EF4444"), 2))
            painter.drawLine(px, 0, px, h)

else:
    class VisemeLaneWidget:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


__all__ = [
    "VISEME_COLORS",
    "VisemeLaneWidget",
]
