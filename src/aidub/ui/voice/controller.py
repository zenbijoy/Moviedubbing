"""
Voice Cloning Studio Presentation UI Controller.

Manages Python business logic bindings, reference quality ranking, consent status audits,
and take evaluation preview triggers for the QML / Qt Quick presentation layer.
"""

from __future__ import annotations

from collections.abc import Sequence

from aidub.application.voice.consent_guard import VoiceConsentGuard
from aidub.application.voice.profile_builder import CharacterVoiceProfileBuilder
from aidub.application.voice.take_evaluator import VoiceTakeEvaluator, VoiceTakeQcReport
from aidub.domain.voice_profile import CharacterVoiceProfile, ReferenceSample


class VoicePreviewUnavailableError(RuntimeError):
    """Raised when this controller cannot produce a real synthesized preview."""


class ConsentAuthorizationUnavailableError(RuntimeError):
    """Raised when consent has not been verified through the rights ledger."""


class VoiceCloningStudioController:
    """
    Controller binding business logic to Qt Quick QML views (headless safe).
    """

    def __init__(self) -> None:
        self.profile_builder = CharacterVoiceProfileBuilder()
        self.consent_guard = VoiceConsentGuard()
        self.take_evaluator = VoiceTakeEvaluator()
        self.active_profile: CharacterVoiceProfile | None = None

    def load_character_profile(
        self,
        character_id: str,
        display_name: str,
        mined_references: Sequence[ReferenceSample],
    ) -> CharacterVoiceProfile:
        """
        Load or assemble character profile.
        """
        self.active_profile = self.profile_builder.build_character_profile(
            character_id, display_name, mined_references, consent_authorized=False
        )
        return self.active_profile

    def authorize_consent(self) -> bool:
        """
        Refuse local consent toggles; authorization must be verified by VoiceRightsService.
        """
        raise ConsentAuthorizationUnavailableError(
            "Consent cannot be authorized from this controller. Register a real consent record "
            "and authorize the profile through VoiceRightsService."
        )

    def clear_local_authorization(self) -> bool:
        """
        Clear the local profile's authorization flag without claiming ledger revocation.
        """
        if not self.active_profile:
            return False
        self.active_profile = self.consent_guard.revoke_voice_consent(self.active_profile)
        return True

    def request_synthesis_preview(self, utterance_id: str, target_language: str = "bn-BD") -> str:
        """
        Keep consent gating, but do not return a fake token in place of synthesized audio.
        """
        if not self.active_profile:
            raise ValueError("No active voice profile loaded")

        self.consent_guard.ensure_synthesis_authorized(self.active_profile)
        raise VoicePreviewUnavailableError(
            "This controller has no voice-conversion preview backend. The timeline's real "
            "Edge TTS preview requires dialogue text and writes an audio file."
        )

    def evaluate_synthesized_take(
        self,
        take_id: str,
        utterance_id: str,
        *,
        speaker_similarity: float,
        naturalness_score: float,
        emotion_match_score: float,
        timing_fit_score: float,
    ) -> VoiceTakeQcReport:
        """
        Evaluate quality metrics for a synthesized take.
        """
        return self.take_evaluator.evaluate_take(
            take_id=take_id,
            utterance_id=utterance_id,
            speaker_similarity=speaker_similarity,
            naturalness_score=naturalness_score,
            emotion_match_score=emotion_match_score,
            timing_fit_score=timing_fit_score,
        )


__all__ = [
    "ConsentAuthorizationUnavailableError",
    "VoiceCloningStudioController",
    "VoicePreviewUnavailableError",
]
