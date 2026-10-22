"""Agent state tracking across dubbing iterations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ConfigDict

from aidub.contracts.base import ContractModel, Identifier


class SegmentState(ContractModel):
    """Current state of a single dialogue segment in the agent loop."""

    utterance_id: Identifier
    speaker_id: Identifier
    source_text: str
    target_text: str = ""
    start_ms: int
    end_ms: int
    duration_ms: int
    quality_score: float = 0.0
    duration_delta_pct: float = 0.0
    passed_qc: bool = False
    flagged_for_review: bool = False
    assigned_voice: str = ""
    dubbed_audio_path: str = ""

    model_config = ConfigDict(frozen=False)


@dataclass
class AgentState:
    """State of the entire movie dubbing job maintained by the DubbingAgent."""

    segments: list[SegmentState] = field(default_factory=list)
    source_language: str = "auto"
    target_language: str = "bn"
    glossary: dict[str, str] = field(default_factory=dict)
    character_notes: str = ""
    iteration_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_segments(self) -> int:
        return len(self.segments)

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.segments if s.passed_qc)

    @property
    def pass_rate(self) -> float:
        if not self.segments:
            return 0.0
        return self.passed_count / len(self.segments)

    def all_segments_pass(self, threshold: float = 0.80) -> bool:
        """Return True if average segment quality score meets or exceeds threshold."""
        if not self.segments:
            return False
        return self.pass_rate >= threshold

    def update_segment_translation(self, utterance_id: str, translated_text: str) -> None:
        """Update target translation for a segment."""
        for seg in self.segments:
            if str(seg.utterance_id) == str(utterance_id):
                seg.target_text = translated_text
                break

    def update_segment_qc(
        self,
        utterance_id: str,
        quality_score: float,
        passed_qc: bool,
        duration_delta_pct: float = 0.0,
    ) -> None:
        """Update QC results for a segment."""
        for seg in self.segments:
            if str(seg.utterance_id) == str(utterance_id):
                seg.quality_score = quality_score
                seg.passed_qc = passed_qc
                seg.duration_delta_pct = duration_delta_pct
                break


__all__ = ["AgentState", "SegmentState"]
