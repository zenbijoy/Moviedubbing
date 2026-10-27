"""
Scene-Aware Dialogue Performance Service (Phase 2).

Combines cinematic scene context (dramatic tone, environment, pacing) with
per-line dialogue controls (emotion, intensity, emphasis, pauses, candidate takes).

Ensures only supported TTS parameters are applied to engines, providing
explicit fallbacks and transparency logs when unsupported controls are requested.
Supports before-and-after candidate auditioning and single-line regeneration.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from aidub.adapters.voice_base import (
    EmotionLabel,
    EngineCapability,
    NormalizedPerformance,
    VoiceEngine,
)
from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class CandidateTake(ContractModel):
    """An alternative audio take delivery candidate for auditioning."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    take_id: str = Field(min_length=1)
    audio_path: str = Field(min_length=1)
    duration_s: float = Field(default=0.0, ge=0.0)
    applied_parameters: dict[str, Any] = Field(default_factory=dict)
    fallback_notes: list[str] = Field(default_factory=list)
    created_at_iso: str = Field(default="")
    is_approved: bool = False
    is_rejected: bool = False
    rejection_reason: str = Field(default="")
    qc_passed: bool = True


class SceneContext(ContractModel):
    """Cinematic scene metadata providing dramatic tone and acoustic setting."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    scene_id: Identifier
    name: str = Field(default="", max_length=128)
    dramatic_tone: str = Field(
        default="neutral", max_length=64
    )  # e.g. "tense", "intimate", "somber", "triumphant"
    acoustic_environment: str = Field(
        default="studio", max_length=64
    )  # e.g. "cavern", "hall", "exterior", "small_room"
    default_emotion: str = Field(default="neutral", max_length=32)
    default_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    delivery_instructions: str = Field(default="", max_length=500)


class DialogueCuePerformance(ContractModel):
    """Tracks full dramatic intent, context, and generated takes for a dialogue cue."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cue_id: Identifier
    scene_id: Identifier
    character_id: Identifier
    speaker_id: Identifier
    source_text: str = Field(min_length=1)
    target_text: str = Field(min_length=1)
    start_s: float = Field(default=0.0, ge=0.0)
    end_s: float = Field(default=0.0, ge=0.0)
    target_duration_s: float = Field(default=0.0, ge=0.0)

    # Per-line performance overrides
    per_line_emotion: str | None = None
    per_line_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    per_line_style: str | None = None
    emphasis_words: list[str] = Field(default_factory=list)
    pause_before_ms: int = Field(default=0, ge=0, le=5000)
    pause_after_ms: int = Field(default=0, ge=0, le=10_000)

    # Multi-take candidate tracking & audition
    selected_take_id: str | None = None
    candidate_takes: list[CandidateTake] = Field(default_factory=list)
    validation_status: str = Field(default="pending")  # "pending", "validated", "warning", "rejected"


