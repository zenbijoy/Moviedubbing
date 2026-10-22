"""Immutable localization-translation snapshots and their auditable effects."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from aidub.application.invalidation import ArtifactStage
from aidub.domain import (
    Localization,
    LocalizationId,
    ProjectId,
    TranslationOrigin,
    TranslationStatus,
    TranslationVersion,
    TranslationVersionId,
    TranslationWarning,
    UtteranceId,
)
from aidub.domain.base import DomainModel, UtcDatetime
from aidub.domain.types import LanguageTag, NonEmptyStr, Sha256, require_unique


class TranslationStalenessReason(StrEnum):
    """A versioned dependency that no longer matches an active translation."""

    SOURCE_CHANGED = "source_changed"
    GLOSSARY_CHANGED = "glossary_changed"
    TRANSLATION_MEMORY_CHANGED = "translation_memory_changed"


class TranslationRecord(DomainModel):
    """One immutable translation revision plus provider-boundary evidence.

    ``TranslationVersion`` intentionally owns the human-facing content and status.
    This wrapper retains versioned source/TM dependencies and opaque request/response
    hashes without storing provider payloads or credentials in project state.
    """

    translation: TranslationVersion
    source_revision: int = Field(ge=0)
    translation_memory_version: int = Field(default=0, ge=0)
    provider_request_id: NonEmptyStr | None = None
    provider_request_hash: Sha256 | None = None
    provider_response_hash: Sha256 | None = None
    provider_latency_ms: int | None = Field(default=None, ge=0)
    provider_retry_count: int | None = Field(default=None, ge=0)
    provider_degraded: bool = False

    @model_validator(mode="after")
    def _validate_provider_evidence(self) -> Self:
        evidence = (
            self.provider_request_id,
            self.provider_request_hash,
            self.provider_response_hash,
            self.provider_latency_ms,
            self.provider_retry_count,
        )
        if self.translation.origin is TranslationOrigin.PROVIDER:
            if any(value is None for value in evidence):
                raise ValueError("provider translations require complete provider evidence")
        elif any(value is not None for value in evidence) or self.provider_degraded:
            raise ValueError("only provider translations may carry provider evidence")
        return self


class TranslationUnit(DomainModel):
    """All immutable translation revisions for one source utterance."""

    utterance_id: UtteranceId
    source_text_sha256: Sha256
    source_revision: int = Field(ge=0)
    records: tuple[TranslationRecord, ...] = ()
    active_translation_version_id: TranslationVersionId | None = None
    stale_reasons: frozenset[TranslationStalenessReason] = frozenset()

    @model_validator(mode="after")
    def _validate_history(self) -> Self:
        translation_ids = tuple(
            record.translation.translation_version_id for record in self.records
        )
        require_unique(translation_ids, field_name="translation_version_ids")
        versions = tuple(record.translation.version for record in self.records)
        if versions != tuple(range(1, len(self.records) + 1)):
            raise ValueError(
                "translation record versions must be a contiguous sequence starting at one"
            )
        for record in self.records:
            if record.translation.utterance_id != self.utterance_id:
                raise ValueError("translation record utterance does not match its translation unit")
        if self.active_translation_version_id is not None and (
            self.active_translation_version_id not in translation_ids
        ):
            raise ValueError("active translation version must exist in the unit history")
        if self.active_translation_version_id is None and self.stale_reasons:
            raise ValueError("a unit without an active translation cannot be stale")
        return self

    @property
    def active_record(self) -> TranslationRecord | None:
        """Return the selected immutable revision, if one is selected."""

        return next(
            (
                record
                for record in self.records
                if record.translation.translation_version_id == self.active_translation_version_id
            ),
            None,
        )

    @property
    def effective_status(self) -> TranslationStatus | None:
        """Expose derived staleness without mutating historical revisions."""

        record = self.active_record
        if record is None:
            return None
        if self.stale_reasons:
            return TranslationStatus.STALE
        return record.translation.status


class TranslationProviderResult(DomainModel):
    """Provider output accepted by the strict validation boundary.

    The workflow intentionally accepts this typed result, never a raw SDK object or
    ``ProviderResponse``. That makes it impossible for a command path to bypass
    response-schema, scope, and privacy checks accidentally.
    """

    request_id: NonEmptyStr
    request_hash: Sha256
    response_hash: Sha256
    provider_id: NonEmptyStr
    model_id: NonEmptyStr
    prompt_id: NonEmptyStr
    prompt_version: NonEmptyStr
    project_id: ProjectId
    localization_id: LocalizationId
    utterance_id: UtteranceId
    source_language: LanguageTag
    target_language: LanguageTag
    source_text_sha256: Sha256
    source_revision: int = Field(ge=0)
    glossary_version: int = Field(ge=0)
    translation_memory_version: int = Field(ge=0)
    target_text: NonEmptyStr
    estimated_duration_ms: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    warnings: tuple[TranslationWarning, ...] = ()
    received_at: UtcDatetime
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    degraded: bool = False

    @model_validator(mode="after")
    def _validate_languages(self) -> Self:
        if self.source_language.casefold() == self.target_language.casefold():
            raise ValueError("provider result target language must differ from source language")
        return self


class TranslationAggregate(DomainModel):
    """A versioned target-language branch over source utterance facts."""

    localization: Localization
    revision: int = Field(default=0, ge=0)
    units: tuple[TranslationUnit, ...] = ()

    @model_validator(mode="after")
    def _validate_units(self) -> Self:
        require_unique(tuple(unit.utterance_id for unit in self.units), field_name="utterance_ids")
        for unit in self.units:
            for record in unit.records:
                if record.translation.localization_id != self.localization.localization_id:
                    raise ValueError("translation record localization does not match aggregate")
            expected = translation_staleness_reasons(unit, self.localization)
            if unit.stale_reasons != expected:
                raise ValueError("translation unit staleness does not match current dependencies")
        return self

    @property
    def project_id(self) -> ProjectId:
        """Convenience access to the project scope owned by the localization."""

        return self.localization.project_id

    def index_of(self, utterance_id: str) -> int:
        """Return a unit index, or ``-1`` when the source utterance is absent."""

        return next(
            (index for index, unit in enumerate(self.units) if unit.utterance_id == utterance_id),
            -1,
        )


class TranslationOperation(StrEnum):
    SYNC_SOURCE = "sync_source"
    CREATE_DRAFT = "create_draft"
    APPLY_PROVIDER_RESULT = "apply_provider_result"
    SEND_TO_REVIEW = "send_to_review"
    APPROVE = "approve"
    REJECT = "reject"
    UPDATE_RESOURCES = "update_resources"


class TranslationAuditFact(DomainModel):
    """Persistable fact emitted for every accepted aggregate mutation."""

    operation: TranslationOperation
    actor: NonEmptyStr
    occurred_at: UtcDatetime
    expected_revision: int = Field(ge=0)
    new_revision: int = Field(ge=1)
    affected_utterance_ids: tuple[UtteranceId, ...] = ()
    affected_translation_version_ids: tuple[TranslationVersionId, ...] = ()
    staleness_reasons: tuple[TranslationStalenessReason, ...] = ()
    automated: bool = False

    @model_validator(mode="after")
    def _validate_revision_and_scope(self) -> Self:
        if self.new_revision != self.expected_revision + 1:
            raise ValueError("an audit fact must describe exactly one aggregate revision")
        require_unique(self.affected_utterance_ids, field_name="affected_utterance_ids")
        require_unique(
            self.affected_translation_version_ids,
            field_name="affected_translation_version_ids",
        )
        require_unique(self.staleness_reasons, field_name="staleness_reasons")
        return self


class TranslationInvalidationRoot(DomainModel):
    """Stable root for invalidating timing, voice, subtitle, QC, and export artifacts."""

    key: NonEmptyStr
    stage: ArtifactStage = ArtifactStage.TRANSLATION
    project_id: ProjectId
    localization_id: LocalizationId
    target_language: LanguageTag
    utterance_id: UtteranceId

    @model_validator(mode="after")
    def _validate_key(self) -> Self:
        if self.stage is not ArtifactStage.TRANSLATION:
            raise ValueError("translation invalidation roots must use the translation stage")
        expected = translation_invalidation_key(
            project_id=self.project_id,
            localization_id=self.localization_id,
            target_language=self.target_language,
            utterance_id=self.utterance_id,
        )
        if self.key != expected:
            raise ValueError("invalidation key does not match its typed translation scope")
        return self


class TranslationMutationResult(DomainModel):
    """A new aggregate snapshot plus the facts consumers must persist or invalidate."""

    aggregate: TranslationAggregate
    audit: TranslationAuditFact
    invalidation_roots: tuple[TranslationInvalidationRoot, ...] = ()


def translation_staleness_reasons(
    unit: TranslationUnit,
    localization: Localization,
) -> frozenset[TranslationStalenessReason]:
    """Calculate staleness from versioned dependencies without changing history."""

    active = unit.active_record
    if active is None:
        return frozenset()

    reasons: set[TranslationStalenessReason] = set()
    translation = active.translation
    if (
        translation.source_utterance_sha256 != unit.source_text_sha256
        or active.source_revision != unit.source_revision
    ):
        reasons.add(TranslationStalenessReason.SOURCE_CHANGED)
    if translation.glossary_version != localization.glossary_version:
        reasons.add(TranslationStalenessReason.GLOSSARY_CHANGED)
    if active.translation_memory_version != localization.translation_memory_version:
        reasons.add(TranslationStalenessReason.TRANSLATION_MEMORY_CHANGED)
    return frozenset(reasons)


def translation_invalidation_key(
    *,
    project_id: str,
    localization_id: str,
    target_language: str,
    utterance_id: str,
) -> str:
    """Build a stable, locale-independent translation dependency key."""

    return ":".join(
        (
            ArtifactStage.TRANSLATION.value,
            project_id,
            localization_id,
            target_language.casefold(),
            utterance_id,
        )
    )


__all__ = [
    "TranslationAggregate",
    "TranslationAuditFact",
    "TranslationInvalidationRoot",
    "TranslationMutationResult",
    "TranslationOperation",
    "TranslationProviderResult",
    "TranslationRecord",
    "TranslationStalenessReason",
    "TranslationUnit",
    "translation_invalidation_key",
    "translation_staleness_reasons",
]
