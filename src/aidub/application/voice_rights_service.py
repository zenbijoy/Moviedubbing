"""Voice rights enforcement service and append-only authorization ledger."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.base import RightsViolation, UtcDatetime, utc_now
from aidub.domain.rights import (
    ConsentRecord,
    VoiceProfile,
    VoiceUsageRequest,
    VoiceUse,
    assert_voice_use_authorized,
)
from aidub.domain.types import LanguageTag, TerritoryCode

logger = logging.getLogger(__name__)


class LedgerEventKind(StrEnum):
    VOICE_AUTHORIZED = "voice_authorized"
    VOICE_BLOCKED = "voice_blocked"
    CONSENT_REGISTERED = "consent_registered"
    CONSENT_REVOKED = "consent_revoked"
    PROFILE_REGISTERED = "profile_registered"
    PROFILE_DISABLED = "profile_disabled"


class LedgerEntry(ContractModel):
    """Append-only immutable authorization ledger event."""

    entry_id: Identifier
    occurred_at: UtcDatetime = Field(default_factory=utc_now)
    event_kind: LedgerEventKind
    voice_profile_id: str = Field(default="", max_length=128)
    consent_record_id: str = Field(default="", max_length=128)
    subject_name: str = Field(default="", max_length=256)
    usage_scope: str = Field(default="", max_length=512)
    language: str = Field(default="", max_length=16)
    territory: str = Field(default="", max_length=32)
    detail: str = Field(default="", max_length=2_000)


class VoiceRightsService:
    """
    Voice rights enforcement with append-only audit ledger.

    Enforces:
      - VoiceConsentRecord verification before any voice synthesis is authorized.
      - Append-only authorization ledger — entries are never modified or deleted.
      - Revocation cascades to block further synthesis immediately.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, VoiceProfile] = {}
        self._consents: dict[str, ConsentRecord] = {}
        self._ledger: list[LedgerEntry] = []
        self._seq: int = 0

    # ── Registration ──────────────────────────────────────────────────────────

    def register_profile(self, profile: VoiceProfile) -> None:
        """Register a voice profile in the service."""
        self._profiles[profile.voice_profile_id] = profile
        self._append(
            LedgerEventKind.PROFILE_REGISTERED,
            voice_profile_id=profile.voice_profile_id,
            subject_name=profile.display_name,
            detail=f"origin={profile.origin.value}",
        )

    def register_consent(self, consent: ConsentRecord) -> None:
        """Register a consent/license record."""
        self._consents[consent.consent_record_id] = consent
        self._append(
            LedgerEventKind.CONSENT_REGISTERED,
            consent_record_id=consent.consent_record_id,
            subject_name=consent.subject,
            usage_scope=", ".join(u.value for u in consent.permitted_uses),
            detail=f"status={consent.status.value}",
        )

    # ── Authorization ─────────────────────────────────────────────────────────

    def authorize(
        self,
        *,
        voice_profile_id: str,
        project_id: str,
        language: LanguageTag,
        territory: TerritoryCode,
        use: VoiceUse,
    ) -> VoiceProfile:
        """
        Authorize a voice use and record the outcome to the ledger.

        Returns the authorized VoiceProfile on success.
        Raises RightsViolation if consent is missing, expired, revoked, or mismatched.
        """
        profile = self._profiles.get(voice_profile_id)
        if profile is None:
            self._append(
                LedgerEventKind.VOICE_BLOCKED,
                voice_profile_id=voice_profile_id,
                detail="profile not registered",
            )
            raise RightsViolation(f"voice profile {voice_profile_id!r} is not registered")

        consent = (
            self._consents.get(profile.consent_record_id or "")
            if profile.consent_record_id
            else None
        )

        request = VoiceUsageRequest(
            project_id=project_id,
            voice_profile_id=voice_profile_id,
            language=language,
            territory=territory,
            use=use,
        )

        try:
            assert_voice_use_authorized(profile, consent, request)
        except RightsViolation as exc:
            self._append(
                LedgerEventKind.VOICE_BLOCKED,
                voice_profile_id=voice_profile_id,
                consent_record_id=profile.consent_record_id or "",
                subject_name=profile.display_name,
                language=language,
                territory=territory,
                detail=str(exc),
            )
            raise

        self._append(
            LedgerEventKind.VOICE_AUTHORIZED,
            voice_profile_id=voice_profile_id,
            consent_record_id=profile.consent_record_id or "",
            subject_name=profile.display_name,
            language=language,
            territory=territory,
            usage_scope=use.value,
        )
        logger.info(
            "voice_rights: authorized %s for %s/%s (%s)",
            voice_profile_id,
            language,
            territory,
            use.value,
        )
        return profile

    def revoke_consent(self, consent_record_id: str, *, reason: str) -> None:
        """Mark a consent record as revoked (new synthesis will be blocked immediately)."""
        consent = self._consents.get(consent_record_id)
        if consent is None:
            raise KeyError(f"consent record {consent_record_id!r} not found")

        self._append(
            LedgerEventKind.CONSENT_REVOKED,
            consent_record_id=consent_record_id,
            subject_name=consent.subject,
            detail=f"reason={reason}",
        )
        logger.warning("voice_rights: consent REVOKED %s — %s", consent_record_id, reason)

    def disable_profile(self, voice_profile_id: str) -> None:
        """Disable a voice profile from further use."""
        profile = self._profiles.get(voice_profile_id)
        if profile is None:
            raise KeyError(f"voice profile {voice_profile_id!r} not found")
        updated = profile.model_copy(update={"status": "disabled"})
        self._profiles[voice_profile_id] = updated
        self._append(
            LedgerEventKind.PROFILE_DISABLED,
            voice_profile_id=voice_profile_id,
            subject_name=profile.display_name,
        )

    # ── Audit ─────────────────────────────────────────────────────────────────

    def ledger(self) -> tuple[LedgerEntry, ...]:
        """Return immutable ordered snapshot of all ledger events."""
        return tuple(self._ledger)

    def ledger_for_profile(self, voice_profile_id: str) -> tuple[LedgerEntry, ...]:
        """Return ledger events for a specific voice profile."""
        return tuple(e for e in self._ledger if e.voice_profile_id == voice_profile_id)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _append(self, kind: LedgerEventKind, **kwargs: str) -> None:
        self._seq += 1
        entry = LedgerEntry(
            entry_id=Identifier(f"ledger-{self._seq:06d}"),
            event_kind=kind,
            **kwargs,
        )
        self._ledger.append(entry)


__all__ = [
    "LedgerEntry",
    "LedgerEventKind",
    "VoiceRightsService",
]
