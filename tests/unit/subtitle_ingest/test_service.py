from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidub.domain import RationalRate, RationalTime, RoundingMode, UtteranceStatus
from aidub.subtitle_ingest import (
    SourceSubtitleIngestionService,
    SubtitleIngestionConflictError,
    SubtitleIngestionError,
    SubtitleIngestionRequest,
    SubtitleSourceEncoding,
    SubtitleTimingConflictCode,
    UnsupportedSubtitleEncodingError,
)


def _request(**changes: object) -> SubtitleIngestionRequest:
    values: dict[str, object] = {
        "project_id": "prj_subtitle_demo",
        "media_asset_id": "med_subtitle_source",
        "source_language": "bn-BD",
    }
    values.update(changes)
    return SubtitleIngestionRequest.model_validate(values)


def _write(path: Path, source: str, *, bom: bool = False) -> None:
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + source.encode("utf-8"))


def test_ingest_converts_utf8_srt_to_deterministic_scoped_draft_candidates(tmp_path: Path) -> None:
    source = tmp_path / "bangla-source.srt"
    bangla = "\u09ac\u09be\u0982\u09b2\u09be \u09b8\u0982\u09b2\u09be\u09aa"
    second_line = "\u09a6\u09cd\u09ac\u09bf\u09a4\u09c0\u09af\u09bc \u09b2\u09be\u0987\u09a8"
    payload = "\n".join(
        (
            "1",
            "00:00:01,250 --> 00:00:03,500",
            bangla,
            "",
            "2",
            "00:00:04,000 --> 00:00:05,125",
            second_line,
            "",
        )
    )
    _write(source, payload)

    service = SourceSubtitleIngestionService()
    first = service.ingest(source, _request())
    second = service.ingest(source, _request())

    assert first.report.is_acceptable
    assert first.report.provenance.content_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first.report.provenance.byte_length == len(source.read_bytes())
    assert first.report.provenance.language == "bn-BD"
    assert first.report.provenance.encoding is SubtitleSourceEncoding.UTF8
    assert first.report.candidate_count == 2
    assert first.report.conflicts == ()
    assert [candidate.utterance.utterance_id for candidate in first.candidates] == [
        candidate.utterance.utterance_id for candidate in second.candidates
    ]

    first_candidate = first.candidates[0]
    assert first_candidate.source_text == bangla
    assert first_candidate.source_range.start.ticks == 1_250
    assert first_candidate.utterance.edit_range.end_exclusive.ticks == 3_500
    assert first_candidate.utterance.confidence == 0.0
    assert first_candidate.utterance.status is UtteranceStatus.DRAFT
    assert first_candidate.utterance.utterance_id.startswith("utt_")


def test_bom_is_recorded_and_source_content_change_gets_new_candidate_ids(tmp_path: Path) -> None:
    source = tmp_path / "source.srt"
    original = "1\n00:00:00,000 --> 00:00:02,000\nfirst\n"
    _write(source, original, bom=True)

    service = SourceSubtitleIngestionService()
    first = service.ingest(source, _request())
    _write(source, original.replace("first", "second"), bom=True)
    second = service.ingest(source, _request())

    assert first.report.provenance.encoding is SubtitleSourceEncoding.UTF8_BOM
    assert first.report.provenance.content_sha256 != second.report.provenance.content_sha256
    assert first.candidates[0].utterance.utterance_id != second.candidates[0].utterance.utterance_id


def test_language_is_explicit_and_invalid_encoding_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="source_language"):
        SubtitleIngestionRequest(
            project_id="prj_subtitle_demo",
            media_asset_id="med_subtitle_source",
        )

    source = tmp_path / "utf16.srt"
    source.write_bytes("1\n00:00:00,000 --> 00:00:01,000\nhello\n".encode("utf-16"))
    with pytest.raises(UnsupportedSubtitleEncodingError, match="UTF-8"):
        SourceSubtitleIngestionService().ingest(source, _request(source_language="hi-IN"))


def test_unsupported_extension_and_size_limit_fail_before_candidate_conversion(
    tmp_path: Path,
) -> None:
    unsupported = tmp_path / "source.ass"
    _write(unsupported, "[Script Info]\n")
    with pytest.raises(SubtitleIngestionError, match="unsupported subtitle extension"):
        SourceSubtitleIngestionService().ingest(unsupported, _request())

    oversized = tmp_path / "large.srt"
    _write(oversized, "1\n00:00:00,000 --> 00:00:01,000\nlong text\n")
    with pytest.raises(SubtitleIngestionError, match="exceeds 4 bytes"):
        SourceSubtitleIngestionService().ingest(oversized, _request(maximum_bytes=4))


