"""Persistent automation plan and quality gates for the dubbing workstation.

The desktop UI uses this module as its headless source of truth.  It deliberately
contains no Qt imports so plans can be created, resumed, audited and tested by
CLI workers as well as by the interactive studio.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from aidub.domain.base import DomainModel, UtcDatetime, utc_now


class AutomationStage(StrEnum):
    """Canonical end-to-end production stages shown by the studio agent."""

    INGEST = "ingest"
    AUDIO_SEPARATION = "audio_separation"
    SPEAKER_ANALYSIS = "speaker_analysis"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"
    VOICE_CASTING = "voice_casting"
    SYNTHESIS = "synthesis"
    TIMING = "timing"
    LIP_SYNC = "lip_sync"
    MIX = "mix"
    QUALITY_CONTROL = "quality_control"
    MASTER_EXPORT = "master_export"


class StageStatus(StrEnum):
    """Observable lifecycle for an automation stage."""

    WAITING = "waiting"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.SKIPPED}


class QualityMetric(DomainModel):
    """One measurable delivery gate."""

    metric: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=80)
    score: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    threshold: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    blocking: bool = True
    detail: str = Field(default="", max_length=500)

    @property
    def passed(self) -> bool:
        return self.score >= self.threshold


class QualityGateReport(DomainModel):
    """Auditable collection of delivery metrics."""

    profile: str = Field(default="theatrical", min_length=2, max_length=40)
    metrics: tuple[QualityMetric, ...] = ()
    evaluated_at: UtcDatetime = Field(default_factory=utc_now)

    @property
    def passed(self) -> bool:
        return not any(metric.blocking and not metric.passed for metric in self.metrics)

    @property
    def overall_score(self) -> float:
        if not self.metrics:
            return 0.0
        return sum(metric.score for metric in self.metrics) / len(self.metrics)

    @property
    def blockers(self) -> tuple[QualityMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.blocking and not metric.passed)


class AutomationStageState(DomainModel):
    """Persisted state for one node in the automation graph."""

    stage: AutomationStage
    label: str = Field(min_length=2, max_length=80)
    status: StageStatus = StageStatus.WAITING
    progress: int = Field(default=0, ge=0, le=100)
    detail: str = Field(default="", max_length=500)
    dependencies: tuple[AutomationStage, ...] = ()
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> Self:
        if self.status is StageStatus.RUNNING and self.started_at is None:
            raise ValueError("running stage requires started_at")
        if self.status.terminal and self.finished_at is None:
            raise ValueError("terminal stage requires finished_at")
        if not self.status.terminal and self.finished_at is not None:
            raise ValueError("non-terminal stage cannot have finished_at")
        if self.status is StageStatus.SUCCEEDED and self.progress != 100:
            raise ValueError("successful stage requires 100 percent progress")
        if (
            self.finished_at is not None
            and self.started_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("stage finish cannot precede start")
        return self


class AgenticStudioState(DomainModel):
    """Durable operator state for one localized master."""

    schema_version: int = Field(default=1, ge=1)
    project_name: str = Field(min_length=1, max_length=160)
    source_path: str = Field(default="", max_length=2_048)
    source_language: str = Field(default="auto", min_length=2, max_length=35)
    target_language: str = Field(default="bn", min_length=2, max_length=35)
    quality_profile: str = Field(default="theatrical", min_length=2, max_length=40)
    stages: tuple[AutomationStageState, ...]
    quality_report: QualityGateReport | None = None
    updated_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        stage_ids = [item.stage for item in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("automation plan contains duplicate stages")
        known = set(stage_ids)
        for item in self.stages:
            if item.stage in item.dependencies:
                raise ValueError("automation stage cannot depend on itself")
            missing = set(item.dependencies) - known
            if missing:
                raise ValueError(f"stage {item.stage} has missing dependencies: {missing}")
        return self

    @property
    def progress(self) -> int:
        if not self.stages:
            return 0
        return round(sum(item.progress for item in self.stages) / len(self.stages))

    @property
    def is_complete(self) -> bool:
        return all(
            item.status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
            for item in self.stages
        )

    def stage(self, stage: AutomationStage) -> AutomationStageState:
        try:
            return next(item for item in self.stages if item.stage is stage)
        except StopIteration as exc:
            raise KeyError(f"stage not present in plan: {stage}") from exc

    def ready_stages(self) -> tuple[AutomationStage, ...]:
        succeeded = {
            item.stage
            for item in self.stages
            if item.status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
        }
        return tuple(
            item.stage
            for item in self.stages
            if item.status in {StageStatus.WAITING, StageStatus.READY}
            and set(item.dependencies) <= succeeded
        )

    def update_stage(
        self,
        stage: AutomationStage,
        *,
        status: StageStatus,
        progress: int,
        detail: str = "",
        at: datetime | None = None,
    ) -> AgenticStudioState:
        """Return the next immutable plan revision after a worker event."""

        instant = at or utc_now()
        current = self.stage(stage)
        started_at = current.started_at
        finished_at = None
        if status is StageStatus.RUNNING:
            started_at = started_at or instant
        elif status.terminal:
            started_at = started_at or instant
            finished_at = instant

        replacement = current.model_copy(
            update={
                "status": status,
                "progress": (
                    100
                    if status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
                    else progress
                ),
                "detail": detail,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        )
        stages = tuple(replacement if item.stage is stage else item for item in self.stages)
        return self.model_copy(update={"stages": stages, "updated_at": instant})

    def with_quality_report(self, report: QualityGateReport) -> AgenticStudioState:
        return self.model_copy(update={"quality_report": report, "updated_at": report.evaluated_at})


_STAGE_SPECS: tuple[tuple[AutomationStage, str, tuple[AutomationStage, ...]], ...] = (
    (AutomationStage.INGEST, "Ingest & media validation", ()),
    (AutomationStage.AUDIO_SEPARATION, "Dialogue / music separation", (AutomationStage.INGEST,)),
    (
        AutomationStage.SPEAKER_ANALYSIS,
        "Speaker & character analysis",
        (AutomationStage.AUDIO_SEPARATION,),
    ),
    (AutomationStage.TRANSCRIPTION, "Speech recognition", (AutomationStage.AUDIO_SEPARATION,)),
    (
        AutomationStage.TRANSLATION,
        "Context-aware translation",
        (AutomationStage.SPEAKER_ANALYSIS, AutomationStage.TRANSCRIPTION),
    ),
    (
        AutomationStage.VOICE_CASTING,
        "Consent-aware voice casting",
        (AutomationStage.SPEAKER_ANALYSIS,),
    ),
    (
        AutomationStage.SYNTHESIS,
        "Emotion-preserving voice synthesis",
        (AutomationStage.TRANSLATION, AutomationStage.VOICE_CASTING),
    ),
    (AutomationStage.TIMING, "Timing & prosody fit", (AutomationStage.SYNTHESIS,)),
    (AutomationStage.LIP_SYNC, "Selective neural lip sync", (AutomationStage.TIMING,)),
    (
        AutomationStage.MIX,
        "Dialogue edit & theatrical mix",
        (AutomationStage.TIMING, AutomationStage.AUDIO_SEPARATION),
    ),
    (
        AutomationStage.QUALITY_CONTROL,
        "Multimodal quality control",
        (AutomationStage.LIP_SYNC, AutomationStage.MIX),
    ),
    (
        AutomationStage.MASTER_EXPORT,
        "Mastering & delivery package",
        (AutomationStage.QUALITY_CONTROL,),
    ),
)


def create_automation_plan(
    project_name: str,
    *,
    source_path: str = "",
    source_language: str = "auto",
    target_language: str = "bn",
    quality_profile: str = "theatrical",
) -> AgenticStudioState:
    """Create the deterministic production graph used by UI and headless workers."""

    stages = tuple(
        AutomationStageState(
            stage=stage,
            label=label,
            status=StageStatus.READY if not dependencies else StageStatus.WAITING,
            dependencies=dependencies,
        )
        for stage, label, dependencies in _STAGE_SPECS
    )
    return AgenticStudioState(
        project_name=project_name,
        source_path=source_path,
        source_language=source_language,
        target_language=target_language,
        quality_profile=quality_profile,
        stages=stages,
    )


def build_quality_report(
    *,
    voice: float,
    emotion: float,
    timing: float,
    lip_sync: float,
    translation: float = 0.95,
    audio: float = 0.95,
    profile: str = "theatrical",
) -> QualityGateReport:
    """Build the standard delivery-gate report displayed in the inspector."""

    threshold = 0.90 if profile == "theatrical" else 0.85
    return QualityGateReport(
        profile=profile,
        metrics=(
            QualityMetric(
                metric="translation",
                label="Translation",
                score=translation,
                threshold=threshold,
            ),
            QualityMetric(metric="voice", label="Voice", score=voice, threshold=threshold),
            QualityMetric(metric="emotion", label="Emotion", score=emotion, threshold=0.85),
            QualityMetric(metric="timing", label="Timing", score=timing, threshold=0.92),
            QualityMetric(metric="lip_sync", label="Lip Sync", score=lip_sync, threshold=0.90),
            QualityMetric(metric="audio", label="Audio", score=audio, threshold=0.90),
        ),
    )


class StudioSessionStore:
    """Atomic JSON persistence for resumable studio automation sessions."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    @staticmethod
    def _safe_name(project_name: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name.strip()).strip("-.")
        return value[:100] or "untitled"

    def path_for(self, project_name: str) -> Path:
        return self.workspace / f"{self._safe_name(project_name)}.studio.json"

    def load(self, project_name: str) -> AgenticStudioState | None:
        path = self.path_for(project_name)
        if not path.is_file():
            return None
        return AgenticStudioState.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, state: AgenticStudioState) -> Path:
        self.workspace.mkdir(parents=True, exist_ok=True)
        target = self.path_for(state.project_name)
        payload = state.model_dump_json(indent=2)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.workspace,
                prefix=f".{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            temp_path.replace(target)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        return target


__all__ = [
    "AgenticStudioState",
    "AutomationStage",
    "AutomationStageState",
    "QualityGateReport",
    "QualityMetric",
    "StageStatus",
    "StudioSessionStore",
    "build_quality_report",
    "create_automation_plan",
]
