"""Status chips, badges, and syllable duration budget indicators."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from aidub.ui.design.icons import get_pixmap
from aidub.ui.design.tokens import (
    RADIUS_PILL,
    ThemeMode,
    get_theme_tokens,
)


class StatusChip(QWidget):
    """Pill badge showing state icon and text (e.g. Offline, Local Only, Running, Review)."""

    def __init__(
        self,
        text: str,
        state: str = "info",  # "info", "success", "warning", "danger", "ai", "neutral"
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tokens = get_theme_tokens(ThemeMode.STUDIO_DARK)
        self.state = state

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(5)

        self._icon_lbl = QLabel(self)
        self._text_lbl = QLabel(text, self)
        self._text_lbl.setProperty("role", "status")

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)

        self.update_state(state, text, icon_name)

    def update_state(
        self, state: str, text: str | None = None, icon_name: str | None = None
    ) -> None:
        self.state = state
        if text:
            self._text_lbl.setText(text)

        color_map = {
            "success": (self.tokens.success, self.tokens.success_subtle, "check"),
            "warning": (self.tokens.warning, self.tokens.warning_subtle, "alert-triangle"),
            "danger": (self.tokens.danger, self.tokens.danger_subtle, "x-circle"),
            "ai": (self.tokens.ai_purple, self.tokens.ai_subtle, "sparkles"),
            "info": (self.tokens.info, self.tokens.info_subtle, "cloud"),
            "neutral": (self.tokens.text_muted, "transparent", "help-circle"),
        }

        fg, bg, default_icon = color_map.get(
            state, (self.tokens.text_secondary, "transparent", "sparkles")
        )
        chosen_icon = icon_name or default_icon
        self._icon_lbl.setPixmap(get_pixmap(chosen_icon, size=12, color_hex=fg))
        self._text_lbl.setStyleSheet(f"color: {fg}; font-size: 11px; font-weight: 600;")
        self.setStyleSheet(
            f"background-color: {bg}; border: 1px solid {fg}44; border-radius: {RADIUS_PILL}px;"
        )


class SyllableBudgetIndicator(QWidget):
    """Visual meter comparing original duration/syllable budget against dub voice take."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setMinimumWidth(100)
        self.tokens = get_theme_tokens(ThemeMode.STUDIO_DARK)
        self.delta_seconds: float = 0.0  # +0.2s = over budget, -0.1s = under budget
        self.orig_syllables: int = 0
        self.dub_syllables: int = 0

    def set_budget(
        self, orig_dur: float, dub_dur: float, orig_syl: int = 0, dub_syl: int = 0
    ) -> None:
        self.delta_seconds = dub_dur - orig_dur
        self.orig_syllables = orig_syl
        self.dub_syllables = dub_syl
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background track
        painter.fillRect(0, 0, w, h, QColor(self.tokens.bg_elevated))

        # Tolerance: +/- 0.15s is green (fit), 0.15s - 0.35s is amber (warn), > 0.35s is red (drift)
        abs_d = abs(self.delta_seconds)
        if abs_d <= 0.15:
            color = QColor(self.tokens.success)
            status_text = f"Sync: {self.delta_seconds:+.2f}s (OK)"
        elif abs_d <= 0.35:
            color = QColor(self.tokens.warning)
            status_text = f"Sync: {self.delta_seconds:+.2f}s (Review)"
        else:
            color = QColor(self.tokens.danger)
            status_text = f"Sync: {self.delta_seconds:+.2f}s (Clip)"

        # Fill proportional delta bar
        bar_w = min(w, max(4, int(w * min(1.0, abs_d / 0.8))))
        painter.fillRect(0, h - 3, bar_w, 3, color)

        # Draw text
        painter.setPen(color)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(4, h - 5, status_text)
        painter.end()
