"""
Industry-standard multi-track Undo/Redo transaction stack.

Provides atomic, reversible state transitions for all NLE timeline operations
(blade splits, trims, clip moves, volume changes, marker modifications).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

DEFAULT_MAX_UNDO_LEVELS = 100


class UndoCommand(ContractModel):
    """An atomic undoable timeline action."""

    command_id: Identifier
    name: str = Field(min_length=1, max_length=128)
    snapshot_before: dict[str, Any] = Field(default_factory=dict)
    snapshot_after: dict[str, Any] = Field(default_factory=dict)


class UndoManager:
    """
    Manages undo/redo stacks with configurable max history depth.
    """

    def __init__(self, max_levels: int = DEFAULT_MAX_UNDO_LEVELS) -> None:
        self._max_levels = max(10, max_levels)
        self._undo_stack: list[UndoCommand] = []
        self._redo_stack: list[UndoCommand] = []

    def execute(self, command: UndoCommand) -> None:
        """Push a newly executed command onto the undo stack and clear redo stack."""
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_levels:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        logger.debug(
            "undo_manager: executed %s (stack depth=%d)", command.name, len(self._undo_stack)
        )

    def undo(self) -> UndoCommand | None:
        """Pop and return the top command from the undo stack, moving it to redo."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        self._redo_stack.append(cmd)
        logger.info("undo_manager: UNDO %s", cmd.name)
        return cmd

    def redo(self) -> UndoCommand | None:
        """Pop and return the top command from the redo stack, moving it back to undo."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        self._undo_stack.append(cmd)
        logger.info("undo_manager: REDO %s", cmd.name)
        return cmd

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_action_name(self) -> str | None:
        return self._undo_stack[-1].name if self._undo_stack else None

    @property
    def redo_action_name(self) -> str | None:
        return self._redo_stack[-1].name if self._redo_stack else None

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()


__all__ = [
    "DEFAULT_MAX_UNDO_LEVELS",
    "UndoCommand",
    "UndoManager",
]
