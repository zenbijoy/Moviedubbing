"""
Unit tests for EditEngine application service.
"""

from __future__ import annotations

import pytest

from aidub.application.timeline.edit_engine import EditEngine, EditResult
from aidub.domain.edit_ops import EditCommand, EditCommandType
from aidub.domain.invalidation import InvalidationGraph, PipelineStage


def test_edit_engine_apply_text_edit() -> None:
    engine = EditEngine()

    state = {"text": "Original English"}

    def do_edit() -> str:
        state["text"] = "নমস্কার বন্ধু"
        return state["text"]

    def undo_edit() -> str:
        state["text"] = "Original English"
        return state["text"]

    cmd = EditCommand(
        description="Update Bengali dialogue translation",
        command_type=EditCommandType.TEXT_EDIT,
        affected_cue_ids=["cue_101"],
        execute_fn=do_edit,
        undo_fn=undo_edit,
    )

    res = engine.apply(cmd)
    assert res.success
    assert res.output == "নমস্কার বন্ধু"
    assert "cue_101" in res.invalidated_stages

    # TEXT_EDIT invalidates TRANSLATION and all downstream stages:
    # TTS_BASE_AUDIO, RVC_CLONE_AUDIO, TIMED_AUDIO, PROCESSED_AUDIO, LIPSYNC_VIDEO, FINAL_MIX
    inv = res.invalidated_stages["cue_101"]
    assert PipelineStage.TRANSLATION in inv
    assert PipelineStage.TTS_BASE_AUDIO in inv
    assert PipelineStage.LIPSYNC_VIDEO in inv
    assert PipelineStage.TRANSCRIPT not in inv  # Upstream transcript is preserved!

    assert engine.can_undo
    assert not engine.can_redo
    assert engine.is_dirty

    # Test undo
    undo_res = engine.undo()
    assert undo_res is not None
    assert undo_res.success
    assert state["text"] == "Original English"
    assert engine.can_redo

    # Test redo
    redo_res = engine.redo()
    assert redo_res is not None
    assert redo_res.success
    assert state["text"] == "নমস্কার বন্ধু"
    assert not engine.can_redo


def test_edit_engine_dsp_param_change_invalidation() -> None:
    engine = EditEngine()

    cmd = EditCommand(
        description="Adjust vocal 4-band EQ high shelf",
        command_type=EditCommandType.DSP_PARAM_CHANGE,
        affected_cue_ids=["cue_202"],
        execute_fn=lambda: "eq_applied",
        undo_fn=lambda: None,
    )

    res = engine.apply(cmd)
    assert res.success
    inv = res.invalidated_stages["cue_202"]

    # DSP_PARAM_CHANGE only invalidates PROCESSED_AUDIO, LIPSYNC_VIDEO, and FINAL_MIX
    # It does NOT invalidate TTS or RVC!
    assert PipelineStage.PROCESSED_AUDIO in inv
    assert PipelineStage.FINAL_MIX in inv
    assert PipelineStage.TTS_BASE_AUDIO not in inv
    assert PipelineStage.RVC_CLONE_AUDIO not in inv


def test_edit_engine_checkpoint() -> None:
    engine = EditEngine()
    cmd = EditCommand(
        description="Timing nudge",
        command_type=EditCommandType.TIMING_SHIFT,
        affected_cue_ids=["cue_1"],
        execute_fn=lambda: None,
        undo_fn=lambda: None,
    )
    engine.apply(cmd)
    assert engine.is_dirty

    cp = engine.checkpoint("Saved project")
    assert cp.checkpoint_id.startswith("chk_")
    assert not engine.is_dirty
