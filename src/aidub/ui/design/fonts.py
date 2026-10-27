"""Font management and typographic scales for AI Dubbing Studio."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def setup_application_fonts(app: Any) -> None:
    """Register bundled fonts (Inter, Noto Sans Bengali) and configure typography."""
    if app is None:
        return

    try:
        from PySide6.QtGui import QFont, QFontDatabase

        # 1. Register any bundled TTF/OTF fonts in resources/fonts if present
        fonts_dir = Path(__file__).resolve().parents[3] / "resources" / "fonts"
        if fonts_dir.is_dir():
            for font_file in fonts_dir.glob("*.ttf"):
                QFontDatabase.addApplicationFont(str(font_file))
            for font_file in fonts_dir.glob("*.otf"):
                QFontDatabase.addApplicationFont(str(font_file))

        # 2. Configure default sans-serif font stack with Inter & Noto Sans Bengali preference
        preferred_family = "Inter"
        available_families = QFontDatabase.families()
        if preferred_family not in available_families:
            for candidate in ("Segoe UI Variable", "Segoe UI", "Noto Sans", "Roboto", "sans-serif"):
                if candidate in available_families:
                    preferred_family = candidate
                    break

        app_font = QFont(preferred_family, 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)

        # Set up font substitutions for multilingual Bengali conjunct rendering
        QFont.insertSubstitutions(
            preferred_family,
            [
                "Noto Sans Bengali",
                "Vrinda",
                "Kalpurush",
                "SolaimanLipi",
                "Segoe UI Variable",
                "Segoe UI",
                "sans-serif",
            ],
        )

        app.setFont(app_font)
    except Exception as exc:
        logger.warning("Could not initialize typography stack: %s", exc)


def get_monospace_timecode_font(size: int = 11) -> Any:
    """Return a tabular/monospace font for precise timecode display."""
    from PySide6.QtGui import QFont

    font = QFont("Consolas", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
    return font
