"""User interface package with lazy Qt import support for headless environments."""

from __future__ import annotations

import importlib
from typing import Any

from .commands import Command, CommandRegistry
from .editorial import EditorialCommandEngine, SnappingEngine
from .keyboard_shortcuts import (
    DEFAULT_SHORTCUTS,
    EditToolMode,
    KeyboardShortcut,
    ShortcutAction,
    ShortcutManager,
)
from .workspace_manager import (
    PanelState,
    WorkspaceLayout,
    WorkspaceManager,
    WorkspacePreset,
)

_LAZY_EXPORTS = {
    "DesktopApplication": ".application",
    "CommandPaletteDialog": ".command_palette",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        val = getattr(module, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_SHORTCUTS",
    "Command",
    "CommandPaletteDialog",
    "CommandRegistry",
    "DesktopApplication",
    "EditToolMode",
    "EditorialCommandEngine",
    "KeyboardShortcut",
    "PanelState",
    "ShortcutAction",
    "ShortcutManager",
    "SnappingEngine",
    "WorkspaceLayout",
    "WorkspaceManager",
    "WorkspacePreset",
]
