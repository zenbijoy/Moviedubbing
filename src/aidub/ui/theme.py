"""
Broadcast-grade enterprise theme design tokens and Qt style generator.

Color system inspired by Hollywood NLE standards (DaVinci Resolve / Premiere Pro):
  - Primary Background: #121216 (Deep Slate)
  - Surface Card: #1E1E24 (Dark Charcoal)
  - Panel Border: #2D2D38
  - Primary Accent: #6366F1 (Studio Indigo)
  - Success / Active: #10B981 (Emerald)
  - Warning / Alert: #F59E0B (Amber)
  - Danger / Lock: #EF4444 (Crimson)
  - Text Primary: #F9FAFB
  - Text Muted: #9CA3AF
"""

from __future__ import annotations

from enum import StrEnum

from aidub.contracts.base import ContractModel


class ThemeMode(StrEnum):
    STUDIO_DARK = "studio_dark"
    BROADCAST_GRAY = "broadcast_gray"
    CYBER_DARK = "cyber_dark"
    HIGH_CONTRAST = "high_contrast"
    LIGHT_STUDIO = "light_studio"


class ColorTokens(ContractModel):
    bg_dark: str = "#121216"
    bg_surface: str = "#1E1E24"
    bg_elevated: str = "#2A2A34"
    border: str = "#2D2D38"
    accent: str = "#6366F1"
    accent_hover: str = "#4F46E5"
    success: str = "#10B981"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    text_primary: str = "#F9FAFB"
    text_secondary: str = "#D1D5DB"
    text_muted: str = "#9CA3AF"


_THEME_PRESETS: dict[ThemeMode, ColorTokens] = {
    ThemeMode.STUDIO_DARK: ColorTokens(
        bg_dark="#0D1118",
        bg_surface="#161D28",
        bg_elevated="#1C2431",
        border="#283241",
        accent="#4F8CFF",
        accent_hover="#3B82F6",
        text_primary="#F7F9FC",
        text_secondary="#D1D5DB",
        text_muted="#687386",
    ),
    ThemeMode.BROADCAST_GRAY: ColorTokens(
        bg_dark="#18181B",
        bg_surface="#24242A",
        bg_elevated="#2E2E36",
        border="#3F3F46",
        accent="#10B981",
        accent_hover="#059669",
        text_primary="#FAFAFA",
        text_secondary="#E4E4E7",
        text_muted="#A1A1AA",
    ),
    ThemeMode.CYBER_DARK: ColorTokens(
        bg_dark="#0A0E1A",
        bg_surface="#111827",
        bg_elevated="#1F2937",
        border="#374151",
        accent="#06B6D4",
        accent_hover="#0891B2",
        text_primary="#F9FAFB",
        text_secondary="#E5E7EB",
        text_muted="#9CA3AF",
    ),
    ThemeMode.HIGH_CONTRAST: ColorTokens(
        bg_dark="#000000",
        bg_surface="#111111",
        bg_elevated="#1E1E1E",
        border="#444444",
        accent="#F59E0B",
        accent_hover="#D97706",
        text_primary="#FFFFFF",
        text_secondary="#E0E0E0",
        text_muted="#AAAAAA",
    ),
    ThemeMode.LIGHT_STUDIO: ColorTokens(
        bg_dark="#F8FAFC",
        bg_surface="#FFFFFF",
        bg_elevated="#F1F5F9",
        border="#CBD5E1",
        accent="#2563EB",
        accent_hover="#1D4ED8",
        text_primary="#0F172A",
        text_secondary="#334155",
        text_muted="#64748B",
    ),
}


def get_theme_tokens(mode: str | ThemeMode = ThemeMode.STUDIO_DARK) -> ColorTokens:
    if isinstance(mode, str):
        try:
            mode = ThemeMode(mode.lower())
        except ValueError:
            mode = ThemeMode.STUDIO_DARK
    return _THEME_PRESETS.get(mode, _THEME_PRESETS[ThemeMode.STUDIO_DARK])


TRACK_COLOR_PALETTE: dict[str, str] = {
    "V1": "#3B82F6",  # Blue
    "V2": "#8B5CF6",  # Purple
    "A1": "#10B981",  # Emerald
    "A2": "#6366F1",  # Indigo
    "A3": "#F59E0B",  # Amber
    "A4": "#EC4899",  # Pink
    "A5": "#14B8A6",  # Teal
    "S1": "#F97316",  # Orange
    "S2": "#06B6D4",  # Cyan
}


def build_enterprise_stylesheet(tokens: ColorTokens | None = None) -> str:
    """Generate comprehensive QSS stylesheet for the application."""
    t = tokens or ColorTokens()
    return f"""
    QWidget {{
        background-color: {t.bg_dark};
        color: {t.text_primary};
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 10pt;
    }}
    QMainWindow::separator {{
        background-color: {t.border};
        width: 2px;
        height: 2px;
    }}
    QFrame#TopBar, QFrame#Sidebar, QStatusBar#StudioStatusBar {{
        background-color: {t.bg_surface};
        border-color: {t.border};
    }}
    QFrame.StudioCard, QFrame#ElevatedPanel, QFrame#Panel {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border};
        border-radius: 8px;
    }}
    QPushButton {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {t.accent_hover};
        border-color: {t.accent};
        color: #FFFFFF;
    }}
    QPushButton.Primary, QPushButton[primary="true"] {{
        background-color: {t.accent};
        color: #FFFFFF;
        border: none;
    }}
    QPushButton.Primary:hover, QPushButton[primary="true"]:hover {{
        background-color: {t.accent_hover};
    }}
    QLineEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {t.accent};
    }}
    QListWidget, QTreeWidget {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border};
        color: {t.text_primary};
        border-radius: 6px;
    }}
    QListWidget::item:selected {{
        background-color: {t.accent};
        color: #FFFFFF;
        border-radius: 4px;
    }}
    """


__all__ = [
    "TRACK_COLOR_PALETTE",
    "ColorTokens",
    "ThemeMode",
    "build_enterprise_stylesheet",
    "get_theme_tokens",
]
