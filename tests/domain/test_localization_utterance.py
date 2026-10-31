from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aidub.domain.localization import (
    Localization,
    TranslationOrigin,
    TranslationStatus,
    TranslationVersion,
)
from aidub.domain.time import RationalRate, RationalTime, TimeRange
from aidub.domain.utterance import (
    FaceVisibility,
    FaceVisibilityPriority,
    LockedUtteranceField,
    Utterance,
    UtteranceStatus,
    WordTiming,
)

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)
RATE = RationalRate(numerator=1_000)
HASH = "1" * 64


def tr(start: int, end: int) -> TimeRange:
    return TimeRange.from_start_end(
        RationalTime(ticks=start, rate=RATE),
        RationalTime(ticks=end, rate=RATE),
    )


def utterance(**updates: object) -> Utterance:
    values: dict[str, object] = {
        "utterance_id": "utt_line_001",
        "project_id": "prj_feature_film",
        "scene_id": "scn_opening_01",
        "speaker_id": "spk_actor_001",
        "character_id": "char_tony_01",
        "source_range": tr(1_000, 3_500),
        "edit_range": tr(5_000, 7_500),
        "source_text": "What are you doing here?",
        "source_language": "en-US",
        "confidence": 0.97,
        "words": (
            WordTiming(text="What", source_range=tr(1_000, 1_300), confidence=0.99),
            WordTiming(text="are", source_range=tr(1_350, 1_600), confidence=0.98),
            WordTiming(text="you", source_range=tr(1_650, 1_900), confidence=0.98),
            WordTiming(text="doing", source_range=tr(1_950, 2_400), confidence=0.96),
            WordTiming(text="here", source_range=tr(2_450, 3_100), confidence=0.97),
        ),
    }
    values.update(updates)
    return Utterance.model_validate(values)


def test_localization_is_a_distinct_language_branch() -> None:
    localization = Localization(
        localization_id="loc_bengali_bd",
        project_id="prj_feature_film",
        source_language="en-US",
        target_language="bn-BD",
        display_name="Bengali (Bangladesh)",
        created_at=NOW,
        updated_at=NOW,
    )

    assert localization.target_language == "bn-BD"

    with pytest.raises(ValidationError, match="must differ"):
        Localization(
            localization_id="loc_english_us",
            project_id="prj_feature_film",
            source_language="en-US",
            target_language="EN-us",
            display_name="English",
            created_at=NOW,
            updated_at=NOW,
        )


def test_provider_translation_requires_complete_provenance() -> None:
    base = {
        "translation_version_id": "trn_bengali_v01",
        "utterance_id": "utt_line_001",
        "localization_id": "loc_bengali_bd",
        "version": 1,
        "source_utterance_sha256": HASH,
        "target_text": "তুমি এখানে কী করছ?",
        "origin": TranslationOrigin.PROVIDER,
        "created_by": "translator@example.test",
        "created_at": NOW,
    }

    with pytest.raises(ValidationError, match="provider, model, and prompt"):
        TranslationVersion.model_validate(base)

    version = TranslationVersion.model_validate(
        {
            **base,
            "provider_id": "openai",
            "model_id": "translation-model",
            "prompt_version": "duration-aware-2.1",
        }
    )
    assert version.status is TranslationStatus.DRAFT


def test_approved_translation_requires_a_chronological_approval() -> None:
    values = {
        "translation_version_id": "trn_bengali_v01",
        "utterance_id": "utt_line_001",
        "localization_id": "loc_bengali_bd",
        "version": 1,
        "source_utterance_sha256": HASH,
        "target_text": "তুমি এখানে কী করছ?",
        "origin": TranslationOrigin.HUMAN,
        "status": TranslationStatus.APPROVED,
        "created_by": "translator@example.test",
        "created_at": NOW,
    }

    with pytest.raises(ValidationError, match="requires approver"):
        TranslationVersion.model_validate(values)
    with pytest.raises(ValidationError, match="before creation"):
        TranslationVersion.model_validate(
            {
                **values,
                "approved_by": "editor@example.test",
                "approved_at": NOW - timedelta(seconds=1),
            }
        )


def test_utterance_accepts_ordered_words_within_source_boundaries() -> None:
    line = utterance()

    assert len(line.words) == 5
    assert line.source_range.contains_range(line.words[-1].source_range)


def test_utterance_rejects_word_outside_or_overlapping_previous_word() -> None:
    outside = WordTiming(text="Outside", source_range=tr(3_400, 3_600), confidence=0.5)
    with pytest.raises(ValidationError, match="outside"):
        utterance(words=(outside,))

    first = WordTiming(text="One", source_range=tr(1_000, 1_500), confidence=0.9)
    overlap = WordTiming(text="Two", source_range=tr(1_400, 1_800), confidence=0.9)
    with pytest.raises(ValidationError, match="non-overlapping"):
        utterance(words=(first, overlap))


def test_locked_utterance_identifies_what_is_locked() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        utterance(status=UtteranceStatus.LOCKED, locked_fields=frozenset())

    line = utterance(
        status=UtteranceStatus.LOCKED,
        locked_fields=frozenset(
            {LockedUtteranceField.SOURCE_TEXT, LockedUtteranceField.SOURCE_TIMING}
        ),
    )
    assert LockedUtteranceField.SOURCE_TEXT in line.locked_fields


def test_face_priority_cannot_exist_without_a_tracked_face() -> None:
    with pytest.raises(ValidationError, match="active face"):
        FaceVisibility(priority=FaceVisibilityPriority.HIGH)

    visible = FaceVisibility(
        active_face_id="face_0007",
        priority=FaceVisibilityPriority.HIGH,
        confidence=0.92,
    )
    assert visible.confidence == 0.92
