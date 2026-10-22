"""Bounded, deterministic conversion of source captions into transcript candidates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from aidub.domain import TimeRange, Utterance, UtteranceStatus
from aidub.subtitles import (
    SubtitleCodecError,
    SubtitleCue,
    SubtitleDocument,
    SubtitleFormat,
    parse_srt,
    parse_webvtt,
)

from .errors import (
    SubtitleIngestionConflictError,
    SubtitleIngestionError,
    UnsafeSubtitleSourceError,
    UnsupportedSubtitleEncodingError,
)
from .models import (
    SourceSubtitleProvenance,
    SubtitleIngestionReport,
    SubtitleIngestionRequest,
    SubtitleIngestionResult,
    SubtitleSourceEncoding,
    SubtitleTimingConflict,
    SubtitleTimingConflictCode,
    SubtitleTimingConflictSeverity,
    SubtitleUtteranceCandidate,
)

_UTF8_BOM = b"\xef\xbb\xbf"
_REPARSE_POINT_ATTRIBUTE = 0x0400


@dataclass(frozen=True, slots=True)
class _LoadedSubtitle:
    """Internal immutable source snapshot, read exactly once for parsing and hashing."""

    path: Path
    contents: str
    provenance: SourceSubtitleProvenance


@dataclass(frozen=True, slots=True)
class _MappedCue:
    """Internal cue after exact source-to-edit clock validation."""

    cue_number: int
    cue: SubtitleCue
    edit_range: TimeRange | None


class SourceSubtitleIngestionService:
    """Read a local UTF-8 caption source and create an all-or-nothing candidate set.

    The service is intentionally pure with respect to project state: it reads one source file but
    never writes, persists, invokes media tools, or uses a network/provider. A successful parse
    always returns a report. Call :meth:`require_acceptable` before committing its candidates.
    """

    def ingest(
        self,
        source: Path | str,
        request: SubtitleIngestionRequest,
    ) -> SubtitleIngestionResult:
        """Create deterministic draft utterance candidates from one caption file."""

        loaded = _load_source(source, request)
        document = _parse_document(loaded, request)
        conflicts, mapped_cues = _validate_timing(document, request)
        report = SubtitleIngestionReport(
            provenance=loaded.provenance,
            candidate_count=0,
            conflicts=tuple(conflicts),
        )
        if not report.is_acceptable:
            return SubtitleIngestionResult(report=report)

        candidates = tuple(
            _candidate(mapped, request, loaded.provenance.content_sha256)
            for mapped in mapped_cues
            if mapped.edit_range is not None
        )
        return SubtitleIngestionResult(
            report=SubtitleIngestionReport(
                provenance=loaded.provenance,
                candidate_count=len(candidates),
                conflicts=tuple(conflicts),
            ),
            candidates=candidates,
        )

    @staticmethod
    def require_acceptable(result: SubtitleIngestionResult) -> SubtitleIngestionResult:
        """Fail closed unless the caller has resolved every blocking timing conflict."""

        if not result.report.is_acceptable:
            raise SubtitleIngestionConflictError(result.report)
        return result


def ingest_source_subtitle(
    source: Path | str,
    request: SubtitleIngestionRequest,
) -> SubtitleIngestionResult:
    """Convenience entry point for the default deterministic ingestion service."""

    return SourceSubtitleIngestionService().ingest(source, request)


def _load_source(source: Path | str, request: SubtitleIngestionRequest) -> _LoadedSubtitle:
    original = Path(source).expanduser()
    if _is_link_or_reparse(original):
        raise UnsafeSubtitleSourceError(
            f"subtitle source cannot be a link/reparse point: {original}"
        )
    try:
        path = original.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise UnsafeSubtitleSourceError(
            f"subtitle source cannot be resolved: {original}"
        ) from error
    if not path.is_file():
        raise UnsafeSubtitleSourceError(f"subtitle source is not a regular file: {path}")

    try:
        with path.open("rb") as stream:
            payload = stream.read(request.maximum_bytes + 1)
    except OSError as error:
        raise UnsafeSubtitleSourceError(f"subtitle source cannot be read: {path}") from error
    if len(payload) > request.maximum_bytes:
        raise SubtitleIngestionError(
            f"subtitle source exceeds {request.maximum_bytes} bytes: {path.name}"
        )

    encoding = (
        SubtitleSourceEncoding.UTF8_BOM
        if payload.startswith(_UTF8_BOM)
        else SubtitleSourceEncoding.UTF8
    )
    try:
        contents = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnsupportedSubtitleEncodingError(
            "subtitle source must be valid UTF-8 or UTF-8 with a BOM"
        ) from error

    subtitle_format = _format_from_path(path)
    provenance = SourceSubtitleProvenance(
        display_name=path.name,
        format=subtitle_format,
        encoding=encoding,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        language=request.source_language,
    )
    return _LoadedSubtitle(path=path, contents=contents, provenance=provenance)


def _is_link_or_reparse(path: Path) -> bool:
    """Reject links before resolving an untrusted file name on all supported hosts."""

    try:
        stat_result = path.lstat()
    except OSError:
        return False
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def _format_from_path(path: Path) -> SubtitleFormat:
    suffix = path.suffix.casefold()
    if suffix == ".srt":
        return SubtitleFormat.SRT
    if suffix in {".vtt", ".webvtt"}:
        return SubtitleFormat.WEBVTT
    raise SubtitleIngestionError(f"unsupported subtitle extension: {path.suffix}")


def _parse_document(
    loaded: _LoadedSubtitle,
    request: SubtitleIngestionRequest,
) -> SubtitleDocument:
    try:
        if loaded.provenance.format is SubtitleFormat.SRT:
            return parse_srt(
                loaded.contents,
                language=request.source_language,
                maximum_cues=request.maximum_cues,
                maximum_text_characters=request.maximum_text_characters,
            )
        return parse_webvtt(
            loaded.contents,
            language=request.source_language,
            maximum_cues=request.maximum_cues,
            maximum_text_characters=request.maximum_text_characters,
        )
    except SubtitleCodecError as error:
        raise SubtitleIngestionError(
            f"invalid {loaded.provenance.format.value} subtitle: {error}"
        ) from error


def _validate_timing(
    document: SubtitleDocument,
    request: SubtitleIngestionRequest,
) -> tuple[list[SubtitleTimingConflict], tuple[_MappedCue, ...]]:
    """Validate all cues first so any blocking issue prevents partial candidate use."""

    conflicts: list[SubtitleTimingConflict] = []
    mapped: list[_MappedCue] = []
    furthest_active_cue: tuple[int, SubtitleCue] | None = None

    for cue_number, cue in enumerate(document.cues, start=1):
        source_range = cue.time_range
        if (
            furthest_active_cue is not None
            and source_range.start < furthest_active_cue[1].time_range.end_exclusive
        ):
            conflicts.append(
                SubtitleTimingConflict(
                    code=SubtitleTimingConflictCode.OVERLAPPING_SOURCE_CUES,
                    severity=SubtitleTimingConflictSeverity.WARNING,
                    cue_number=cue_number,
                    source_range=source_range,
                    related_cue_number=furthest_active_cue[0],
                )
            )
        if (
            furthest_active_cue is None
            or furthest_active_cue[1].time_range.end_exclusive < source_range.end_exclusive
        ):
            furthest_active_cue = (cue_number, cue)

        if (
            request.media_duration is not None
            and source_range.end_exclusive > request.media_duration
        ):
            conflicts.append(
                SubtitleTimingConflict(
                    code=SubtitleTimingConflictCode.OUTSIDE_MEDIA_DURATION,
                    severity=SubtitleTimingConflictSeverity.ERROR,
                    cue_number=cue_number,
                    source_range=source_range,
                )
            )

        edit_range: TimeRange | None
        try:
            edit_range = source_range.rescaled_to(
                request.edit_rate,
                rounding=request.edit_rounding,
            )
        except ValueError:
            edit_range = None
            conflicts.append(
                SubtitleTimingConflict(
                    code=SubtitleTimingConflictCode.EDIT_TIME_NOT_EXACT,
                    severity=SubtitleTimingConflictSeverity.ERROR,
                    cue_number=cue_number,
                    source_range=source_range,
                )
            )
        else:
            if edit_range.is_empty:
                edit_range = None
                conflicts.append(
                    SubtitleTimingConflict(
                        code=SubtitleTimingConflictCode.EDIT_RANGE_COLLAPSED,
                        severity=SubtitleTimingConflictSeverity.ERROR,
                        cue_number=cue_number,
                        source_range=source_range,
                    )
                )
        mapped.append(_MappedCue(cue_number=cue_number, cue=cue, edit_range=edit_range))

    conflicts.sort(
        key=lambda conflict: (
            conflict.cue_number,
            conflict.related_cue_number or 0,
            conflict.code.value,
        )
    )
    return conflicts, tuple(mapped)


def _candidate(
    mapped: _MappedCue,
    request: SubtitleIngestionRequest,
    source_sha256: str,
) -> SubtitleUtteranceCandidate:
    """Build one provider-neutral candidate after the full input passed validation."""

    if mapped.edit_range is None:
        raise AssertionError("a blocked subtitle cue cannot become a candidate")
    source_text_hash = hashlib.sha256(mapped.cue.text.encode("utf-8")).hexdigest()
    utterance_id = _utterance_id(
        project_id=request.project_id,
        media_asset_id=request.media_asset_id,
        source_sha256=source_sha256,
        cue_number=mapped.cue_number,
    )
    utterance = Utterance(
        utterance_id=utterance_id,
        project_id=request.project_id,
        source_range=mapped.cue.time_range,
        edit_range=mapped.edit_range,
        source_text=mapped.cue.text,
        source_language=request.source_language,
        confidence=0.0,
        status=UtteranceStatus.DRAFT,
    )
    return SubtitleUtteranceCandidate(
        cue_number=mapped.cue_number,
        cue_identifier=mapped.cue.cue_id,
        cue_settings=mapped.cue.settings,
        source_range=mapped.cue.time_range,
        source_text=mapped.cue.text,
        source_text_sha256=source_text_hash,
        utterance=utterance,
    )


def _utterance_id(
    *,
    project_id: str,
    media_asset_id: str,
    source_sha256: str,
    cue_number: int,
) -> str:
    """Derive a stable scoped identifier without random IDs or file paths."""

    digest = hashlib.sha256()
    digest.update(b"aidub-source-subtitle-candidate-v1\0")
    for value in (project_id, media_asset_id, source_sha256):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    digest.update(cue_number.to_bytes(8, "big", signed=False))
    return f"utt_{digest.hexdigest()[:32]}"


__all__ = ["SourceSubtitleIngestionService", "ingest_source_subtitle"]
