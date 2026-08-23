"""
Unit tests for Phase 6 Visual Intelligence & Selective Lip-Sync Engine:
  - Task 6.1: Shot Segmentation & Face Tracking Pipeline
  - Task 6.2: Active-Speaker Association & Lip-Sync Eligibility Scoring
  - Task 6.3: Selective Lip-Sync Adapters (MuseTalk & LatentSync) & Worker Handler
  - Task 6.4: Visual Quality Control & Original-Shot Fallback Engine
  - Task 6.5: NLE Timeline Lip-Sync Control Panel & Diagnostic Reporter
"""

from __future__ import annotations

import pytest

from aidub.adapters.lipsync_latentsync import LatentSyncLipSyncEngine
from aidub.adapters.lipsync_musetalk import MuseTalkLipSyncEngine
from aidub.ai.vision.active_speaker import ActiveSpeakerDetector
from aidub.ai.vision.eligibility import (
    LipSyncEligibilityEvaluator,
    ShotEligibilityClass,
    UserOverrideMode,
)
from aidub.ai.vision.face_tracker import (
    FaceBoundingBox,
    FaceTracker,
    FrameFaceDetection,
    KalmanState,
)
from aidub.ai.vision.shot_detector import ShotDetector
from aidub.ai.vision.visual_qc import VisualQcEvaluator
from aidub.ui.timeline.lipsync_panel import LipSyncControlPanelController
from aidub.workers.handlers import WorkerContext, get_handler

# ── Task 6.1: Shot Detector & Face Tracker Tests ──────────────────────────────


def test_shot_detector_uses_measured_frame_differences() -> None:
    detector = ShotDetector(fps=24.0)
    frame_diffs = [0.0] * 199
    frame_diffs[71] = 0.8
    frame_diffs[143] = 0.8
    result = detector.detect_shots("media_001", total_frames=200, frame_diffs=frame_diffs)
    assert len(result.shots) > 1
    assert result.shots[0].shot_id == "shot_0001"
    assert result.shots[0].start_frame == 0


def test_multi_criteria_shot_detector() -> None:
    detector = ShotDetector(cut_threshold=0.4, fps=24.0)
    hist_a = [0.1, 0.5, 0.4]
    hist_b = [0.9, 0.05, 0.05]
    delta = detector.compute_histogram_delta(hist_a, hist_b)
    assert delta > 0.5

    cut_type, conf = detector.classify_cut_type(0.60)
    assert cut_type == "hard_cut"
    assert conf >= 0.80

    cut_type_diss, _ = detector.classify_cut_type(0.30)
    assert cut_type_diss == "dissolve"


def test_face_tracker_iou_matching() -> None:
    tracker = FaceTracker(iou_threshold=0.3)
    frame0 = FrameFaceDetection(
        frame_index=0,
        faces=[FaceBoundingBox(x_min=0.2, y_min=0.2, width=0.2, height=0.2)],
    )
    frame1 = FrameFaceDetection(
        frame_index=1,
        faces=[FaceBoundingBox(x_min=0.21, y_min=0.21, width=0.2, height=0.2)],
    )

    tracks = tracker.track_faces_in_shot("shot_001", [frame0, frame1])
    assert len(tracks) == 1
    assert tracks[0].start_frame == 0
    assert tracks[0].end_frame == 1


def test_kalman_state_prediction() -> None:
    box = FaceBoundingBox(x_min=0.2, y_min=0.2, width=0.2, height=0.2)
    state = KalmanState(box)
    pred_box = state.predict()
    assert pred_box.width == 0.2
    assert pred_box.height == 0.2

    box_moved = FaceBoundingBox(x_min=0.25, y_min=0.25, width=0.2, height=0.2)
    state.update(box_moved)
    assert state.vx > 0
    assert state.vy > 0


# ── Task 6.2: Active Speaker & Eligibility Tests ──────────────────────────────


def test_active_speaker_association() -> None:
    tracker = FaceTracker()
    frame0 = FrameFaceDetection(
        frame_index=0,
        faces=[FaceBoundingBox(x_min=0.1, y_min=0.1, width=0.3, height=0.3)],
    )
    tracks = tracker.track_faces_in_shot("shot_001", [frame0])

    assoc = ActiveSpeakerDetector.associate_speaker("spk_01", tracks, 0, 3000)
    assert assoc is not None
    assert assoc.speaker_id == "spk_01"
    assert assoc.is_active_speaker is True


def test_syncnet_cross_modal_cross_correlation() -> None:
    audio_energy = [0.1, 0.8, 0.9, 0.2, 0.85]
    mouth_motion = [0.12, 0.75, 0.88, 0.18, 0.82]
    corr = ActiveSpeakerDetector.compute_cross_correlation(audio_energy, mouth_motion)
    assert corr > 0.85


