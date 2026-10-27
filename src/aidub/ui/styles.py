"""AI Movie Dubbing Studio — Design System Style Adapter.

Unified with `aidub.ui.design`.
"""

from __future__ import annotations

from aidub.ui.design.stylesheet import build_stylesheet
from aidub.ui.design.tokens import (
    FONT_BODY,
    FONT_DISPLAY,
    FONT_META,
    FONT_PANEL_TITLE,
    FONT_TIMELINE,
    FONT_TITLE,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SPACE_2XL,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    THEME_PRESETS,
    ColorTokens,
    ThemeMode,
    get_theme_tokens,
)

# Backward compatibility constants
BG0 = "#0B0E14"
BG1 = "#111622"
BG2 = "#182030"
PANEL = "#111622"
ELEVATED = "#182030"
BORDER = "#1F293D"
BORDER_LIGHT = "#2E3C57"

PRIMARY = "#3B82F6"
PRIMARY_HOVER = "#2563EB"
PRIMARY_PRESSED = "#1D4ED8"

AI_VIOLET = "#A855F7"
AI_VIOLET_HOVER = "#9333EA"
VOICE_CYAN = "#06B6D4"
TRANS_PURPLE = "#A855F7"
AUDIO_GREEN = "#10B981"
LIPSYNC_PINK = "#EC4899"
WARNING = "#F59E0B"
DANGER = "#EF4444"
SUCCESS = "#10B981"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#64748B"

APPLICATION_STYLE: str = build_stylesheet()

__all__ = [
    "AI_VIOLET",
    "AI_VIOLET_HOVER",
    "APPLICATION_STYLE",
    "AUDIO_GREEN",
    "BG0",
    "BG1",
    "BG2",
    "BORDER",
    "BORDER_LIGHT",
    "DANGER",
    "ELEVATED",
    "FONT_BODY",
    "FONT_DISPLAY",
    "FONT_META",
    "FONT_PANEL_TITLE",
    "FONT_TIMELINE",
    "FONT_TITLE",
    "LIPSYNC_PINK",
    "PANEL",
    "PRIMARY",
    "PRIMARY_HOVER",
    "PRIMARY_PRESSED",
    "RADIUS_LG",
    "RADIUS_MD",
    "RADIUS_SM",
    "RADIUS_XL",
    "SPACE_2XL",
    "SPACE_LG",
    "SPACE_MD",
    "SPACE_SM",
    "SPACE_XL",
    "SPACE_XS",
    "SUCCESS",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "THEME_PRESETS",
    "TRANS_PURPLE",
    "VOICE_CYAN",
    "WARNING",
    "ColorTokens",
    "ThemeMode",
    "build_stylesheet",
    "get_theme_tokens",
]
