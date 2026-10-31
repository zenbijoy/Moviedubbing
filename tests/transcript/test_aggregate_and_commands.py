from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aidub.application.invalidation import ArtifactStage
from aidub.domain import LockedUtteranceField, UtteranceStatus
from aidub.transcript import (
    ApproveUtteranceCommand,
    AssignCharacterCommand,
    AssignSpeakerCommand,
    AutomatedAsrUpdateCommand,
    ChangeStatusCommand,
    EditTextCommand,
    LockedFieldViolation,
    LockFieldsCommand,
    Transcript,
    TranscriptCommandService,
    TranscriptInvariantViolation,
    TranscriptOperation,
    TranscriptRevisionConflict,
    UnlockFieldsCommand,
)

from .factories import MEDIA_ID, PROJECT_ID, time_range, transcript, utterance

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
EDITOR = "editor@example.test"


def test_transcript_rejects_wrong_scope_language_and_order() -> None:
    bengali = utterance()
    hindi = utterance("utt_line_002", language="hi-IN", source_text="मैं यहाँ हूँ")
    other_project = utterance("utt_line_003", project_id="prj_other_001")
    earlier = utterance(
        "utt_line_004",
        source_start=0,
        source_end=900,
        edit_start=0,
        edit_end=900,
    )

    with pytest.raises(ValidationError, match="source language"):
        transcript(bengali, hindi)
    with pytest.raises(ValidationError, match="transcript project"):
        transcript(bengali, other_project)
    with pytest.raises(ValidationError, match="ordered"):
        transcript(bengali, earlier)
    with pytest.raises(ValidationError, match="utterance_ids"):
        transcript(bengali, bengali)


def test_manual_bengali_text_edit_returns_new_snapshot_audit_and_scoped_root() -> None:
    source = transcript(utterance())
    service = TranscriptCommandService()

    result = service.edit_text(
        source,
        EditTextCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            source_text="আমি এখন ঢাকায় আছি",
        ),
    )

    assert source.revision == 0
    assert source.utterances[0].source_text == "আমি এখানে আছি"
    assert result.transcript.revision == 1
    assert result.transcript.utterances[0].revision == 1
    assert result.transcript.utterances[0].source_text == "আমি এখন ঢাকায় আছি"
    assert result.audit.operation is TranscriptOperation.EDIT_TEXT
    assert result.audit.affected_utterance_ids == ("utt_line_001",)
    assert result.invalidation_roots[0].stage is ArtifactStage.TRANSCRIPT
    assert result.invalidation_roots[0].key == (
        f"transcript:{PROJECT_ID}:{MEDIA_ID}:bn-bd:utt_line_001"
    )


def test_hindi_text_round_trips_without_normalization_or_loss() -> None:
    source = transcript(
        utterance(language="hi-IN", source_text="मैं यहाँ हूँ"),
        language="hi-IN",
    )
    text = "क्या तुम यहाँ ठीक हो?"

    result = TranscriptCommandService().edit_text(
        source,
        EditTextCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            source_text=text,
        ),
    )

    assert result.transcript.utterances[0].source_text == text
    serialized = result.transcript.model_dump_json()
    assert Transcript.model_validate_json(serialized) == result.transcript


def test_stale_command_is_rejected_as_an_optimistic_revision_conflict() -> None:
    service = TranscriptCommandService()
    source = transcript(utterance())
    first = service.edit_text(
        source,
        EditTextCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            source_text="প্রথম সম্পাদনা",
        ),
    )

    with pytest.raises(TranscriptRevisionConflict) as raised:
        service.edit_text(
            first.transcript,
            EditTextCommand(
                expected_revision=0,
                actor=EDITOR,
                occurred_at=NOW,
                utterance_id="utt_line_001",
                source_text="দ্বিতীয় সম্পাদনা",
            ),
        )

    assert raised.value.expected == 0
    assert raised.value.current == 1
    assert first.transcript.utterances[0].source_text == "প্রথম সম্পাদনা"


