"""Score ring and visual metric badges (replacing plain text 'Not measured')."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from aidub.ui.design.tokens import ThemeMode, get_theme_tokens


class ScoreRingWidget(QWidget):
    """Circular radial meter for QC scores (Naturalness, MOS, Bleurt, Lip-Sync sync score)."""

    def __init__(
        self,
        score: float | None = None,
        label: str = "Score",
        size: int = 48,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.score = score  # 0.0 to 1.0, or None if unmeasured
        self.label = label
        self.tokens = get_theme_tokens(ThemeMode.STUDIO_DARK)

    def set_score(self, score: float | None) -> None:
        self.score = score
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        rect = QRectF(4, 4, size - 8, size - 8)

        # Track background circle
        track_pen = QPen(QColor(self.tokens.border_subtle), 3.5)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self.score is None:
            # Unmeasured: gray dash or dot
            painter.setPen(QPen(QColor(self.tokens.text_muted), 1))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "N/A")
            painter.end()
            return

        # Measured: determine semantic color (Green >= 0.8, Amber >= 0.55, Red < 0.55)
        val = max(0.0, min(1.0, self.score))
        if val >= 0.80:
            color = QColor(self.tokens.success)
        elif val >= 0.55:
            color = QColor(self.tokens.warning)
        else:
            color = QColor(self.tokens.danger)

        arc_pen = QPen(color, 3.5)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)

        # Start at 12 o'clock (90 degrees) and draw clockwise (-val * 360)
        start_angle = 90 * 16
        span_angle = -int(val * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Centered percentage / score text
        painter.setPen(QColor(self.tokens.text_primary))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(val * 100)}%")
        painter.end()