def test_eligibility_evaluator_classifications() -> None:
    evaluator = LipSyncEligibilityEvaluator(min_face_area_ratio=0.015)

    # Off screen speaker -> ineligible
    res_off = evaluator.evaluate_eligibility("shot_001", face_track=None, is_off_screen=True)
    assert res_off.classification == ShotEligibilityClass.OFF_SCREEN_INELIGIBLE
    assert res_off.is_eligible_for_rendering is False

    # Close up track -> eligible
    tracker = FaceTracker()
    frame0 = FrameFaceDetection(
        frame_index=0,
        faces=[FaceBoundingBox(x_min=0.1, y_min=0.1, width=0.4, height=0.4)],  # area 0.16
    )
    tracks = tracker.track_faces_in_shot("shot_001", [frame0])
    res_close = evaluator.evaluate_eligibility("shot_001", face_track=tracks[0])
    assert res_close.classification == ShotEligibilityClass.CLOSE_UP_ELIGIBLE
    assert res_close.is_eligible_for_rendering is True


def test_3d_pose_and_user_override_eligibility() -> None:
    evaluator = LipSyncEligibilityEvaluator()
    tracker = FaceTracker()
    frame0 = FrameFaceDetection(
        frame_index=0,
        faces=[FaceBoundingBox(x_min=0.1, y_min=0.1, width=0.4, height=0.4)],
    )
    tracks = tracker.track_faces_in_shot("shot_001", [frame0])

    # Extreme Yaw 45 deg -> ineligible
    res_pose = evaluator.evaluate_eligibility("shot_001", tracks[0], head_yaw_deg=45.0)
    assert res_pose.is_eligible_for_rendering is False

    # Force eligible override -> eligible
    res_force = evaluator.evaluate_eligibility(
        "shot_001", tracks[0], head_yaw_deg=45.0, user_override=UserOverrideMode.FORCE_ELIGIBLE
    )
    assert res_force.is_eligible_for_rendering is True


# ── Task 6.3: Selective Lip-Sync Engine Tests ─────────────────────────────────


def test_musetalk_preview_engine(tmp_path) -> None:
    engine = MuseTalkLipSyncEngine()
    with pytest.raises(FileNotFoundError, match="source video does not exist"):
        engine.synthesize_lip_sync(
            shot_id="shot_001",
            source_video_path="source.mp4",
            target_audio_path="audio.wav",
            output_directory=str(tmp_path),
        )


def test_latentsync_cinema_engine(tmp_path) -> None:
    engine = LatentSyncLipSyncEngine()
    with pytest.raises(FileNotFoundError, match="source video does not exist"):
        engine.synthesize_lip_sync(
            shot_id="shot_002",
            source_video_path="source.mp4",
            target_audio_path="audio.wav",
            output_directory=str(tmp_path),
        )


def test_lipsync_worker_registered_handler(tmp_path) -> None:
    import queue

    from aidub.contracts.jobs import JobDescriptor

    handler = get_handler("lipsync.render")
    assert handler is not None

    control_q = queue.Queue()
    result_q = queue.Queue()
    ctx = WorkerContext(job_id="job_ls_1", _control_queue=control_q, _result_queue=result_q)
    job = JobDescriptor(
        job_id="job_ls_1",
        idempotency_key="a" * 64,
        project_id="prj_001",
        job_type="lipsync.render",
        parameters={
            "shot_id": "shot_003",
            "source_video_path": "source.mp4",
            "target_audio_path": "audio.wav",
            "output_directory": str(tmp_path),
            "quality_tier": "preview_fast",
        },
    )
    with pytest.raises(FileNotFoundError, match="source video does not exist"):
        handler(job, ctx)


# ── Task 6.4 & 6.5: Visual Quality Control & NLE Panel Controller Tests ─────


def test_visual_qc_evaluator_pass_and_fallback() -> None:
    evaluator = VisualQcEvaluator(pass_threshold=0.70)

    # Good scores pass QC
    good_res = evaluator.evaluate_shot_video("shot_001", "vid.mp4", (0.95, 0.90, 0.95))
    assert good_res.passed_qc is True
    assert good_res.should_fallback_to_original is False

    # Low scores fail QC -> fallback to original video with recommendations
    bad_res = evaluator.evaluate_shot_video("shot_002", "vid.mp4", (0.40, 0.30, 0.50))
    assert bad_res.passed_qc is False
    assert bad_res.should_fallback_to_original is True
    assert "Falling back to original video" in bad_res.rejection_reason
    assert len(bad_res.diagnostic_recommendations) > 0


def test_lipsync_control_panel_controller() -> None:
    ctrl = LipSyncControlPanelController()
    ctrl.set_shot("shot_0042")
    assert ctrl.config.selected_shot_id == "shot_0042"

    ctrl.set_override(UserOverrideMode.FORCE_ELIGIBLE)
    assert ctrl.config.user_override == UserOverrideMode.FORCE_ELIGIBLE

    eligibility, qc_result = ctrl.inspect_shot(simulated_qc_scores=(0.95, 0.95, 0.95))
    assert eligibility.is_eligible_for_rendering is True
    assert qc_result.passed_qc is True
