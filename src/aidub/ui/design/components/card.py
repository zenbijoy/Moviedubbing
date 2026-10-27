"""Studio Card and container widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QWidget


class StudioCard(QFrame):
    """Tier 1 or Tier 2 card container with subtle border and standard padding."""

    def __init__(self, tier: str = "elevated", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StudioCard")
        self.setProperty("tier", tier)
