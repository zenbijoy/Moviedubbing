"""
Enterprise lip-sync shot eligibility classification engine.

Classifies camera shots into:
  - CLOSE_UP_ELIGIBLE: High-priority, high-resolution close-up face shot.
  - MEDIUM_SHOT_ELIGIBLE: Medium shot eligible for selective lip-sync overlay.
  - TINY_FACE_INELIGIBLE: Face size < min area threshold (ineligible).
  - OCCLUDED_INELIGIBLE: Face obscured or hand/object blocking mouth.
  - OFF_SCREEN_INELIGIBLE: Active speaker is off-screen (ineligible).
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.ai.vision.face_tracker import FaceTrack
from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class ShotEligibilityClass(StrEnum):
    CLOSE_UP_ELIGIBLE = "close_up_eligible"
    MEDIUM_SHOT_ELIGIBLE = "medium_shot_eligible"
    TINY_FACE_INELIGIBLE = "tiny_face_ineligible"
    OCCLUDED_INELIGIBLE = "occluded_ineligible"
    OFF_SCREEN_INELIGIBLE = "off_screen_ineligible"


class UserOverrideMode(StrEnum):
    AUTO = "auto"
    FORCE_ELIGIBLE = "force_eligible"
    FORCE_INELIGIBLE = "force_ineligible"


class EligibilityScore(ContractModel):
    """Evaluation result determining if a face track in a shot should undergo lip-sync rendering."""

    shot_id: Identifier
    face_track_id: Identifier | None = None
    classification: ShotEligibilityClass = ShotEligibilityClass.CLOSE_UP_ELIGIBLE
    face_area_ratio: float = Field(default=0.08, ge=0.0, le=1.0)
    head_pose_yaw_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    head_pose_pitch_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    illumination_score: float = Field(default=0.90, ge=0.0, le=1.0)
    blur_score: float = Field(default=0.05, ge=0.0, le=1.0)
    override_mode: UserOverrideMode = UserOverrideMode.AUTO
    is_eligible_for_rendering: bool = True
    reason: str = Field(default="Eligible close-up face shot", max_length=256)


class LipSyncEligibilityEvaluator:
    """
    Enterprise evaluator assessing face size, 3D head pose, lighting, blur, and manual user overrides.
    """

    def __init__(
        self,
        min_face_area_ratio: float = 0.015,
        max_yaw_angle_deg: float = 40.0,
        max_pitch_angle_deg: float = 35.0,
    ) -> None:
        self.min_face_area_ratio = min_face_area_ratio
        self.max_yaw_angle_deg = max_yaw_angle_deg
        self.max_pitch_angle_deg = max_pitch_angle_deg

    def evaluate_eligibility(
        self,
        shot_id: str,
        face_track: FaceTrack | None,
        is_off_screen: bool = False,
        is_occluded: bool = False,
        head_yaw_deg: float = 0.0,
        head_pitch_deg: float = 0.0,
        illumination_score: float = 0.90,
        blur_score: float = 0.05,
        user_override: UserOverrideMode = UserOverrideMode.AUTO,
    ) -> EligibilityScore:
        """Evaluate whether a face track in a shot should undergo AI lip-sync synthesis."""
        sid = Identifier(shot_id)

        # Handle Manual User Overrides
        if user_override == UserOverrideMode.FORCE_ELIGIBLE:
            return EligibilityScore(
                shot_id=sid,
                face_track_id=face_track.track_id if face_track else None,
                classification=ShotEligibilityClass.CLOSE_UP_ELIGIBLE,
                face_area_ratio=face_track.average_area if face_track else 0.05,
                override_mode=user_override,
                is_eligible_for_rendering=True,
                reason="Forced eligible by user timeline override",
            )
        if user_override == UserOverrideMode.FORCE_INELIGIBLE:
            return EligibilityScore(
                shot_id=sid,
                face_track_id=face_track.track_id if face_track else None,
                classification=ShotEligibilityClass.OFF_SCREEN_INELIGIBLE,
                face_area_ratio=face_track.average_area if face_track else 0.0,
                override_mode=user_override,
                is_eligible_for_rendering=False,
                reason="Forced ineligible by user timeline override",
            )

        if is_off_screen or face_track is None:
            return EligibilityScore(
                shot_id=sid,
                face_track_id=None,
                classification=ShotEligibilityClass.OFF_SCREEN_INELIGIBLE,
                face_area_ratio=0.0,
                is_eligible_for_rendering=False,
                reason="Speaker is off-screen or no face detected",
            )

        if is_occluded:
            return EligibilityScore(
                shot_id=sid,
                face_track_id=face_track.track_id,
                classification=ShotEligibilityClass.OCCLUDED_INELIGIBLE,
                face_area_ratio=face_track.average_area,
                is_eligible_for_rendering=False,
                reason="Face or mouth area is occluded by objects or hand",
            )

        # 3D Head Pose angle evaluation
        if (
            abs(head_yaw_deg) > self.max_yaw_angle_deg
            or abs(head_pitch_deg) > self.max_pitch_angle_deg
        ):
            return EligibilityScore(
                shot_id=sid,
                face_track_id=face_track.track_id,
                classification=ShotEligibilityClass.OCCLUDED_INELIGIBLE,
                face_area_ratio=face_track.average_area,
                head_pose_yaw_deg=head_yaw_deg,
                head_pose_pitch_deg=head_pitch_deg,
                is_eligible_for_rendering=False,
                reason=f"Extreme 3D head pose (yaw={head_yaw_deg:.1f}°, pitch={head_pitch_deg:.1f}°)",
            )

        area_ratio = face_track.average_area
        if area_ratio < self.min_face_area_ratio:
            return EligibilityScore(
                shot_id=sid,
                face_track_id=face_track.track_id,
                classification=ShotEligibilityClass.TINY_FACE_INELIGIBLE,
                face_area_ratio=area_ratio,
                is_eligible_for_rendering=False,
                reason=f"Face area {area_ratio:.4f} is below minimum threshold {self.min_face_area_ratio}",
            )

        if area_ratio >= 0.05:
            classification = ShotEligibilityClass.CLOSE_UP_ELIGIBLE
            reason = "High-visibility close-up shot eligible for Cinema Lip-Sync"
        else:
            classification = ShotEligibilityClass.MEDIUM_SHOT_ELIGIBLE
            reason = "Medium shot eligible for Preview Lip-Sync"

        return EligibilityScore(
            shot_id=sid,
            face_track_id=face_track.track_id,
            classification=classification,
            face_area_ratio=area_ratio,
            head_pose_yaw_deg=head_yaw_deg,
            head_pose_pitch_deg=head_pitch_deg,
            illumination_score=illumination_score,
            blur_score=blur_score,
            is_eligible_for_rendering=True,
            reason=reason,
        )


__all__ = [
    "EligibilityScore",
    "LipSyncEligibilityEvaluator",
    "ShotEligibilityClass",
    "UserOverrideMode",
]
