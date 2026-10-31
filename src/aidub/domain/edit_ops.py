"""
Domain models for editorial commands, undo/redo history, and command graphs.

Enables professional NLE non-destructive operations:
  - Atomic, reversible EditCommands.
  - UndoStack with configurable depth and clean/dirty snapshot tracking.
  - CommandGraph mapping revisions, timeline state mutations, and invalidation triggers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EditCommandType(StrEnum):
    """Categorized domain edit operations."""

    TEXT_EDIT = "text_edit"
    TIMING_SHIFT = "timing_shift"
    VOICE_RECAST = "voice_recast"
    EMOTION_TWEAK = "emotion_tweak"
    DSP_PARAM_CHANGE = "dsp_param_change"
    VISEME_OVERRIDE = "viseme_override"
    BLADE_SPLIT = "blade_split"
    RIPPLE_DELETE = "ripple_delete"
    MARKER_MUTATION = "marker_mutation"
    TAKE_SELECT = "take_select"
    CUSTOM = "custom"


@dataclass
class EditCommand:
    """Atomic, reversible timeline command."""

    description: str
    command_type: EditCommandType = EditCommandType.CUSTOM
    affected_cue_ids: list[str] = field(default_factory=list)
    execute_fn: Callable[[], Any] | None = None
    undo_fn: Callable[[], Any] | None = None
    redo_fn: Callable[[], Any] | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: f"cmd_{uuid4().hex[:12]}")
    created_at_s: float = field(default_factory=time.time)

    def execute(self) -> Any:
        if self.execute_fn is not None:
            return self.execute_fn()
        return None

    def undo(self) -> Any:
        if self.undo_fn is not None:
            return self.undo_fn()
        return None

    def redo(self) -> Any:
        if self.redo_fn is not None:
            return self.redo_fn()
        return self.execute()


@dataclass
class SnapshotCheckpoint:
    """Represents a saved state in project history."""

    checkpoint_id: str
    created_at_s: float
    command_index: int
    description: str


class UndoStack:
    """
    DAW/NLE Grade Undo/Redo Engine.

    Guarantees:
      - Bounded history depth to prevent memory unbounded growth.
      - Dirty / Clean project status against saved checkpoints.
      - Callback hooks on state mutations.
    """

    def __init__(self, max_depth: int = 150) -> None:
        self.max_depth: int = max(1, max_depth)
        self._undo_stack: list[EditCommand] = []
        self._redo_stack: list[EditCommand] = []
        self._clean_index: int = 0  # Points to top of undo stack when saved
        self._listeners: list[Callable[[bool, bool, bool], None]] = []

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def is_dirty(self) -> bool:
        return len(self._undo_stack) != self._clean_index

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def add_listener(self, callback: Callable[[bool, bool, bool], None]) -> None:
        """Subscribe to (can_undo, can_redo, is_dirty) changes."""
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb(self.can_undo, self.can_redo, self.is_dirty)
            except Exception:
                pass

    def push_and_execute(self, command: EditCommand) -> Any:
        """Executes the command and places it on the undo stack, clearing redo."""
        result = command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)
            if self._clean_index > 0:
                self._clean_index -= 1
        self._redo_stack.clear()
        self._notify()
        return result

    def push_executed(self, command: EditCommand) -> None:
        """Pushes an already-executed command onto the stack."""
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)
            if self._clean_index > 0:
                self._clean_index -= 1
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> EditCommand | None:
        """Rolls back the most recent command."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify()
        return cmd

    def redo(self) -> EditCommand | None:
        """Re-applies the most recently undone command."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.redo()
        self._undo_stack.append(cmd)
        self._notify()
        return cmd

    def mark_clean(self) -> None:
        """Marks current stack state as clean (e.g. project saved)."""
        self._clean_index = len(self._undo_stack)
        self._notify()

    def clear(self) -> None:
        """Resets the history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clean_index = 0
        self._notify()


class CommandGraph:
    """
    Project-level Command and Invalidation History Graph.

    Tracks chronological revisions, checkpoints, and affected cues.
    """

    def __init__(self, undo_stack: UndoStack | None = None) -> None:
        self.undo_stack: UndoStack = undo_stack or UndoStack()
        self.checkpoints: list[SnapshotCheckpoint] = []
        self._history: list[EditCommand] = []

    def record_command(self, command: EditCommand, execute: bool = True) -> Any:
        self._history.append(command)
        if execute:
            return self.undo_stack.push_and_execute(command)
        self.undo_stack.push_executed(command)
        return None

    def create_checkpoint(self, description: str = "Saved State") -> SnapshotCheckpoint:
        cp = SnapshotCheckpoint(
            checkpoint_id=f"chk_{uuid4().hex[:10]}",
            created_at_s=time.time(),
            command_index=self.undo_stack.undo_count,
            description=description,
        )
        self.checkpoints.append(cp)
        self.undo_stack.mark_clean()
        return cp

    def get_mutated_cues_since(self, checkpoint: SnapshotCheckpoint) -> set[str]:
        """Returns all cue IDs mutated since the specified checkpoint."""
        cues: set[str] = set()
        start_idx = checkpoint.command_index
        for cmd in self._history[start_idx:]:
            cues.update(cmd.affected_cue_ids)
        return cues


__all__ = [
    "CommandGraph",
    "EditCommand",
    "EditCommandType",
    "SnapshotCheckpoint",
    "UndoStack",
]
