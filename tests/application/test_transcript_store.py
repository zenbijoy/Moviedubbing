from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aidub.application import DurableTranscriptService
from aidub.domain import (
    ProjectId,
    RationalRate,
    RationalTime,
    TimeRange,
    Utterance,
    UtteranceStatus,
)
from aidub.infrastructure.persistence import ProjectDatabase, ProjectRecord
from aidub.infrastructure.transcripts import (
    StoredTranscriptRevisionConflict,
    TranscriptAlreadyExistsError,
    TranscriptStore,
)
from aidub.transcript import EditTextCommand, Transcript, TranscriptCommandService


def _range(start: int, end: int) -> TimeRange:
    rate = RationalRate(numerator=24_000, denominator=1_001)
    return TimeRange.from_start_end(
        RationalTime(ticks=start, rate=rate), RationalTime(ticks=end, rate=rate)
    )


def _transcript() -> Transcript:
    return Transcript(
        project_id=ProjectId("prj_transcript"),
        media_asset_id="med_source",
        language="en-US",
        utterances=(
            Utterance(
                utterance_id="utt_line_one",
                project_id="prj_transcript",
                source_range=_range(0, 48),
                edit_range=_range(0, 48),
                source_text="Original line.",
                source_language="en-US",
                confidence=0.9,
                status=UtteranceStatus.DRAFT,
            ),
        ),
    )


@pytest.fixture
def store(tmp_path: Path) -> TranscriptStore:
    database = ProjectDatabase(tmp_path / "Movie.aidub" / "project.db")
    database.initialize()
    database.create_project(ProjectRecord(id="prj_transcript", name="Transcript Test"))
    return TranscriptStore(database)


def test_create_load_commit_and_history_are_revision_safe(store: TranscriptStore) -> None:
    initial = _transcript()
    assert store.create(initial) == initial
    assert (
        store.require(project_id="prj_transcript", media_asset_id="med_source", language="en-us")
        == initial
    )

    service = TranscriptCommandService()
    result = service.edit_text(
        initial,
        EditTextCommand(
            expected_revision=0,
            actor="editor",
            occurred_at=datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
            utterance_id="utt_line_one",
            source_text="Corrected line.",
        ),
    )
    committed = store.commit(result)

    loaded = store.require(
        project_id="prj_transcript", media_asset_id="med_source", language="en-US"
    )
    assert loaded == committed.transcript
    history = store.history(
        project_id="prj_transcript", media_asset_id="med_source", language="en-US"
    )
    assert len(history) == 1
    assert history[0].audit == result.audit
    assert len(history[0].transcript_sha256) == 64
    assert history[0].invalidation_roots == result.invalidation_roots


def test_duplicate_create_and_stale_commit_fail_without_overwrite(store: TranscriptStore) -> None:
    initial = _transcript()
    store.create(initial)
    with pytest.raises(TranscriptAlreadyExistsError):
        store.create(initial)

    service = TranscriptCommandService()
    first = service.edit_text(
        initial,
        EditTextCommand(
            expected_revision=0,
            actor="editor-a",
            occurred_at=datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
            utterance_id="utt_line_one",
            source_text="First correction.",
        ),
    )
    stale = service.edit_text(
        initial,
        EditTextCommand(
            expected_revision=0,
            actor="editor-b",
            occurred_at=datetime(2026, 8, 14, 12, 1, tzinfo=UTC),
            utterance_id="utt_line_one",
            source_text="Stale correction.",
        ),
    )
    store.commit(first)
    with pytest.raises(StoredTranscriptRevisionConflict, match="expected 0, stored 1"):
        store.commit(stale)
    loaded = store.require(
        project_id="prj_transcript", media_asset_id="med_source", language="en-US"
    )
    assert loaded.utterances[0].source_text == "First correction."


def test_application_service_dispatches_command_and_persists_it(store: TranscriptStore) -> None:
    application = DurableTranscriptService(store)
    application.create(_transcript())

    result = application.apply(
        project_id="prj_transcript",
        media_asset_id="med_source",
        language="en-US",
        command=EditTextCommand(
            expected_revision=0,
            actor="editor",
            occurred_at=datetime(2026, 8, 14, 12, 2, tzinfo=UTC),
            utterance_id="utt_line_one",
            source_text="Persisted through application service.",
        ),
    )

    assert result.transcript.revision == 1
    assert (
        application.get(project_id="prj_transcript", media_asset_id="med_source", language="en-US")
        == result.transcript
    )