def test_overlap_is_a_visible_nonblocking_warning(tmp_path: Path) -> None:
    source = tmp_path / "overlap.srt"
    _write(
        source,
        "\n".join(
            (
                "1",
                "00:00:00,000 --> 00:00:03,000",
                "first",
                "",
                "2",
                "00:00:02,000 --> 00:00:04,000",
                "second",
                "",
            )
        ),
    )

    result = SourceSubtitleIngestionService().ingest(source, _request())

    assert result.report.is_acceptable
    assert len(result.candidates) == 2
    assert result.report.conflicts[0].code is SubtitleTimingConflictCode.OVERLAPPING_SOURCE_CUES
    assert result.report.conflicts[0].cue_number == 2
    assert result.report.conflicts[0].related_cue_number == 1


def test_outside_media_duration_is_reported_and_blocks_all_candidates(tmp_path: Path) -> None:
    source = tmp_path / "too-long.srt"
    _write(source, "1\n00:00:02,000 --> 00:00:04,000\nlate cue\n")

    result = SourceSubtitleIngestionService().ingest(
        source,
        _request(media_duration=RationalTime(ticks=3_000, rate=RationalRate(numerator=1_000))),
    )

    assert not result.report.is_acceptable
    assert result.candidates == ()
    assert result.report.candidate_count == 0
    assert [conflict.code for conflict in result.report.blocking_conflicts] == [
        SubtitleTimingConflictCode.OUTSIDE_MEDIA_DURATION
    ]
    with pytest.raises(SubtitleIngestionConflictError, match="outside_media_duration"):
        SourceSubtitleIngestionService.require_acceptable(result)


def test_nonexact_edit_time_requires_explicit_rounding_and_collapse_is_blocking(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fractional.srt"
    _write(source, "1\n00:00:00,001 --> 00:00:00,002\ntiny\n")

    service = SourceSubtitleIngestionService()
    missing_policy = service.ingest(source, _request(edit_rate=RationalRate(numerator=24)))
    collapsed = service.ingest(
        source,
        _request(
            edit_rate=RationalRate(numerator=24),
            edit_rounding=RoundingMode.NEAREST_EVEN,
        ),
    )

    assert [conflict.code for conflict in missing_policy.report.blocking_conflicts] == [
        SubtitleTimingConflictCode.EDIT_TIME_NOT_EXACT
    ]
    assert [conflict.code for conflict in collapsed.report.blocking_conflicts] == [
        SubtitleTimingConflictCode.EDIT_RANGE_COLLAPSED
    ]
    assert missing_policy.candidates == collapsed.candidates == ()


def test_explicit_rounding_can_map_a_nonexact_but_nonempty_edit_range(tmp_path: Path) -> None:
    source = tmp_path / "rounding.srt"
    _write(source, "1\n00:00:00,125 --> 00:00:00,250\nrounded\n")

    result = SourceSubtitleIngestionService().ingest(
        source,
        _request(
            edit_rate=RationalRate(numerator=24),
            edit_rounding=RoundingMode.NEAREST_EVEN,
        ),
    )

    assert result.report.is_acceptable
    assert result.candidates[0].utterance.edit_range.start.ticks == 3
    assert result.candidates[0].utterance.edit_range.end_exclusive.ticks == 6


def test_multiple_conflicts_are_sorted_deterministically_by_cue_and_code(tmp_path: Path) -> None:
    source = tmp_path / "combined.srt"
    _write(
        source,
        "\n".join(
            (
                "1",
                "00:00:00,000 --> 00:00:05,000",
                "first",
                "",
                "2",
                "00:00:02,000 --> 00:00:06,000",
                "second",
                "",
            )
        ),
    )

    result = SourceSubtitleIngestionService().ingest(
        source,
        _request(media_duration=RationalTime(ticks=3_000, rate=RationalRate(numerator=1_000))),
    )

    assert [(conflict.cue_number, conflict.code.value) for conflict in result.report.conflicts] == [
        (1, "outside_media_duration"),
        (2, "outside_media_duration"),
        (2, "overlapping_source_cues"),
    ]
