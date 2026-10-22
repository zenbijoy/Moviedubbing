"""Immutable, local-first contracts for shared source analysis.

The analysis center combines work with very different runtimes (media inspection,
ASR, scene detection, and so on).  These contracts deliberately describe the
work and its evidence without exposing a particular SDK, network endpoint, or
model implementation to project state.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self, TypeAlias

from pydantic import Field, StringConstraints, field_validator, model_validator

from aidub.contracts.base import Identifier
from aidub.domain.base import DomainModel, UtcDatetime, normalize_utc, utc_now
from aidub.domain.types import MimeType, NonEmptyStr, SemanticVersion, Sha256, require_unique

BASIS_POINTS = 10_000

AnalysisRunId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^anl_[A-Za-z0-9][A-Za-z0-9_-]{2,63}$"),
]
LocalArtifactPath: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_024),
]


class AnalysisModel(DomainModel):
    """Strict frozen base for source-analysis snapshots and boundary contracts."""


class AnalysisExecutionMode(StrEnum):
    """Execution modes intentionally supported by this local-first boundary."""

    LOCAL = "local"


class AnalysisStageKind(StrEnum):
    """Shared-source operations that can contribute evidence to a project."""

    MEDIA_PROBE = "media_probe"
    SOURCE_FINGERPRINT = "source_fingerprint"
    PROXY = "proxy"
    THUMBNAILS = "thumbnails"
    WAVEFORM = "waveform"
    REFERENCE_AUDIO = "reference_audio"
    SUBTITLE_IMPORT = "subtitle_import"
    SCENE_DETECTION = "scene_detection"
    AUDIO_SEPARATION = "audio_separation"
    VOICE_ACTIVITY = "voice_activity"
    SPEECH_RECOGNITION = "speech_recognition"
    WORD_ALIGNMENT = "word_alignment"
    DIARIZATION = "diarization"
    OVERLAP_DETECTION = "overlap_detection"
    LANGUAGE_IDENTIFICATION = "language_identification"
    FACE_TRACKING = "face_tracking"
    ACTIVE_SPEAKER = "active_speaker"


class AnalysisStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

    @property
    def terminal(self) -> bool:
        return self in {
            self.SUCCEEDED,
            self.FAILED,
            self.CANCELLED,
            self.SKIPPED,
        }


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED}


class AnalysisFailureCode(StrEnum):
    INVALID_SOURCE = "invalid_source"
    UNSUPPORTED_MEDIA = "unsupported_media"
    INTEGRITY_FAILURE = "integrity_failure"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_EXECUTION_FAILURE = "model_execution_failure"
    OUTPUT_VALIDATION_FAILURE = "output_validation_failure"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    TIMEOUT = "timeout"
    POLICY_BLOCKED = "policy_blocked"
    INTERNAL = "internal"


class AnalysisCancellationReason(StrEnum):
    USER_REQUESTED = "user_requested"
    PROJECT_CLOSED = "project_closed"
    APPLICATION_SHUTDOWN = "application_shutdown"
    TIME_LIMIT = "time_limit"
    RESOURCE_PREEMPTED = "resource_preempted"
    POLICY_CHANGED = "policy_changed"


class EvidenceKind(StrEnum):
    MEDIA_METADATA = "media_metadata"
    SOURCE_FINGERPRINT = "source_fingerprint"
    DERIVATIVE = "derivative"
    SUBTITLE_HINT = "subtitle_hint"
    SCENE_BOUNDARY = "scene_boundary"
    VOICE_ACTIVITY = "voice_activity"
    SPEECH_SEGMENT = "speech_segment"
    WORD_ALIGNMENT = "word_alignment"
    SPEAKER_CLUSTER = "speaker_cluster"
    OVERLAP_REGION = "overlap_region"
    LANGUAGE_HYPOTHESIS = "language_hypothesis"
    FACE_TRACK = "face_track"
    ACTIVE_SPEAKER_LINK = "active_speaker_link"
    WARNING = "warning"


class ConfidenceMetric(StrEnum):
    LANGUAGE_IDENTIFICATION = "language_identification"
    SPEECH_RECOGNITION = "speech_recognition"
    WORD_ALIGNMENT = "word_alignment"
    SPEAKER_DIARIZATION = "speaker_diarization"
    OVERLAP_DETECTION = "overlap_detection"
    SCENE_BOUNDARY = "scene_boundary"
    SOURCE_SEPARATION = "source_separation"
    FACE_TRACKING = "face_tracking"
    ACTIVE_SPEAKER_LINK = "active_speaker_link"


class LocalAnalyzerIdentity(AnalysisModel):
    """Identity of a locally installed adapter, engine, and optional model build.

    There is intentionally no endpoint, account, provider region, or remote model
    alias here.  A caller cannot describe a network-required analyzer through
    this contract.
    """

    adapter_id: Identifier
    adapter_version: SemanticVersion
    engine_id: Identifier
    engine_version: SemanticVersion
    model_id: Identifier | None = None
    model_version: SemanticVersion | None = None
    model_weights_sha256: Sha256 | None = None
    execution_mode: AnalysisExecutionMode = AnalysisExecutionMode.LOCAL
    network_required: Literal[False] = False

    @model_validator(mode="after")
    def _validate_model_identity(self) -> Self:
        model_fields = (self.model_id, self.model_version, self.model_weights_sha256)
        if any(value is None for value in model_fields) and any(
            value is not None for value in model_fields
        ):
            raise ValueError("model id, version, and weights hash must be supplied together")
        if self.execution_mode is not AnalysisExecutionMode.LOCAL:
            raise ValueError("source-analysis adapters must execute locally")
        if self.network_required:
            raise ValueError("source-analysis adapters cannot require network access")
        return self


class LocalAnalysisSource(AnalysisModel):
    """Content-addressed local source input; paths are project-relative only."""

    source_id: Identifier
    source_sha256: Sha256
    byte_length: int = Field(ge=0)
    relative_artifact_path: LocalArtifactPath

    @field_validator("relative_artifact_path")
    @classmethod
    def _validate_local_path(cls, value: str) -> str:
        _validate_local_artifact_path(value)
        return value


class AnalysisFailure(AnalysisModel):
    """Safe, structured explanation for a terminal failed analysis stage/run."""

    code: AnalysisFailureCode
    message: NonEmptyStr
    retryable: bool
    occurred_at: UtcDatetime
    remediation_code: Identifier | None = None


class AnalysisCancellation(AnalysisModel):
    """Structured cancellation fact retained instead of converting it to a failure."""

    reason: AnalysisCancellationReason
    requested_at: UtcDatetime
    requested_by: Identifier | None = None


class AnalysisMeasurement(AnalysisModel):
    """A compact exact measurement attached to evidence, without embedding payloads."""

    metric_id: Identifier
    numerator: int
    denominator: int = Field(default=1, gt=0)
    unit: Identifier


class AnalysisEvidence(AnalysisModel):
    """Content-addressed evidence emitted by exactly one local analysis stage."""

    evidence_id: Identifier
    stage_id: Identifier
    kind: EvidenceKind
    source_sha256: Sha256
    payload_sha256: Sha256
    producer: LocalAnalyzerIdentity
    observed_at: UtcDatetime
    local_artifact_path: LocalArtifactPath | None = None
    mime_type: MimeType | None = None
    measurements: tuple[AnalysisMeasurement, ...] = ()

    @field_validator("local_artifact_path")
    @classmethod
    def _validate_optional_local_path(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_local_artifact_path(value)
        return value

    @model_validator(mode="after")
    def _validate_measurements(self) -> Self:
        require_unique(
            tuple(measurement.metric_id for measurement in self.measurements),
            field_name="evidence measurement metric_ids",
        )
        if self.mime_type is not None and self.local_artifact_path is None:
            raise ValueError("a MIME type requires a local evidence artifact path")
        return self


class ConfidenceAssessment(AnalysisModel):
    """A calibrated confidence claim tied to source-hash and evidence references.

    Scores use integer basis points.  Calibration identifiers prevent accidental
    arithmetic across model outputs whose confidence scales are incomparable.
    """

    assessment_id: Identifier
    stage_id: Identifier
    subject_id: Identifier
    metric: ConfidenceMetric
    confidence_basis_points: int = Field(ge=0, le=BASIS_POINTS)
    calibration_id: Identifier
    source_sha256: Sha256
    producer: LocalAnalyzerIdentity
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    weight_units: int = Field(default=1, gt=0)
    assessed_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_evidence_ids(self) -> Self:
        require_unique(self.evidence_ids, field_name="confidence evidence_ids")
        return self


class ConfidenceAggregate(AnalysisModel):
    """Deterministic, calibration-safe weighted confidence aggregate."""

    metric: ConfidenceMetric
    calibration_id: Identifier
    source_sha256: Sha256
    confidence_basis_points: int = Field(ge=0, le=BASIS_POINTS)
    total_weight_units: int = Field(gt=0)
    assessment_ids: tuple[Identifier, ...] = Field(min_length=1)
    aggregated_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_assessment_ids(self) -> Self:
        require_unique(self.assessment_ids, field_name="confidence aggregate assessment_ids")
        if tuple(sorted(self.assessment_ids)) != self.assessment_ids:
            raise ValueError("confidence aggregate assessment_ids must be canonical sorted order")
        return self


class AnalysisStagePlan(AnalysisModel):
    """Stable work declaration used to create one immutable analysis run."""

    stage_id: Identifier
    kind: AnalysisStageKind
    weight_units: int = Field(gt=0, le=1_000_000)
    total_units: int = Field(default=1, gt=0, le=2_147_483_647)
    dependency_stage_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _validate_dependencies(self) -> Self:
        require_unique(self.dependency_stage_ids, field_name="stage dependency_stage_ids")
        if self.stage_id in self.dependency_stage_ids:
            raise ValueError("a stage cannot depend on itself")
        return self

    def initial_stage(self, *, at: datetime | None = None) -> AnalysisStage:
        """Create the pending stage snapshot for this immutable plan item."""

        return AnalysisStage(
            stage_id=self.stage_id,
            kind=self.kind,
            weight_units=self.weight_units,
            total_units=self.total_units,
            dependency_stage_ids=self.dependency_stage_ids,
            updated_at=normalize_utc(at or utc_now()),
        )


class AnalysisStage(AnalysisStagePlan):
    """One stage snapshot with exact work accounting and terminal facts."""

    status: AnalysisStageStatus = AnalysisStageStatus.PENDING
    completed_units: int = Field(default=0, ge=0)
    message: str = Field(default="", max_length=1_000)
    failure: AnalysisFailure | None = None
    cancellation: AnalysisCancellation | None = None
    evidence_ids: tuple[Identifier, ...] = ()
    updated_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate_stage_state(self) -> Self:
        if self.completed_units > self.total_units:
            raise ValueError("stage completed units cannot exceed total units")
        require_unique(self.evidence_ids, field_name="stage evidence_ids")
        if self.failure is not None and self.failure.occurred_at > self.updated_at:
            raise ValueError("stage failure cannot occur after its update timestamp")
        if self.cancellation is not None and self.cancellation.requested_at > self.updated_at:
            raise ValueError("stage cancellation cannot occur after its update timestamp")

        if self.status is AnalysisStageStatus.PENDING:
            if self.completed_units != 0:
                raise ValueError("pending stages must have zero completed units")
            if self.failure is not None or self.cancellation is not None:
                raise ValueError("pending stages cannot carry terminal facts")
        elif self.status is AnalysisStageStatus.RUNNING:
            if self.failure is not None or self.cancellation is not None:
                raise ValueError("running stages cannot carry terminal facts")
        elif self.status in {AnalysisStageStatus.SUCCEEDED, AnalysisStageStatus.SKIPPED}:
            if self.completed_units != self.total_units:
                raise ValueError("successful or skipped stages must report complete progress")
            if self.failure is not None or self.cancellation is not None:
                raise ValueError("successful or skipped stages cannot carry terminal facts")
        elif self.status is AnalysisStageStatus.FAILED:
            if self.failure is None or self.cancellation is not None:
                raise ValueError("failed stages require exactly one structured failure")
        elif self.status is AnalysisStageStatus.CANCELLED:
            if self.cancellation is None or self.failure is not None:
                raise ValueError("cancelled stages require exactly one cancellation fact")
        return self

    @property
    def progress_basis_points(self) -> int:
        """Floor-normalized exact progress suitable for deterministic aggregation."""

        return (self.completed_units * BASIS_POINTS) // self.total_units

    def advance(
        self,
        status: AnalysisStageStatus,
        *,
        completed_units: int | None = None,
        message: str | None = None,
        failure: AnalysisFailure | None = None,
        cancellation: AnalysisCancellation | None = None,
        at: datetime | None = None,
    ) -> AnalysisStage:
        """Return a validated non-regressing stage revision.

        Retrying or re-planning uses a new analysis run.  A stage in a terminal
        state is therefore immutable, which makes published progress monotonic.
        """

        if not can_transition_stage_status(self.status, status):
            raise ValueError(f"cannot transition stage from {self.status} to {status}")
        instant = normalize_utc(at or utc_now())
        if instant < self.updated_at:
            raise ValueError("stage update timestamp cannot move backwards")

        if completed_units is None:
            target_completed = self.completed_units
            if status in {AnalysisStageStatus.SUCCEEDED, AnalysisStageStatus.SKIPPED}:
                target_completed = self.total_units
        else:
            target_completed = completed_units
        if target_completed < self.completed_units:
            raise ValueError("stage completed units cannot move backwards")
        if target_completed > self.total_units:
            raise ValueError("stage completed units cannot exceed total units")

        payload = self.model_dump(mode="python")
        payload.update(
            {
                "status": status,
                "completed_units": target_completed,
                "message": self.message if message is None else message,
                "failure": failure if status is AnalysisStageStatus.FAILED else None,
                "cancellation": cancellation if status is AnalysisStageStatus.CANCELLED else None,
                "updated_at": instant,
            }
        )
        return type(self).model_validate(payload)


class AnalysisStageProgress(AnalysisModel):
    """Projection of a stage used in a published run-level progress snapshot."""

    stage_id: Identifier
    status: AnalysisStageStatus
    completed_units: int = Field(ge=0)
    total_units: int = Field(gt=0)
    progress_basis_points: int = Field(ge=0, le=BASIS_POINTS)

    @model_validator(mode="after")
    def _validate_progress(self) -> Self:
        if self.completed_units > self.total_units:
            raise ValueError("stage progress completed units cannot exceed total units")
        expected = (self.completed_units * BASIS_POINTS) // self.total_units
        if self.progress_basis_points != expected:
            raise ValueError("stage progress basis points do not match exact work units")
        if self.status in {AnalysisStageStatus.SUCCEEDED, AnalysisStageStatus.SKIPPED}:
            if self.progress_basis_points != BASIS_POINTS:
                raise ValueError("successful or skipped progress must be complete")
        if self.status is AnalysisStageStatus.PENDING and self.progress_basis_points != 0:
            raise ValueError("pending progress must be zero")
        return self

    @classmethod
    def from_stage(cls, stage: AnalysisStage) -> AnalysisStageProgress:
        return cls(
            stage_id=stage.stage_id,
            status=stage.status,
            completed_units=stage.completed_units,
            total_units=stage.total_units,
            progress_basis_points=stage.progress_basis_points,
        )


class AnalysisProgress(AnalysisModel):
    """A complete, immutable, weighted source-analysis progress publication."""

    run_id: AnalysisRunId
    status: AnalysisRunStatus
    stages: tuple[AnalysisStageProgress, ...] = Field(min_length=1)
    completed_weighted_units: int = Field(ge=0)
    total_weighted_units: int = Field(gt=0)
    progress_basis_points: int = Field(ge=0, le=BASIS_POINTS)
    emitted_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_progress(self) -> Self:
        require_unique(
            tuple(stage.stage_id for stage in self.stages), field_name="progress stage_ids"
        )
        if self.completed_weighted_units > self.total_weighted_units:
            raise ValueError("completed weighted units cannot exceed total weighted units")
        expected = (self.completed_weighted_units * BASIS_POINTS) // self.total_weighted_units
        if self.progress_basis_points != expected:
            raise ValueError("run progress basis points do not match weighted units")
        expected_status = derive_run_status(self.stages)
        if self.status is not expected_status:
            raise ValueError("run progress status does not match stage statuses")
        if (
            self.status is AnalysisRunStatus.SUCCEEDED
            and self.progress_basis_points != BASIS_POINTS
        ):
            raise ValueError("successful analysis progress must be complete")
        if self.status is AnalysisRunStatus.QUEUED and self.progress_basis_points != 0:
            raise ValueError("queued analysis progress must be zero")
        return self


class SourceAnalysisRequest(AnalysisModel):
    """Provider-neutral request for a fixed locally executed analysis plan."""

    run_id: AnalysisRunId
    source: LocalAnalysisSource
    stages: tuple[AnalysisStagePlan, ...] = Field(min_length=1)
    requested_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        _validate_stage_graph(self.stages)
        return self

    def initial_stages(self, *, at: datetime | None = None) -> tuple[AnalysisStage, ...]:
        """Materialize the fixed plan as pending stage snapshots."""

        instant = normalize_utc(at or self.requested_at)
        return tuple(stage.initial_stage(at=instant) for stage in self.stages)


class AnalysisRun(AnalysisModel):
    """Auditable snapshot of one source-analysis attempt and all published facts."""

    run_id: AnalysisRunId
    source: LocalAnalysisSource
    analyzer: LocalAnalyzerIdentity
    stages: tuple[AnalysisStage, ...] = Field(min_length=1)
    progress: AnalysisProgress
    status: AnalysisRunStatus
    evidence: tuple[AnalysisEvidence, ...] = ()
    confidence_assessments: tuple[ConfidenceAssessment, ...] = ()
    failure: AnalysisFailure | None = None
    cancellation: AnalysisCancellation | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate_run(self) -> Self:
        _validate_stage_graph(self.stages)
        stage_by_id: dict[str, AnalysisStage] = {
            str(stage.stage_id): stage for stage in self.stages
        }
        _validate_stage_dependencies_satisfied(stage_by_id)

        expected_status = derive_run_status(self.stages)
        if self.status is not expected_status:
            raise ValueError("analysis run status does not match stage statuses")
        _validate_run_progress(self.progress, self.run_id, self.stages, self.status)

        if self.updated_at < self.created_at:
            raise ValueError("analysis run update timestamp cannot precede creation")
        if any(stage.updated_at > self.updated_at for stage in self.stages):
            raise ValueError("analysis run cannot predate a stage update")
        if self.started_at is not None:
            if self.started_at < self.created_at or self.started_at > self.updated_at:
                raise ValueError("analysis run start timestamp is outside its lifetime")
        if self.status is AnalysisRunStatus.QUEUED:
            if self.started_at is not None:
                raise ValueError("queued analysis run cannot have a start timestamp")
        elif self.started_at is None:
            raise ValueError("started, terminal analysis run requires a start timestamp")

        if self.status.terminal:
            if self.finished_at is None:
                raise ValueError("terminal analysis run requires a finish timestamp")
            baseline = self.started_at or self.created_at
            if self.finished_at < baseline or self.finished_at > self.updated_at:
                raise ValueError("analysis run finish timestamp is outside its lifetime")
        elif self.finished_at is not None:
            raise ValueError("non-terminal analysis run cannot have a finish timestamp")

        _validate_run_terminal_fact(self.status, self.failure, self.cancellation)
        _validate_run_evidence_and_confidence(
            source=self.source,
            stages=stage_by_id,
            evidence=self.evidence,
            confidence_assessments=self.confidence_assessments,
            updated_at=self.updated_at,
        )
        return self


def can_transition_stage_status(
    current: AnalysisStageStatus,
    target: AnalysisStageStatus,
) -> bool:
    """Return whether a stage state can move forward without resetting a run."""

    allowed: dict[AnalysisStageStatus, frozenset[AnalysisStageStatus]] = {
        AnalysisStageStatus.PENDING: frozenset(
            {
                AnalysisStageStatus.RUNNING,
                AnalysisStageStatus.SKIPPED,
                AnalysisStageStatus.FAILED,
                AnalysisStageStatus.CANCELLED,
            }
        ),
        AnalysisStageStatus.RUNNING: frozenset(
            {
                AnalysisStageStatus.RUNNING,
                AnalysisStageStatus.SUCCEEDED,
                AnalysisStageStatus.FAILED,
                AnalysisStageStatus.CANCELLED,
            }
        ),
        AnalysisStageStatus.SUCCEEDED: frozenset(),
        AnalysisStageStatus.FAILED: frozenset(),
        AnalysisStageStatus.CANCELLED: frozenset(),
        AnalysisStageStatus.SKIPPED: frozenset(),
    }
    return target in allowed[current]


def derive_run_status(
    stages: Sequence[AnalysisStage | AnalysisStageProgress],
) -> AnalysisRunStatus:
    """Derive one terminal-safe run state using deterministic precedence.

    Failure wins over cancellation because a concrete operational fault must not
    be hidden by a concurrently requested stop.  Cancellation wins over an
    otherwise incomplete plan.  A run succeeds only if every stage is successful
    or deliberately skipped.
    """

    if not stages:
        raise ValueError("analysis run requires at least one stage")
    statuses = tuple(stage.status for stage in stages)
    if AnalysisStageStatus.FAILED in statuses:
        return AnalysisRunStatus.FAILED
    if AnalysisStageStatus.CANCELLED in statuses:
        return AnalysisRunStatus.CANCELLED
    if all(
        status in {AnalysisStageStatus.SUCCEEDED, AnalysisStageStatus.SKIPPED}
        for status in statuses
    ):
        return AnalysisRunStatus.SUCCEEDED
    if all(status is AnalysisStageStatus.PENDING for status in statuses):
        return AnalysisRunStatus.QUEUED
    return AnalysisRunStatus.RUNNING


def _validate_local_artifact_path(value: str) -> None:
    """Reject absolute, URI, Windows-drive, and traversal locations."""

    if "\\" in value or ":" in value or "://" in value:
        raise ValueError("artifact paths must be local project-relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact paths must not be absolute or traverse outside the project")


def _validate_stage_graph(stages: Sequence[AnalysisStagePlan]) -> None:
    stage_ids = tuple(stage.stage_id for stage in stages)
    require_unique(stage_ids, field_name="analysis stage_ids")
    known_ids = set(stage_ids)
    earlier_ids: set[str] = set()
    for stage in stages:
        unknown_dependencies = set(stage.dependency_stage_ids) - known_ids
        if unknown_dependencies:
            joined = ", ".join(sorted(unknown_dependencies))
            raise ValueError(f"stage {stage.stage_id} has unknown dependencies: {joined}")
        later_dependencies = set(stage.dependency_stage_ids) - earlier_ids
        if later_dependencies:
            joined = ", ".join(sorted(later_dependencies))
            raise ValueError(
                f"stage {stage.stage_id} dependencies must appear earlier in the immutable plan: {joined}"
            )
        earlier_ids.add(stage.stage_id)


def _validate_stage_dependencies_satisfied(stage_by_id: dict[str, AnalysisStage]) -> None:
    completed_statuses = {AnalysisStageStatus.SUCCEEDED, AnalysisStageStatus.SKIPPED}
    for stage in stage_by_id.values():
        if stage.status not in {AnalysisStageStatus.RUNNING, AnalysisStageStatus.SUCCEEDED}:
            continue
        unresolved = tuple(
            dependency_id
            for dependency_id in stage.dependency_stage_ids
            if stage_by_id[dependency_id].status not in completed_statuses
        )
        if unresolved:
            joined = ", ".join(unresolved)
            raise ValueError(
                f"active or successful stage {stage.stage_id} has unresolved dependencies: {joined}"
            )


def _validate_run_progress(
    progress: AnalysisProgress,
    run_id: str,
    stages: tuple[AnalysisStage, ...],
    status: AnalysisRunStatus,
) -> None:
    if progress.run_id != run_id:
        raise ValueError("analysis progress run id does not match its analysis run")
    if progress.status is not status:
        raise ValueError("analysis progress status does not match its analysis run")
    stage_progress_by_id = {item.stage_id: item for item in progress.stages}
    stage_by_id = {stage.stage_id: stage for stage in stages}
    if stage_progress_by_id.keys() != stage_by_id.keys():
        raise ValueError("analysis progress stages do not match analysis run stages")
    for stage_id, stage in stage_by_id.items():
        snapshot = stage_progress_by_id[stage_id]
        if (
            snapshot.status is not stage.status
            or snapshot.completed_units != stage.completed_units
            or snapshot.total_units != stage.total_units
            or snapshot.progress_basis_points != stage.progress_basis_points
        ):
            raise ValueError(f"analysis progress stage snapshot diverges for {stage_id}")
    expected_completed = sum(stage.weight_units * stage.progress_basis_points for stage in stages)
    expected_total = sum(stage.weight_units * BASIS_POINTS for stage in stages)
    if progress.completed_weighted_units != expected_completed:
        raise ValueError("analysis progress completed weighted units do not match stages")
    if progress.total_weighted_units != expected_total:
        raise ValueError("analysis progress total weighted units do not match stages")
    if progress.emitted_at > max(stage.updated_at for stage in stages):
        # A coordinator may publish after every stage event, never before the last observed event.
        raise ValueError("analysis progress cannot be emitted after its latest stage update")


def _validate_run_terminal_fact(
    status: AnalysisRunStatus,
    failure: AnalysisFailure | None,
    cancellation: AnalysisCancellation | None,
) -> None:
    if status is AnalysisRunStatus.FAILED:
        if failure is None or cancellation is not None:
            raise ValueError("failed analysis run requires exactly one structured failure")
    elif status is AnalysisRunStatus.CANCELLED:
        if cancellation is None or failure is not None:
            raise ValueError("cancelled analysis run requires exactly one cancellation fact")
    elif failure is not None or cancellation is not None:
        raise ValueError("only failed or cancelled analysis runs may carry terminal facts")


def _validate_run_evidence_and_confidence(
    *,
    source: LocalAnalysisSource,
    stages: dict[str, AnalysisStage],
    evidence: tuple[AnalysisEvidence, ...],
    confidence_assessments: tuple[ConfidenceAssessment, ...],
    updated_at: datetime,
) -> None:
    require_unique(tuple(item.evidence_id for item in evidence), field_name="analysis evidence_ids")
    evidence_by_id = {item.evidence_id: item for item in evidence}
    for item in evidence:
        if item.stage_id not in stages:
            raise ValueError(f"evidence {item.evidence_id} references an unknown stage")
        if item.source_sha256 != source.source_sha256:
            raise ValueError("evidence source hash does not match analysis run source")
        if item.observed_at > updated_at:
            raise ValueError("evidence cannot be observed after analysis run update")
    for stage in stages.values():
        if any(evidence_id not in evidence_by_id for evidence_id in stage.evidence_ids):
            raise ValueError(f"stage {stage.stage_id} references missing evidence")
        stage_evidence_ids = {
            item.evidence_id for item in evidence if item.stage_id == stage.stage_id
        }
        if stage_evidence_ids != set(stage.evidence_ids):
            raise ValueError(f"stage {stage.stage_id} evidence references are not bidirectional")

    require_unique(
        tuple(item.assessment_id for item in confidence_assessments),
        field_name="confidence assessment_ids",
    )
    for assessment in confidence_assessments:
        if assessment.stage_id not in stages:
            raise ValueError(f"confidence {assessment.assessment_id} references an unknown stage")
        if assessment.source_sha256 != source.source_sha256:
            raise ValueError("confidence source hash does not match analysis run source")
        if assessment.assessed_at > updated_at:
            raise ValueError("confidence cannot be assessed after analysis run update")
        if any(evidence_id not in evidence_by_id for evidence_id in assessment.evidence_ids):
            raise ValueError(f"confidence {assessment.assessment_id} references missing evidence")
        if any(
            evidence_by_id[evidence_id].stage_id != assessment.stage_id
            for evidence_id in assessment.evidence_ids
        ):
            raise ValueError("confidence evidence must be emitted by the same analysis stage")


__all__ = [
    "BASIS_POINTS",
    "AnalysisCancellation",
    "AnalysisCancellationReason",
    "AnalysisEvidence",
    "AnalysisExecutionMode",
    "AnalysisFailure",
    "AnalysisFailureCode",
    "AnalysisMeasurement",
    "AnalysisModel",
    "AnalysisProgress",
    "AnalysisRun",
    "AnalysisRunId",
    "AnalysisRunStatus",
    "AnalysisStage",
    "AnalysisStageKind",
    "AnalysisStagePlan",
    "AnalysisStageProgress",
    "AnalysisStageStatus",
    "ConfidenceAggregate",
    "ConfidenceAssessment",
    "ConfidenceMetric",
    "EvidenceKind",
    "LocalAnalysisSource",
    "LocalAnalyzerIdentity",
    "LocalArtifactPath",
    "SourceAnalysisRequest",
    "can_transition_stage_status",
    "derive_run_status",
]
