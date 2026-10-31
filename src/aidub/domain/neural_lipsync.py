"""
Domain contracts and data models for Neural AI Lip-Sync & Face Synthesis.

Covers:
  - Bounding boxes and facial landmark anchors for mouth ROI extraction.
  - Model configuration presets (Wav2Lip, MuseTalk, LatentSync).
  - Real-time progress telemetry and evaluation metrics (LSE-C, LSE-D).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class NeuralModelType(str, enum.Enum):
    WAV2LIP = "wav2lip"
    MUSETALK = "musetalk"
    LATENTSYNC = "latentsync"


@dataclass
class FaceBBox:
    """Bounding box coordinates for face and lower-half mouth ROI."""

    x: int = 0
    y: int = 0
    w: int = 128
    h: int = 128
    confidence: float = 1.0

    @property
    def mouth_roi(self) -> tuple[int, int, int, int]:
        """Returns lower-half mouth region: (x, mouth_y, w, mouth_h)."""
        mouth_y = self.y + int(self.h * 0.55)
        mouth_h = int(self.h * 0.45)
        return (self.x, mouth_y, self.w, mouth_h)


@dataclass
class LipSyncConfig:
    """Hyperparameters and configuration for neural lip-sync synthesis."""

    model_type: NeuralModelType = NeuralModelType.WAV2LIP
    fps: float = 25.0
    crop_size: int = 96
    feather_radius_px: int = 12
    temporal_smoothing_factor: float = 0.35
    aperture_scale: float = 1.0
    sync_offset_ms: float = 0.0
    mel_step_size: int = 16
    device: str = "cpu"
    sample_rate: int = 16000


@dataclass
class LipSyncRenderProgress:
    """Frame-by-frame progress telemetry during neural synthesis."""

    current_frame: int = 0
    total_frames: int = 0
    fps_rendered: float = 0.0
    eta_seconds: float = 0.0
    status_message: str = ""

    @property
    def percent_complete(self) -> float:
        if self.total_frames <= 0:
            return 0.0
        return min(100.0, (self.current_frame / self.total_frames) * 100.0)


@dataclass
class LipSyncResult:
    """Final output from neural lip-sync generation."""

    output_path: Path
    total_frames: int
    duration_s: float
    average_lse_c: float = 7.5  # Lip-Sync Error - Confidence (higher is better, >= 6.0 is good)
    average_lse_d: float = 6.2  # Lip-Sync Error - Distance (lower is better, <= 7.5 is good)
    model_used: str = "Wav2Lip-ONNX"
    metadata: dict[str, Any] = field(default_factory=dict)
