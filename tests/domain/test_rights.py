from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aidub.domain.base import RightsViolation
from aidub.domain.rights import (
    ConsentRecord,
    ConsentStatus,
    VoiceOrigin,
    VoiceProfile,
    VoiceProfileStatus,
    VoiceUsageRequest,
    VoiceUse,
    assert_voice_use_authorized,
)

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)


def consent(**updates: object) -> ConsentRecord:
    values: dict[str, object] = {
        "consent_record_id": "cns_actor_tony",
        "project_id": "prj_feature_film",
        "subject": "Example Performer",
        "rights_owner": "Example Performer",
        "status": ConsentStatus.GRANTED,
        "evidence_reference": "rights/performer-license.pdf",
        "permitted_uses": frozenset({VoiceUse.DUBBING, VoiceUse.PREVIEW, VoiceUse.FINAL_EXPORT}),
        "languages": frozenset({"bn-BD", "hi-IN"}),
        "territories": frozenset({"WORLDWIDE"}),
        "valid_from": NOW - timedelta(days=1),
        "expires_at": NOW + timedelta(days=365),
        "approved_by": "legal@example.test",
        "approved_at": NOW - timedelta(days=2),
    }
    values.update(updates)
    return ConsentRecord.model_validate(values)


def profile(**updates: object) -> VoiceProfile:
    values: dict[str, object] = {
        "voice_profile_id": "vcp_tony_bengali",
        "project_id": "prj_feature_film",
        "display_name": "Tony Bengali",
        "origin": VoiceOrigin.CLONED,
        "engine_id": "voice-engine",
        "engine_voice_key": "tony-bn-v2",
        "supported_languages": frozenset({"bn-BD"}),
        "consent_record_id": "cns_actor_tony",
    }
    values.update(updates)
    return VoiceProfile.model_validate(values)


def request(**updates: object) -> VoiceUsageRequest:
    values: dict[str, object] = {
        "project_id": "prj_feature_film",
        "voice_profile_id": "vcp_tony_bengali",
        "language": "bn-BD",
        "territory": "BD",
        "use": VoiceUse.FINAL_EXPORT,
        "requested_at": NOW,
    }
    values.update(updates)
    return VoiceUsageRequest.model_validate(values)


def test_granted_consent_requires_evidence_scope_and_approval() -> None:
    with pytest.raises(ValidationError, match="missing"):
        ConsentRecord(
            consent_record_id="cns_actor_tony",
            subject="Example Performer",
            rights_owner="Example Performer",
            status=ConsentStatus.GRANTED,
        )


def test_consent_expiry_is_exclusive_and_language_territory_scoped() -> None:
    grant = consent()

    assert grant.permits(language="bn-BD", territory="BD", use=VoiceUse.FINAL_EXPORT, at=NOW)
    assert not grant.permits(language="es-ES", territory="BD", use=VoiceUse.FINAL_EXPORT, at=NOW)
    assert grant.expires_at is not None
    assert not grant.permits(
        language="bn-BD", territory="BD", use=VoiceUse.FINAL_EXPORT, at=grant.expires_at
    )


def test_revoked_consent_requires_reason_and_blocks_new_use() -> None:
    with pytest.raises(ValidationError, match="time and reason"):
        consent(status=ConsentStatus.REVOKED, revoked_at=None, revocation_reason=None)

    revoked = consent(
        status=ConsentStatus.REVOKED,
        revoked_at=NOW,
        revocation_reason="Grant withdrawn by performer",
    )
    with pytest.raises(RightsViolation, match="outside"):
        assert_voice_use_authorized(profile(), revoked, request())


def test_controlled_voice_profile_requires_consent_reference() -> None:
    with pytest.raises(ValidationError, match="requires a consent"):
        profile(consent_record_id=None)


def test_authorized_voice_use_passes_and_profile_mismatches_fail() -> None:
    assert_voice_use_authorized(profile(), consent(), request())

    with pytest.raises(RightsViolation, match="does not match"):
        assert_voice_use_authorized(
            profile(), consent(), request(voice_profile_id="vcp_other_voice")
        )
    with pytest.raises(RightsViolation, match="disabled"):
        assert_voice_use_authorized(
            profile(status=VoiceProfileStatus.DISABLED), consent(), request()
        )


def test_stock_synthetic_voice_can_be_used_without_performer_consent() -> None:
    stock = profile(
        origin=VoiceOrigin.SYNTHETIC_STOCK,
        consent_record_id=None,
        engine_voice_key="licensed-stock-voice-001",
    )

    assert_voice_use_authorized(stock, None, request())
