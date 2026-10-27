"""Custom Studio Button variants with stateful styling and Lucide icons."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton, QWidget

from aidub.ui.design.icons import get_icon


class StudioButton(QPushButton):
    """Sleek button supporting Primary, Secondary, Ghost, AI, and Destructive variants."""

    def __init__(
        self,
        text: str = "",
        variant: str = "secondary",  # "primary", "secondary", "ghost", "ai", "destructive"
        icon_name: str | None = None,
        icon_color: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        if compact:
            self.setProperty("compact", True)
            self.setFixedHeight(28)
            self.setIconSize(QSize(14, 14))
        else:
            self.setFixedHeight(32)
            self.setIconSize(QSize(16, 16))

        if icon_name:
            color = icon_color or ("#FFFFFF" if variant in ("primary", "ai") else "#CBD5E1")
            self.setIcon(get_icon(icon_name, size=16, color_hex=color))
