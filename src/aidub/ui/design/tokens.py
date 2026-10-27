"""Design System Tokens for AI Dubbing Studio."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ThemeMode(StrEnum):
    STUDIO_DARK = "studio_dark"
    BROADCAST_GRAY = "broadcast_gray"
    CYBER_DARK = "cyber_dark"
    HIGH_CONTRAST = "high_contrast"
    LIGHT_STUDIO = "light_studio"


@dataclass(frozen=True)
class ColorTokens:
    # Background Tiers
    bg_base: str = "#121216"  # Tier 0 (App Canvas / Root)
    bg_surface: str = "#1E1E24"  # Tier 1 (Sidebars, Main Panels)
    bg_elevated: str = "#2A2A34"  # Tier 2 (Cards, Controls, Lists)
    bg_overlay: str = "#333342"  # Tier 3 (Dropdowns, Popovers, Modals)

    # Borders
    border_subtle: str = "#2D2D38"  # Subtle divider (0.5 - 1px)
    border_strong: str = "#3D3D4C"  # Focus / Active surface border
    border_accent: str = "#6366F1"  # Accent outline

    # Primary Accent & Focus
    accent: str = "#6366F1"
    accent_hover: str = "#4F46E5"
    accent_pressed: str = "#4338CA"
    accent_subtle: str = "rgba(99, 102, 241, 0.15)"  # 12-15% opacity tint for badges

    # AI & Dubbing Semantic Tokens (Master Spec Sec 26-27)
    ai_purple: str = "#8B5CF6"  # AI-generated content / takes
    ai_subtle: str = "rgba(139, 92, 246, 0.18)"
    success: str = "#10B981"  # Pass / Verified / Done (Green)
    success_subtle: str = "rgba(16, 185, 129, 0.15)"
    warning: str = "#F59E0B"  # Needs Review / Drift (Amber)
    warning_subtle: str = "rgba(245, 158, 11, 0.15)"
    danger: str = "#EF4444"  # Failure / Out of Spec (Red)
    danger_subtle: str = "rgba(239, 68, 68, 0.15)"
    info: str = "#06B6D4"  # Informational / Blue
    info_subtle: str = "rgba(6, 182, 212, 0.15)"

    # Text Tiers
    text_primary: str = "#F9FAFB"  # Main headers, active text
    text_secondary: str = "#D1D5DB"  # Body, labels
    text_muted: str = "#9CA3AF"  # Meta, disabled, subtle hints
    text_inverse: str = "#FFFFFF"  # Text on bright accents

    # Backward compatibility properties for theme.py consumers
    @property
    def bg_dark(self) -> str:
        return self.bg_base

    @property
    def border(self) -> str:
        return self.border_subtle


# Spacing Scale (in pixels)
SPACE_2XS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32

# Corner Radii (in pixels)
RADIUS_XS = 3
RADIUS_SM = 4
RADIUS_MD = 6  # Buttons, inputs, chips
RADIUS_LG = 10  # Cards, group boxes, dialogs
RADIUS_XL = 14  # Spotlight palette, floating overlays
RADIUS_PILL = 9999

# Typography Scale (pt / px)
FONT_DISPLAY = 22
FONT_TITLE = 17
FONT_PANEL_TITLE = 15
FONT_BODY = 13
FONT_META = 12
FONT_TIMELINE = 11
FONT_MICRO = 10

# Theme Presets
THEME_PRESETS: dict[ThemeMode, ColorTokens] = {
    ThemeMode.STUDIO_DARK: ColorTokens(
        bg_base="#0B0E14",
        bg_surface="#111622",
        bg_elevated="#182030",
        bg_overlay="#1F293D",
        border_subtle="#1F293D",
        border_strong="#2E3C57",
        border_accent="#3B82F6",
        accent="#3B82F6",
        accent_hover="#2563EB",
        accent_pressed="#1D4ED8",
        accent_subtle="rgba(59, 130, 246, 0.15)",
        ai_purple="#A855F7",
        ai_subtle="rgba(168, 85, 247, 0.18)",
        success="#10B981",
        success_subtle="rgba(16, 185, 129, 0.15)",
        warning="#F59E0B",
        warning_subtle="rgba(245, 158, 11, 0.15)",
        danger="#EF4444",
        danger_subtle="rgba(239, 68, 68, 0.15)",
        info="#06B6D4",
        info_subtle="rgba(6, 182, 212, 0.15)",
        text_primary="#F8FAFC",
        text_secondary="#CBD5E1",
        text_muted="#64748B",
        text_inverse="#FFFFFF",
    ),
    ThemeMode.BROADCAST_GRAY: ColorTokens(
        bg_base="#141416",
        bg_surface="#1A1A1E",
        bg_elevated="#24242A",
        bg_overlay="#2F2F36",
        border_subtle="#2A2A32",
        border_strong="#3F3F4A",
        border_accent="#10B981",
        accent="#10B981",
        accent_hover="#059669",
        accent_pressed="#047857",
        accent_subtle="rgba(16, 185, 129, 0.15)",
        ai_purple="#9333EA",
        ai_subtle="rgba(147, 51, 234, 0.18)",
        success="#10B981",
        success_subtle="rgba(16, 185, 129, 0.15)",
        warning="#F59E0B",
        warning_subtle="rgba(245, 158, 11, 0.15)",
        danger="#EF4444",
        danger_subtle="rgba(239, 68, 68, 0.15)",
        info="#0284C7",
        info_subtle="rgba(2, 132, 199, 0.15)",
        text_primary="#FAFAFA",
        text_secondary="#D4D4D8",
        text_muted="#71717A",
        text_inverse="#FFFFFF",
    ),
    ThemeMode.CYBER_DARK: ColorTokens(
        bg_base="#070B12",
        bg_surface="#0D131F",
        bg_elevated="#141E30",
        bg_overlay="#1C2942",
        border_subtle="#18243B",
        border_strong="#283A5E",
        border_accent="#06B6D4",
        accent="#06B6D4",
        accent_hover="#0891B2",
        accent_pressed="#0E7490",
        accent_subtle="rgba(6, 182, 212, 0.15)",
        ai_purple="#C084FC",
        ai_subtle="rgba(192, 132, 252, 0.18)",
        success="#10B981",
        success_subtle="rgba(16, 185, 129, 0.15)",
        warning="#FBBF24",
        warning_subtle="rgba(251, 191, 36, 0.15)",
        danger="#F43F5E",
        danger_subtle="rgba(244, 63, 94, 0.15)",
        info="#38BDF8",
        info_subtle="rgba(56, 189, 248, 0.15)",
        text_primary="#F0FDF4",
        text_secondary="#99F6E4",
        text_muted="#475569",
        text_inverse="#042F2E",
    ),
    ThemeMode.HIGH_CONTRAST: ColorTokens(
        bg_base="#000000",
        bg_surface="#0A0A0A",
        bg_elevated="#141414",
        bg_overlay="#1F1F1F",
        border_subtle="#383838",
        border_strong="#737373",
        border_accent="#38BDF8",
        accent="#38BDF8",
        accent_hover="#0284C7",
        accent_pressed="#0369A1",
        accent_subtle="rgba(56, 189, 248, 0.25)",
        ai_purple="#D8B4FE",
        ai_subtle="rgba(216, 180, 254, 0.25)",
        success="#4ADE80",
        success_subtle="rgba(74, 222, 128, 0.25)",
        warning="#FDE047",
        warning_subtle="rgba(253, 224, 71, 0.25)",
        danger="#F87171",
        danger_subtle="rgba(248, 113, 113, 0.25)",
        info="#67E8F9",
        info_subtle="rgba(103, 232, 249, 0.25)",
        text_primary="#FFFFFF",
        text_secondary="#E5E5E5",
        text_muted="#A3A3A3",
        text_inverse="#000000",
    ),
    ThemeMode.LIGHT_STUDIO: ColorTokens(
        bg_base="#F1F5F9",
        bg_surface="#FFFFFF",
        bg_elevated="#F8FAFC",
        bg_overlay="#FFFFFF",
        border_subtle="#E2E8F0",
        border_strong="#CBD5E1",
        border_accent="#2563EB",
        accent="#2563EB",
        accent_hover="#1D4ED8",
        accent_pressed="#1E40AF",
        accent_subtle="rgba(37, 99, 235, 0.10)",
        ai_purple="#7C3AED",
        ai_subtle="rgba(124, 58, 237, 0.12)",
        success="#059669",
        success_subtle="rgba(5, 150, 105, 0.10)",
        warning="#D97706",
        warning_subtle="rgba(217, 119, 6, 0.10)",
        danger="#DC2626",
        danger_subtle="rgba(220, 38, 38, 0.10)",
        info="#0284C7",
        info_subtle="rgba(2, 132, 199, 0.10)",
        text_primary="#0F172A",
        text_secondary="#334155",
        text_muted="#64748B",
        text_inverse="#FFFFFF",
    ),
}


def get_theme_tokens(mode: ThemeMode | str = ThemeMode.STUDIO_DARK) -> ColorTokens:
    """Retrieve color tokens for a given theme mode with fallback."""
    if isinstance(mode, str):
        try:
            mode = ThemeMode(mode)
        except ValueError:
            mode = ThemeMode.STUDIO_DARK
    return THEME_PRESETS.get(mode, THEME_PRESETS[ThemeMode.STUDIO_DARK])