def test_manual_lock_blocks_automated_asr_overwrite_but_not_unlocked_confidence() -> None:
    service = TranscriptCommandService()
    source = transcript(utterance())
    locked = service.lock_fields(
        source,
        LockFieldsCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            fields=frozenset({LockedUtteranceField.SOURCE_TEXT}),
        ),
    )

    with pytest.raises(LockedFieldViolation, match="source_text"):
        service.apply_automated_asr_update(
            locked.transcript,
            AutomatedAsrUpdateCommand(
                expected_revision=1,
                actor="asr:local-model-v1",
                occurred_at=NOW,
                utterance_id="utt_line_001",
                source_text="যন্ত্রের প্রতিস্থাপন",
            ),
        )

    confidence = service.apply_automated_asr_update(
        locked.transcript,
        AutomatedAsrUpdateCommand(
            expected_revision=1,
            actor="asr:local-model-v1",
            occurred_at=NOW,
            utterance_id="utt_line_001",
            confidence=0.99,
        ),
    )
    assert confidence.transcript.utterances[0].source_text == "আমি এখানে আছি"
    assert confidence.transcript.utterances[0].confidence == 0.99
    assert confidence.audit.automated is True


def test_timing_lock_protects_words_and_ranges_until_explicit_unlock() -> None:
    service = TranscriptCommandService()
    locked = service.lock_fields(
        transcript(utterance()),
        LockFieldsCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            fields=frozenset({LockedUtteranceField.SOURCE_TIMING}),
        ),
    )
    with pytest.raises(LockedFieldViolation, match="source_timing"):
        service.apply_automated_asr_update(
            locked.transcript,
            AutomatedAsrUpdateCommand(
                expected_revision=1,
                actor="asr:provider",
                occurred_at=NOW,
                utterance_id="utt_line_001",
                source_range=time_range(1_000, 2_900),
            ),
        )

    unlocked = service.unlock_fields(
        locked.transcript,
        UnlockFieldsCommand(
            expected_revision=1,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            fields=frozenset({LockedUtteranceField.SOURCE_TIMING}),
        ),
    )
    assert unlocked.transcript.revision == 2
    assert unlocked.transcript.utterances[0].revision == 2
    assert not unlocked.invalidation_roots


def test_assignments_and_review_approval_increment_only_the_affected_line() -> None:
    service = TranscriptCommandService()
    second = utterance(
        "utt_line_002",
        source_start=3_000,
        source_end=4_000,
        edit_start=7_000,
        edit_end=8_000,
    )
    current = transcript(utterance(), second)

    assigned = service.assign_speaker(
        current,
        AssignSpeakerCommand(
            expected_revision=0,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            speaker_id="spk_actor_001",
        ),
    )
    assert assigned.transcript.utterances[0].revision == 1
    assert assigned.transcript.utterances[1].revision == 0
    assert assigned.invalidation_roots[0].stage is ArtifactStage.DIARIZATION

    characterized = service.assign_character(
        assigned.transcript,
        AssignCharacterCommand(
            expected_revision=1,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            character_id="char_hero_001",
        ),
    )
    review = service.change_status(
        characterized.transcript,
        ChangeStatusCommand(
            expected_revision=2,
            actor=EDITOR,
            occurred_at=NOW,
            utterance_id="utt_line_001",
            status=UtteranceStatus.REVIEW,
        ),
    )
    approved = service.approve(
        review.transcript,
        ApproveUtteranceCommand(
            expected_revision=3,
            actor="reviewer@example.test",
            occurred_at=NOW,
            utterance_id="utt_line_001",
        ),
    )

    assert approved.transcript.revision == 4
    assert approved.transcript.utterances[0].revision == 4
    assert approved.transcript.utterances[0].status is UtteranceStatus.APPROVED
    assert approved.audit.operation is TranscriptOperation.APPROVE
    assert not approved.invalidation_roots


def test_approval_requires_review_and_status_api_cannot_bypass_approval_audit() -> None:
    service = TranscriptCommandService()
    source = transcript(utterance())
    with pytest.raises(TranscriptInvariantViolation, match="in review"):
        service.approve(
            source,
            ApproveUtteranceCommand(
                expected_revision=0,
                actor=EDITOR,
                occurred_at=NOW,
                utterance_id="utt_line_001",
            ),
        )
    with pytest.raises(TranscriptInvariantViolation, match="approval command"):
        service.change_status(
            source,
            ChangeStatusCommand(
                expected_revision=0,
                actor=EDITOR,
                occurred_at=NOW,
                utterance_id="utt_line_001",
                status=UtteranceStatus.APPROVED,
            ),
        )
