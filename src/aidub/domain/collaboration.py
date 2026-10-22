"""
Collaborative Session & Operational Transform Domain Models.

Defines session state, active participant editors, operational transform deltas,
and vector clocks for real-time multi-editor session synchronization.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier


class OperationType(StrEnum):
    INSERT_UTTERANCE = "insert_utterance"
    DELETE_UTTERANCE = "delete_utterance"
    UPDATE_SUBTITLE = "update_subtitle"
    SELECT_VOICE_TAKE = "select_voice_take"
    ADJUST_MIX_AUTOMATION = "adjust_mix_automation"
    SET_CURSOR_POSITION = "set_cursor_position"


class DeltaOperation(ContractModel):
    """Single operational transform delta item."""

    operation_id: Identifier
    op_type: OperationType
    target_path: str = Field(min_length=1)  # e.g. "timeline.utterances[u1].text"
    payload: dict[str, str | float | int | bool] = Field(default_factory=dict)
    client_id: Identifier
    vector_clock: int = Field(ge=0)


class EditorSession(ContractModel):
    """Active participant editor container."""

    client_id: Identifier
    user_id: Identifier
    display_name: str = Field(min_length=1)
    role: str = Field(
        default="editor", max_length=32
    )  # "director", "editor", "audio_engineer", "auditor"
    active_cursor_ms: int = Field(default=0, ge=0)
    connected: bool = True


class CollaborativeSessionState(ContractModel):
    """Full collaborative session state container."""

    session_id: Identifier
    project_id: Identifier
    active_editors: dict[str, EditorSession] = Field(default_factory=dict)
    sequence_version: int = Field(default=0, ge=0)
    applied_deltas: list[DeltaOperation] = Field(default_factory=list)


__all__ = [
    "CollaborativeSessionState",
    "DeltaOperation",
    "EditorSession",
    "OperationType",
]
