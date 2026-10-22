"""
Keyboard shortcuts and editorial tool mode mapping.

Shortcut registry (Master Spec Section 27):
  - V: Select Tool
  - B: Blade Tool (Split at cursor)
  - S: Split at Playhead
  - N: Toggle Timeline Snapping
  - J / K / L: Shuttle Playback (Reverse / Pause / Forward)
  - Space: Toggle Play / Pause
  - Ctrl+K: Open Command Palette
  - Shift+R: Ripple Delete
"""

from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple


class EditToolMode(StrEnum):
    SELECT = "select"  # V
    BLADE = "blade"  # B
    TRIM = "trim"  # T
    RIPPLE = "ripple"  # R
    ROLL = "roll"  # N/A
    SLIP = "slip"  # Y
    SLIDE = "slide"  # U


class ShortcutAction(StrEnum):
    TOOL_SELECT = "tool.select"
    TOOL_BLADE = "tool.blade"
    TOOL_TRIM = "tool.trim"
    TOOL_RIPPLE = "tool.ripple"
    SPLIT_PLAYHEAD = "timeline.split_playhead"
    TOGGLE_SNAPPING = "timeline.toggle_snapping"
    SHUTTLE_REVERSE = "playback.shuttle_reverse"  # J
    SHUTTLE_PAUSE = "playback.shuttle_pause"  # K
    SHUTTLE_FORWARD = "playback.shuttle_forward"  # L
    PLAY_PAUSE = "playback.play_pause"  # Space
    COMMAND_PALETTE = "ui.command_palette"  # Ctrl+K
    RIPPLE_DELETE = "timeline.ripple_delete"  # Shift+Delete / Shift+R


class KeyboardShortcut(NamedTuple):
    key_sequence: str
    action: ShortcutAction
    description: str


DEFAULT_SHORTCUTS: list[KeyboardShortcut] = [
    KeyboardShortcut("V", ShortcutAction.TOOL_SELECT, "Select Tool"),
    KeyboardShortcut("B", ShortcutAction.TOOL_BLADE, "Blade Tool"),
    KeyboardShortcut("T", ShortcutAction.TOOL_TRIM, "Trim Tool"),
    KeyboardShortcut("R", ShortcutAction.TOOL_RIPPLE, "Ripple Edit Tool"),
    KeyboardShortcut("S", ShortcutAction.SPLIT_PLAYHEAD, "Split at Playhead"),
    KeyboardShortcut("N", ShortcutAction.TOGGLE_SNAPPING, "Toggle Timeline Snapping"),
    KeyboardShortcut("J", ShortcutAction.SHUTTLE_REVERSE, "Shuttle Reverse"),
    KeyboardShortcut("K", ShortcutAction.SHUTTLE_PAUSE, "Shuttle Pause"),
    KeyboardShortcut("L", ShortcutAction.SHUTTLE_FORWARD, "Shuttle Forward"),
    KeyboardShortcut("Space", ShortcutAction.PLAY_PAUSE, "Toggle Play/Pause"),
    KeyboardShortcut("Ctrl+K", ShortcutAction.COMMAND_PALETTE, "Open Command Palette"),
    KeyboardShortcut("Shift+R", ShortcutAction.RIPPLE_DELETE, "Ripple Delete"),
]


class NleProfile(StrEnum):
    DEFAULT = "default"
    PREMIERE_PRO = "premiere_pro"
    DAVINCI_RESOLVE = "davinci_resolve"
    FINAL_CUT_PRO = "final_cut_pro"


PREMIERE_SHORTCUTS: list[KeyboardShortcut] = [
    KeyboardShortcut("V", ShortcutAction.TOOL_SELECT, "Selection Tool"),
    KeyboardShortcut("C", ShortcutAction.TOOL_BLADE, "Razor Tool"),
    KeyboardShortcut("B", ShortcutAction.TOOL_RIPPLE, "Ripple Edit Tool"),
    KeyboardShortcut("Ctrl+K", ShortcutAction.SPLIT_PLAYHEAD, "Add Edit"),
    KeyboardShortcut("S", ShortcutAction.TOGGLE_SNAPPING, "Toggle Snapping"),
    KeyboardShortcut("J", ShortcutAction.SHUTTLE_REVERSE, "Shuttle Reverse"),
    KeyboardShortcut("K", ShortcutAction.SHUTTLE_PAUSE, "Shuttle Pause"),
    KeyboardShortcut("L", ShortcutAction.SHUTTLE_FORWARD, "Shuttle Forward"),
    KeyboardShortcut("Space", ShortcutAction.PLAY_PAUSE, "Play/Pause"),
    KeyboardShortcut("Shift+Delete", ShortcutAction.RIPPLE_DELETE, "Ripple Delete"),
]


class ShortcutManager:
    """Registry and resolver for keyboard shortcuts supporting NLE profiles."""

    def __init__(self, profile: NleProfile = NleProfile.DEFAULT) -> None:
        self._profile = profile
        self._map: dict[str, ShortcutAction] = {}
        self.load_profile(profile)

    def load_profile(self, profile: NleProfile) -> None:
        """Load shortcuts from a named NLE profile."""
        self._profile = profile
        shortcuts = PREMIERE_SHORTCUTS if profile == NleProfile.PREMIERE_PRO else DEFAULT_SHORTCUTS
        self._map = {s.key_sequence.upper(): s.action for s in shortcuts}

    def resolve(self, key_sequence: str) -> ShortcutAction | None:
        """Resolve a key sequence string (e.g. 'Ctrl+K') to a ShortcutAction."""
        return self._map.get(key_sequence.strip().upper())

    def bind(self, key_sequence: str, action: ShortcutAction) -> None:
        """Rebind a shortcut key sequence to an action."""
        self._map[key_sequence.strip().upper()] = action

    @property
    def profile(self) -> NleProfile:
        return self._profile


__all__ = [
    "DEFAULT_SHORTCUTS",
    "PREMIERE_SHORTCUTS",
    "EditToolMode",
    "KeyboardShortcut",
    "NleProfile",
    "ShortcutAction",
    "ShortcutManager",
]
