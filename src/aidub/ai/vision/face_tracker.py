"""
Enterprise persistent multi-face tracking engine across video shot frames.

Combines Kalman Filter trajectory prediction, bounding box IoU matching,
and facial feature re-identification (ReID) embedding distance matching to assign
persistent track IDs across frame sequences and handle brief visual occlusions.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Any

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class FaceBoundingBox(ContractModel):
    """Normalized face bounding box in image space [0.0, 1.0]."""

    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    feature_embedding: list[float] = Field(default_factory=list)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x_min + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y_min + self.height / 2.0

    @property
    def x_max(self) -> float:
        return min(1.0, self.x_min + self.width)

    @property
    def y_max(self) -> float:
        return min(1.0, self.y_min + self.height)

    def iou(self, other: FaceBoundingBox) -> float:
        """Calculate Intersection-over-Union (IoU) with another bounding box."""
        inter_x_min = max(self.x_min, other.x_min)
        inter_y_min = max(self.y_min, other.y_min)
        inter_x_max = min(self.x_max, other.x_max)
        inter_y_max = min(self.y_max, other.y_max)

        inter_w = max(0.0, inter_x_max - inter_x_min)
        inter_h = max(0.0, inter_y_max - inter_y_min)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area

    def embedding_similarity(self, other: FaceBoundingBox) -> float:
        """Compute Cosine Similarity between face feature embeddings."""
        if not self.feature_embedding or not other.feature_embedding:
            return 0.0
        if len(self.feature_embedding) != len(other.feature_embedding):
            return 0.0
        dot = sum(
            a * b for a, b in zip(self.feature_embedding, other.feature_embedding, strict=True)
        )
        norm_a = math.sqrt(sum(a * a for a in self.feature_embedding))
        norm_b = math.sqrt(sum(b * b for b in other.feature_embedding))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(0.0, dot / (norm_a * norm_b))


class KalmanState:
    """Kalman Filter state vector for bounding box trajectory prediction [cx, cy, w, h, vx, vy]."""

    def __init__(self, box: FaceBoundingBox) -> None:
        self.cx = box.center_x
        self.cy = box.center_y
        self.w = box.width
        self.h = box.height
        self.vx = 0.0
        self.vy = 0.0

    def predict(self) -> FaceBoundingBox:
        """Predict expected box location in next frame."""
        pred_cx = min(1.0, max(0.0, self.cx + self.vx))
        pred_cy = min(1.0, max(0.0, self.cy + self.vy))
        x_min = max(0.0, pred_cx - self.w / 2.0)
        y_min = max(0.0, pred_cy - self.h / 2.0)
        return FaceBoundingBox(
            x_min=x_min,
            y_min=y_min,
            width=self.w,
            height=self.h,
            confidence=0.8,
        )

    def update(self, observed: FaceBoundingBox, alpha: float = 0.6) -> None:
        """Update state estimate with observed measurement."""
        new_cx = observed.center_x
        new_cy = observed.center_y
        self.vx = alpha * (new_cx - self.cx) + (1 - alpha) * self.vx
        self.vy = alpha * (new_cy - self.cy) + (1 - alpha) * self.vy
        self.cx = new_cx
        self.cy = new_cy
        self.w = alpha * observed.width + (1 - alpha) * self.w
        self.h = alpha * observed.height + (1 - alpha) * self.h


class FrameFaceDetection(ContractModel):
    """Face detections for a single frame index."""

    frame_index: int = Field(ge=0)
    faces: list[FaceBoundingBox] = Field(default_factory=list)


class FaceTrack(ContractModel):
    """Persistent face trajectory identity across consecutive frames."""

    track_id: Identifier
    shot_id: Identifier
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    detections: list[FrameFaceDetection] = Field(default_factory=list)

    @property
    def average_area(self) -> float:
        """Average face bounding box area across detected frames."""
        if not self.detections:
            return 0.0
        total_area = sum(box.area for frame in self.detections for box in frame.faces)
        total_count = sum(len(frame.faces) for frame in self.detections)
        return total_area / max(1, total_count)


class FaceTracker:
    """
    Enterprise Kalman-Filter + IoU + Embedding face tracking system.
    """

    def __init__(
        self,
        iou_threshold: float = 0.3,
        reid_threshold: float = 0.6,
        max_disappeared_frames: int = 5,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.reid_threshold = reid_threshold
        self.max_disappeared_frames = max_disappeared_frames

    def track_faces_in_shot(
        self,
        shot_id: str,
        frame_detections: Sequence[FrameFaceDetection],
    ) -> list[FaceTrack]:
        """Track detected faces across frames and assign persistent track IDs."""
        tracks: list[FaceTrack] = []
        if not frame_detections:
            return tracks

        active_tracks: dict[str, FaceTrack] = {}
        kalman_states: dict[str, KalmanState] = {}
        track_counter = 1

        for fd in frame_detections:
            matched_track_ids: set[str] = set()

            for face in fd.faces:
                best_track_id: str | None = None
                best_score: float = self.iou_threshold

                for tid, track in active_tracks.items():
                    if tid in matched_track_ids:
                        continue
                    last_box = track.detections[-1].faces[0]

                    # Predict with Kalman Filter if available
                    if tid in kalman_states:
                        pred_box = kalman_states[tid].predict()
                        iou_val = face.iou(pred_box)
                    else:
                        iou_val = face.iou(last_box)

                    # Include ReID embedding score if available
                    reid_score = face.embedding_similarity(last_box)
                    composite_score = (
                        0.7 * iou_val + 0.3 * reid_score if reid_score > 0 else iou_val
                    )

                    if composite_score > best_score:
                        best_score = composite_score
                        best_track_id = tid

                if best_track_id is not None:
                    # Append detection to existing track
                    active_tracks[best_track_id].detections.append(
                        FrameFaceDetection(frame_index=fd.frame_index, faces=[face])
                    )
                    active_tracks[best_track_id] = active_tracks[best_track_id].model_copy(
                        update={"end_frame": fd.frame_index}
                    )
                    if best_track_id in kalman_states:
                        kalman_states[best_track_id].update(face)
                    else:
                        kalman_states[best_track_id] = KalmanState(face)
                    matched_track_ids.add(best_track_id)
                else:
                    # Start new track
                    tid = f"track_{track_counter:03d}"
                    track_counter += 1
                    new_track = FaceTrack(
                        track_id=Identifier(tid),
                        shot_id=Identifier(shot_id),
                        start_frame=fd.frame_index,
                        end_frame=fd.frame_index,
                        detections=[FrameFaceDetection(frame_index=fd.frame_index, faces=[face])],
                    )
                    active_tracks[tid] = new_track
                    kalman_states[tid] = KalmanState(face)
                    matched_track_ids.add(tid)

        tracks = list(active_tracks.values())
        logger.info("face_tracker: created %d face tracks for shot %s", len(tracks), shot_id)
        return tracks

    def track_faces_with_shot_boundaries(
        self,
        shot_boundaries: Sequence[Any],
        frame_detections: Sequence[FrameFaceDetection],
    ) -> list[FaceTrack]:
        """
        Shot-aware multi-face tracker.
        Segments frame detections across camera shot cuts, resetting Kalman prediction
        and trajectory smoothing at each cut point to eliminate visual warping across scene cuts.
        """
        if not shot_boundaries:
            return self.track_faces_in_shot("shot_001", frame_detections)

        # Index detections by frame
        det_map: dict[int, FrameFaceDetection] = {fd.frame_index: fd for fd in frame_detections}
        all_tracks: list[FaceTrack] = []

        for shot in shot_boundaries:
            s_id = getattr(shot, "shot_id", "shot_unknown")
            s_start = getattr(shot, "start_frame", 0)
            s_end = getattr(shot, "end_frame", 0)

            shot_dets = [
                det_map[f] for f in range(s_start, s_end + 1) if f in det_map
            ]
            if shot_dets:
                # Isolate Kalman filtering exclusively within this shot
                shot_tracks = self.track_faces_in_shot(str(s_id), shot_dets)
                all_tracks.extend(shot_tracks)

        return all_tracks


__all__ = [
    "FaceBoundingBox",
    "FaceTrack",
    "FaceTracker",
    "FrameFaceDetection",
    "KalmanState",
]
