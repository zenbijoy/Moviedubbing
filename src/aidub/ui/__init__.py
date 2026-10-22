"""User interface package."""

from .application import DesktopApplication
from .command_palette import CommandPaletteDialog
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