class ScenePerformanceService:
    """
    Coordinates scene context with dialogue performance parameters,
    candidate takes, and capability-aware voice synthesis.
    """

    def __init__(self) -> None:
        self._scenes: dict[str, SceneContext] = {}
        self._cues: dict[str, DialogueCuePerformance] = {}

    def register_scene(self, scene: SceneContext) -> None:
        """Register or update a scene context."""
        self._scenes[str(scene.scene_id)] = scene

    def get_scene(self, scene_id: str) -> SceneContext | None:
        """Retrieve scene context by ID."""
        return self._scenes.get(str(scene_id))

    def register_cue(self, cue: DialogueCuePerformance) -> None:
        """Register or update a dialogue cue performance tracker."""
        self._cues[str(cue.cue_id)] = cue

    def get_cue(self, cue_id: str) -> DialogueCuePerformance | None:
        """Retrieve dialogue cue performance by ID."""
        return self._cues.get(str(cue_id))

    def list_cues_for_scene(self, scene_id: str) -> list[DialogueCuePerformance]:
        """Return all dialogue cues registered under a scene."""
        sid = str(scene_id)
        return [c for c in self._cues.values() if str(c.scene_id) == sid]

    def resolve_effective_performance(
        self,
        cue_id: str,
        engine_capabilities: set[EngineCapability],
    ) -> tuple[NormalizedPerformance, dict[str, Any], list[str]]:
        """
        Combine scene context, cue overrides, and engine capabilities.

        Unsupported parameters are safely degraded to neutral defaults and
        logged in fallback_notes.

        Returns:
            (normalized_performance, applied_parameters, fallback_notes)
        """
        cue = self.get_cue(cue_id)
        if not cue:
            raise ValueError(f"Dialogue cue '{cue_id}' not found.")

        scene = self.get_scene(str(cue.scene_id))

        # 1. Determine raw requested values (Cue override > Scene default > Neutral)
        raw_emotion = cue.per_line_emotion or (scene.default_emotion if scene else "neutral")
        raw_intensity = (
            cue.per_line_intensity
            if cue.per_line_intensity is not None
            else (scene.default_intensity if scene else 0.5)
        )
        raw_style = cue.per_line_style or (scene.dramatic_tone if scene else "neutral")
        pause_after_ms = cue.pause_after_ms

        applied_parameters: dict[str, Any] = {}
        fallback_notes: list[str] = []

        # 2. Check Emotion Conditioning capability
        if EngineCapability.EMOTION_CONDITIONING in engine_capabilities:
            try:
                emotion_enum = EmotionLabel(raw_emotion.lower())
                applied_parameters["emotion"] = emotion_enum.value
            except ValueError:
                emotion_enum = EmotionLabel.NEUTRAL
                fallback_notes.append(
                    f"Requested emotion '{raw_emotion}' not in standard vocabulary; defaulted to neutral."
                )
        else:
            emotion_enum = EmotionLabel.NEUTRAL
            if raw_emotion.lower() != "neutral":
                fallback_notes.append(
                    f"Target voice engine does not support emotion conditioning; ignored '{raw_emotion}'."
                )

        # 3. Check Style Intensity capability
        if EngineCapability.STYLE_INTENSITY in engine_capabilities:
            applied_intensity = float(raw_intensity)
            applied_style = str(raw_style)
            applied_parameters["emotion_intensity"] = applied_intensity
            applied_parameters["style_descriptor"] = applied_style
        else:
            applied_intensity = 0.5
            applied_style = "neutral"
            if raw_intensity != 0.5 or raw_style.lower() != "neutral":
                fallback_notes.append(
                    "Target voice engine does not support style intensity; defaulted to standard delivery."
                )

        applied_parameters["pause_after_ms"] = pause_after_ms
        if cue.emphasis_words:
            applied_parameters["emphasis_words"] = list(cue.emphasis_words)

        norm_perf = NormalizedPerformance(
            primary_emotion=emotion_enum,
            emotion_intensity=applied_intensity,
            style_descriptor=applied_style,
            speaking_rate=1.0,
            pitch_shift_semitones=0.0,
            energy_scale=1.0,
            pause_after_ms=pause_after_ms,
        )

        return norm_perf, applied_parameters, fallback_notes

    def add_candidate_take(
        self,
        cue_id: str,
        audio_path: str,
        duration_s: float,
        applied_parameters: dict[str, Any],
        fallback_notes: list[str],
    ) -> CandidateTake:
        """
        Record a new candidate take for a cue.
        Automatically sets it as selected if no take is currently active.
        """
        cue = self.get_cue(cue_id)
        if not cue:
            raise ValueError(f"Dialogue cue '{cue_id}' not found.")

        take_number = len(cue.candidate_takes) + 1
        take_id = f"take_{take_number}"

        candidate = CandidateTake(
            take_id=take_id,
            audio_path=audio_path,
            duration_s=duration_s,
            applied_parameters=applied_parameters,
            fallback_notes=fallback_notes,
            created_at_iso=datetime.now(UTC).isoformat(),
            is_approved=False,
            is_rejected=False,
            qc_passed=True,
        )

        cue.candidate_takes.append(candidate)
        if not cue.selected_take_id:
            cue.selected_take_id = take_id

        logger.info(
            "Registered candidate take '%s' for cue '%s' (duration=%.2fs)",
            take_id,
            cue_id,
            duration_s,
        )
        return candidate

    def select_take(self, cue_id: str, take_id: str) -> bool:
        """Set the active take for playback and timeline rendering."""
        cue = self.get_cue(cue_id)
        if not cue:
            return False
        if any(t.take_id == take_id for t in cue.candidate_takes):
            cue.selected_take_id = take_id
            return True
        return False

    def approve_take(self, cue_id: str, take_id: str) -> bool:
        """Mark a candidate take as director-approved for master export."""
        cue = self.get_cue(cue_id)
        if not cue:
            return False
        for take in cue.candidate_takes:
            if take.take_id == take_id:
                take.is_approved = True
                take.is_rejected = False
                cue.selected_take_id = take_id
                cue.validation_status = "validated"
                return True
        return False

    def reject_take(self, cue_id: str, take_id: str, reason: str = "") -> bool:
        """Mark a candidate take as rejected with director feedback."""
        cue = self.get_cue(cue_id)
        if not cue:
            return False
        for take in cue.candidate_takes:
            if take.take_id == take_id:
                take.is_rejected = True
                take.is_approved = False
                take.rejection_reason = reason
                return True
        return False

    def get_audition_comparison(
        self,
        cue_id: str,
        take_id_a: str,
        take_id_b: str | None = None,
    ) -> dict[str, Any]:
        """
        Produce side-by-side audition metadata for comparing candidate takes.
        If take_id_b is None, compares against the currently selected take or original timing.
        """
        cue = self.get_cue(cue_id)
        if not cue:
            raise ValueError(f"Dialogue cue '{cue_id}' not found.")

        take_a = next((t for t in cue.candidate_takes if t.take_id == take_id_a), None)
        if not take_a:
            raise ValueError(f"Take '{take_id_a}' not found on cue '{cue_id}'.")

        take_b = None
        if take_id_b:
            take_b = next((t for t in cue.candidate_takes if t.take_id == take_id_b), None)
        elif cue.selected_take_id and cue.selected_take_id != take_id_a:
            take_b = next((t for t in cue.candidate_takes if t.take_id == cue.selected_take_id), None)

        return {
            "cue_id": str(cue.cue_id),
            "character_id": str(cue.character_id),
            "target_duration_s": cue.target_duration_s,
            "take_a": {
                "take_id": take_a.take_id,
                "audio_path": take_a.audio_path,
                "duration_s": take_a.duration_s,
                "applied_parameters": take_a.applied_parameters,
                "is_approved": take_a.is_approved,
            },
            "take_b": (
                {
                    "take_id": take_b.take_id,
                    "audio_path": take_b.audio_path,
                    "duration_s": take_b.duration_s,
                    "applied_parameters": take_b.applied_parameters,
                    "is_approved": take_b.is_approved,
                }
                if take_b
                else None
            ),
        }

    def regenerate_single_line(
        self,
        cue_id: str,
        voice_engine: VoiceEngine,
        voice_id: str,
        output_dir: Path | str,
        reference_path: str | None = None,
        language: str = "bn-BD",
    ) -> CandidateTake:
        """
        Regenerate a single dialogue line without invalidating adjacent lines.
        Generates a new candidate take, applies capability filtering, and tracks parameters.
        """
        from aidub.adapters.voice_base import SynthesisRequest
        from aidub.domain.types import LanguageTag

        cue = self.get_cue(cue_id)
        if not cue:
            raise ValueError(f"Cue '{cue_id}' not found.")

        caps = voice_engine.metadata.capabilities
        norm_perf, applied_params, fallback_notes = self.resolve_effective_performance(cue_id, caps)

        take_index = len(cue.candidate_takes) + 1
        req = SynthesisRequest(
            request_id=Identifier(f"req_{cue_id}_{take_index}"),
            utterance_id=cue.cue_id,
            voice_profile_id=Identifier(str(voice_id)),
            text=cue.target_text,
            language=LanguageTag(language),
            emotion=norm_perf.primary_emotion,
            emotion_intensity=norm_perf.emotion_intensity,
            pace_multiplier=norm_perf.speaking_rate,
            pitch_shift_semitones=norm_perf.pitch_shift_semitones,
            reference_audio_path=reference_path or "",
            performance=norm_perf,
        )

        res = voice_engine.synthesize(req, str(output_dir))

        duration_sec = res.duration_ms / 1000.0 if res.duration_ms else 0.0

        return self.add_candidate_take(
            cue_id=cue_id,
            audio_path=str(res.output_path),
            duration_s=duration_sec,
            applied_parameters=applied_params,
            fallback_notes=fallback_notes,
        )



__all__ = [
    "CandidateTake",
    "DialogueCuePerformance",
    "SceneContext",
    "ScenePerformanceService",
]
