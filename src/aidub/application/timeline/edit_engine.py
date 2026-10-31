"""
Core Non-Linear Editorial Engine (EditEngine).

Applies editorial operations to project timeline state with:
  - Atomic transaction execution through EditCommand.
  - Automatic dependency cascade through InvalidationGraph.
  - Full Undo/Redo stack management with dirty state tracking.
  - Headless execution guaranteeing complete CLI and PySide6 compatibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aidub.domain.edit_ops import (
    CommandGraph,
    EditCommand,
    EditCommandType,
    SnapshotCheckpoint,
    UndoStack,
)
from aidub.domain.invalidation import InvalidationGraph, PipelineStage

logger = logging.getLogger(__name__)


@dataclass
class EditResult:
    """Outcome of applying an editorial command."""

    success: bool
    command_id: str
    command_type: EditCommandType
    affected_cue_ids: list[str]
    invalidated_stages: dict[str, set[PipelineStage]] = field(default_factory=dict)
    output: Any = None
    error_message: str = ""


class EditEngine:
    """
    Timeline Editorial Controller for DubForge.

    Coordinates command execution, undo/redo stacks, and artifact invalidation.
    """

    def __init__(
        self,
        undo_stack: UndoStack | None = None,
        invalidation_graph: InvalidationGraph | None = None,
    ) -> None:
        self.undo_stack: UndoStack = undo_stack or UndoStack()
        self.command_graph: CommandGraph = CommandGraph(undo_stack=self.undo_stack)
        self.invalidation_graph: InvalidationGraph = invalidation_graph or InvalidationGraph()

    @property
    def can_undo(self) -> bool:
        return self.undo_stack.can_undo

    @property
    def can_redo(self) -> bool:
        return self.undo_stack.can_redo

    @property
    def is_dirty(self) -> bool:
        return self.undo_stack.is_dirty

    def apply(self, command: EditCommand) -> EditResult:
        """
        Executes an EditCommand, updates the command graph, pushes to undo stack,
        and invalidates downstream artifacts for affected cues.
        """
        try:
            output = self.command_graph.record_command(command, execute=True)

            # Invalidate downstream artifacts
            invalidated = self.invalidation_graph.invalidate_cues(
                cue_ids=command.affected_cue_ids,
                command_type=command.command_type,
            )

            logger.info(
                "EditEngine applied %s (id=%s) on %d cues",
                command.command_type.value,
                command.command_id,
                len(command.affected_cue_ids),
            )

            return EditResult(
                success=True,
                command_id=command.command_id,
                command_type=command.command_type,
                affected_cue_ids=list(command.affected_cue_ids),
                invalidated_stages=invalidated,
                output=output,
            )
        except Exception as ex:
            logger.exception("EditEngine failed to apply command: %s", command.description)
            return EditResult(
                success=False,
                command_id=command.command_id,
                command_type=command.command_type,
                affected_cue_ids=list(command.affected_cue_ids),
                error_message=str(ex),
            )

    def undo(self) -> EditResult | None:
        """Rolls back the most recent command."""
        cmd = self.undo_stack.undo()
        if cmd is None:
            return None

        # On undo, invalidate again because state has rolled back
        invalidated = self.invalidation_graph.invalidate_cues(
            cue_ids=cmd.affected_cue_ids,
            command_type=cmd.command_type,
        )

        return EditResult(
            success=True,
            command_id=cmd.command_id,
            command_type=cmd.command_type,
            affected_cue_ids=list(cmd.affected_cue_ids),
            invalidated_stages=invalidated,
        )

    def redo(self) -> EditResult | None:
        """Re-applies the most recently undone command."""
        cmd = self.undo_stack.redo()
        if cmd is None:
            return None

        invalidated = self.invalidation_graph.invalidate_cues(
            cue_ids=cmd.affected_cue_ids,
            command_type=cmd.command_type,
        )

        return EditResult(
            success=True,
            command_id=cmd.command_id,
            command_type=cmd.command_type,
            affected_cue_ids=list(cmd.affected_cue_ids),
            invalidated_stages=invalidated,
        )

    def checkpoint(self, description: str = "Project Save") -> SnapshotCheckpoint:
        """Creates a snapshot checkpoint and marks editor state as clean."""
        return self.command_graph.create_checkpoint(description)


__all__ = [
    "EditEngine",
    "EditResult",
]
