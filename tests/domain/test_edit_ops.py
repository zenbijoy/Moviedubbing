"""
Unit tests for domain EditCommand, UndoStack, and CommandGraph.
"""

from __future__ import annotations

import pytest

from aidub.domain.edit_ops import (
    CommandGraph,
    EditCommand,
    EditCommandType,
    SnapshotCheckpoint,
    UndoStack,
)


def test_edit_command_lifecycle() -> None:
    value = 0

    def do_inc() -> int:
        nonlocal value
        value += 10
        return value

    def do_dec() -> int:
        nonlocal value
        value -= 10
        return value

    cmd = EditCommand(
        description="Add 10",
        command_type=EditCommandType.CUSTOM,
        affected_cue_ids=["cue_1"],
        execute_fn=do_inc,
        undo_fn=do_dec,
    )

    res = cmd.execute()
    assert res == 10
    assert value == 10

    cmd.undo()
    assert value == 0

    cmd.redo()
    assert value == 10


def test_undo_stack_bounded_depth_and_dirty_tracking() -> None:
    stack = UndoStack(max_depth=5)
    assert not stack.can_undo
    assert not stack.can_redo
    assert not stack.is_dirty

    notifications: list[tuple[bool, bool, bool]] = []
    stack.add_listener(lambda u, r, d: notifications.append((u, r, d)))

    # Push commands
    for i in range(7):
        cmd = EditCommand(
            description=f"Action {i}",
            command_type=EditCommandType.TEXT_EDIT,
            affected_cue_ids=[f"cue_{i}"],
            execute_fn=lambda: None,
            undo_fn=lambda: None,
        )
        stack.push_and_execute(cmd)

    # Maximum depth is 5, so stack size must be 5
    assert stack.undo_count == 5
    assert stack.can_undo
    assert not stack.can_redo
    assert stack.is_dirty

    # Mark clean (e.g. project saved)
    stack.mark_clean()
    assert not stack.is_dirty

    # Undo one step
    undone = stack.undo()
    assert undone is not None
    assert stack.is_dirty
    assert stack.can_redo
    assert stack.redo_count == 1

    # Redo step
    redone = stack.redo()
    assert redone is not None
    assert not stack.is_dirty
    assert not stack.can_redo

    # Clear
    stack.clear()
    assert not stack.can_undo
    assert not stack.can_redo
    assert not stack.is_dirty
    assert len(notifications) > 0


def test_command_graph_checkpoints_and_mutated_cues() -> None:
    graph = CommandGraph()
    cp0 = graph.create_checkpoint("Initial")

    cmd1 = EditCommand(
        description="Edit cue 1 text",
        command_type=EditCommandType.TEXT_EDIT,
        affected_cue_ids=["cue_1"],
        execute_fn=lambda: "done1",
        undo_fn=lambda: None,
    )
    graph.record_command(cmd1)

    cmd2 = EditCommand(
        description="Shift cue 2 timing",
        command_type=EditCommandType.TIMING_SHIFT,
        affected_cue_ids=["cue_2", "cue_3"],
        execute_fn=lambda: "done2",
        undo_fn=lambda: None,
    )
    graph.record_command(cmd2)

    mutated = graph.get_mutated_cues_since(cp0)
    assert mutated == {"cue_1", "cue_2", "cue_3"}

    cp1 = graph.create_checkpoint("After shifts")
    cmd3 = EditCommand(
        description="Recast cue 4",
        command_type=EditCommandType.VOICE_RECAST,
        affected_cue_ids=["cue_4"],
        execute_fn=lambda: "done3",
        undo_fn=lambda: None,
    )
    graph.record_command(cmd3)

    assert graph.get_mutated_cues_since(cp1) == {"cue_4"}
