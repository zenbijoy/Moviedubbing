"""
Caption style presets (CapCut-style animated & broadcast styles).
Provides style dictionary lookups and ASS / CSS styling generation.
"""
from __future__ import annotations

from typing import Any


class CaptionStyle:
    """Pre-configured caption styling presets for video subtitle rendering."""

    PRESETS: dict[str, dict[str, Any]] = {
        "bold_white": {"font": "Arial", "size": 48, "color": "#FFFFFF", "outline": "#000000", "bold": True},
        "yellow_pop": {"font": "Impact", "size": 52, "color": "#FFD700", "outline": "#000000", "bold": True},
        "minimal": {"font": "Helvetica", "size": 36, "color": "#FFFFFF", "outline": None, "bold": False},
        "neon": {"font": "Arial", "size": 44, "color": "#00FFFF", "outline": "#FF00FF", "bold": True},
        "cinema_gold": {"font": "Cinzel", "size": 42, "color": "#E5B869", "outline": "#111111", "bold": True},
        "retro_red": {"font": "Bebas Neue", "size": 50, "color": "#FF3366", "outline": "#000000", "bold": True},
    }

    @classmethod
    def list(cls) -> list[str]:
        return list(cls.PRESETS.keys())

    @classmethod
    def get(cls, name: str) -> dict[str, Any]:
        return dict(cls.PRESETS.get(name, cls.PRESETS["minimal"]))

    @classmethod
    def to_ass_style(cls, name: str, style_name: str = "Default") -> str:
        """Generates an Advanced SubStation Alpha (ASS) Style definition line for ffmpeg burning."""
        p = cls.get(name)
        font = p.get("font", "Arial")
        size = p.get("size", 48)
        bold = "-1" if p.get("bold", False) else "0"
        # Convert hex color (#RRGGBB) to ASS color (&H00BBGGRR)
        hex_c = str(p.get("color", "#FFFFFF")).lstrip("#")
        r, g, b = hex_c[0:2], hex_c[2:4], hex_c[4:6]
        ass_color = f"&H00{b}{g}{r}"

        outline_hex = str(p.get("outline", "#000000") or "000000").lstrip("#")
        if len(outline_hex) == 6:
            or_, og, ob = outline_hex[0:2], outline_hex[2:4], outline_hex[4:6]
            ass_outline = f"&H00{ob}{og}{or_}"
            outline_width = "2"
        else:
            ass_outline = "&H00000000"
            outline_width = "0"

        return (
            f"Style: {style_name},{font},{size},{ass_color},&H000000FF,{ass_outline},&H00000000,"
            f"{bold},0,0,0,100,100,0,0,1,{outline_width},1,2,10,10,24,1"
        )

    @classmethod
    def to_css(cls, name: str) -> str:
        """Generates CSS inline style declarations for web and preview players."""
        p = cls.get(name)
        font = p.get("font", "sans-serif")
        size = p.get("size", 40)
        color = p.get("color", "#FFFFFF")
        weight = "bold" if p.get("bold", False) else "normal"
        outline = p.get("outline")
        shadow = f"text-shadow: -2px -2px 0 {outline}, 2px -2px 0 {outline}, -2px 2px 0 {outline}, 2px 2px 0 {outline};" if outline else ""
        return f"font-family: '{font}', sans-serif; font-size: {size}px; color: {color}; font-weight: {weight}; {shadow}"


__all__ = ["CaptionStyle"]
