"""
Unit tests for VoiceClassifier and CharacterRegistry services.
"""

from __future__ import annotations

import pytest

from aidub.application.voice.character_registry import CharacterRegistry
from aidub.application.voice.voice_classifier import VoiceClassifier
from aidub.domain.voice_classification import GenderIdentity


def test_voice_classifier_uncertainty_and_override() -> None:
    classifier = VoiceClassifier(confidence_threshold=0.75)

    # Register high-confidence prediction
    c1 = classifier.register_cue_prediction("cue_1", "SPEAKER_00", confidence=0.92)
    assert not c1.is_uncertain
    assert c1.effective_speaker == "SPEAKER_00"

    # Register low-confidence prediction (< 0.75)
    c2 = classifier.register_cue_prediction("cue_2", "SPEAKER_01", confidence=0.64)
    assert c2.is_uncertain

    uncertain_list = classifier.get_uncertain_cues()
    assert len(uncertain_list) == 1
    assert uncertain_list[0].cue_id == "cue_2"

    # Manually override c2
    overridden = classifier.override_speaker("cue_2", "Hero", reason="Visual confirmation on face")
    assert overridden.effective_speaker == "Hero"
    assert not overridden.is_uncertain
    assert overridden.override_reason == "Visual confirmation on face"


def test_voice_classifier_cluster_merge() -> None:
    classifier = VoiceClassifier()

    classifier.register_cue_prediction("cue_10", "SPEAKER_00", confidence=0.88)
    classifier.register_cue_prediction("cue_11", "SPEAKER_02", confidence=0.85)
    classifier.register_cue_prediction("cue_12", "SPEAKER_02", confidence=0.78)

    # Merge duplicate cluster SPEAKER_02 into SPEAKER_00
    op = classifier.merge_speaker_clusters("SPEAKER_02", "SPEAKER_00")
    assert op.source_cluster_id == "SPEAKER_02"
    assert op.target_cluster_id == "SPEAKER_00"
    assert set(op.affected_cue_ids) == {"cue_11", "cue_12"}

    # Verify effective speakers updated
    assert classifier.get_cue("cue_11").effective_speaker == "SPEAKER_00"
    assert classifier.get_cue("cue_12").effective_speaker == "SPEAKER_00"
    assert len(classifier.get_merge_history()) == 1


def test_character_registry_and_consent_audit() -> None:
    registry = CharacterRegistry()

    char = registry.register_character(
        character_id="char_hero",
        name="Anupam",
        actor_name="Soumitra Chatterjee",
        assigned_voice_id="bn-BD-PradeepNeural",
        gender=GenderIdentity.MALE,
        consent_granted=True,
    )
    assert char.name == "Anupam"
    assert char.consent_granted

    # Update voice assignment
    success = registry.update_voice_assignment("char_hero", "bn-BD-BashkarNeural")
    assert success
    assert registry.get_character("char_hero").assigned_voice_id == "bn-BD-BashkarNeural"

    # Revoke consent
    registry.set_consent_status("char_hero", False)
    assert not registry.get_character("char_hero").consent_granted

    # Verify audit trail
    logs = registry.get_audit_log()
    assert len(logs) >= 3
    actions = [l.action for l in logs]
    assert "REGISTER" in actions
    assert "VOICE_UPDATE" in actions
    assert "CONSENT_UPDATE" in actions
