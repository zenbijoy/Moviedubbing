"""Broadcast-grade enterprise theme design tokens and Qt style generator.

Re-exports and delegates to the unified `aidub.ui.design` system.
"""

from __future__ import annotations

from aidub.ui.design.stylesheet import build_stylesheet
from aidub.ui.design.tokens import (
    THEME_PRESETS,
    ColorTokens,
    ThemeMode,
    get_theme_tokens,
)


def build_enterprise_stylesheet(tokens: ColorTokens | None = None) -> str:
    """Generate enterprise broadcast stylesheet using unified design system."""
    return build_stylesheet(tokens)


__all__ = [
    "THEME_PRESETS",
    "ColorTokens",
    "ThemeMode",
    "build_enterprise_stylesheet",
    "get_theme_tokens",
]
