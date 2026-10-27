"""Motion, transitions, and easing curves for AI Dubbing Studio."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def is_reduce_motion_enabled() -> bool:
    """Check if reduced motion is requested via environment or settings."""
    return os.environ.get("AIDUB_REDUCE_MOTION", "").lower() in ("1", "true", "yes")


def fade_in(
    widget: QWidget, duration_ms: int = 140, on_finished: Any = None
) -> QPropertyAnimation | None:
    """Fade in a widget smoothly using cubic ease-out."""
    if is_reduce_motion_enabled():
        widget.show()
        if on_finished:
            on_finished()
        return None

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)
    widget.show()

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out(
    widget: QWidget, duration_ms: int = 120, on_finished: Any = None
) -> QPropertyAnimation | None:
    """Fade out a widget smoothly."""
    if is_reduce_motion_enabled():
        widget.hide()
        if on_finished:
            on_finished()
        return None

    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def _done() -> None:
        widget.hide()
        if on_finished:
            on_finished()

    anim.finished.connect(_done)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim
