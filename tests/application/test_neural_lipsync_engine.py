"""
Unit & Integration Test Suite for Neural AI Lip-Sync & Face Synthesis Engine.

Verifies:
  - 80-band log-Mel spectrogram feature extraction and temporal slicing.
  - Face cropping, lower-face mouth ROI, and Gaussian feather mask generation.
  - Bilinear optical deformation synthesis driven by speech acoustics.
  - Temporal smoothing filter across video frames.
  - End-to-end video frame render sequence conforming to Zero Mock DSP.
  - Studio Dialog UI, telemetry tracking, auditioning, and signal emissions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aidub.application.lipsync.neural_lipsync_engine import (
    FaceMaskAndFeatheringEngine,
    MelSpectrogramExtractor,
    NeuralLipSyncEngine,
    TemporalSmoothingFilter,
)
from aidub.domain.neural_lipsync import (
    FaceBBox,
    LipSyncConfig,
    LipSyncRenderProgress,
    LipSyncResult,
    NeuralModelType,
)
from aidub.media.pro_audio_editor import AudioClipData
from aidub.ui.dialogs.neural_lipsync_studio_dialog import NeuralLipSyncStudioDialog

try:
    from PySide6.QtWidgets import QApplication

    _QT = True
except ImportError:
    _QT = False


@pytest.fixture(autouse=True)
def qapp() -> Any:
    if _QT:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    return None


def test_mel_spectrogram_extractor_shape_and_range() -> None:
    extractor = MelSpectrogramExtractor(sample_rate=16000, n_fft=800, hop_size=200, n_mels=80)
    clip = AudioClipData.synthesize_speech_like(duration=1.0, sample_rate=16000)

    mel = extractor.extract(clip.samples, clip.sample_rate)
    assert mel.shape[0] == 80
    assert mel.shape[1] > 20
    assert np.isfinite(mel).all()

    # Slice chunk
    chunk = extractor.get_frame_mel_chunk(mel, frame_idx=5, fps=25.0, mel_step_size=16)
    assert chunk.shape == (80, 16)
    assert np.isfinite(chunk).all()


def test_face_mask_and_feathering() -> None:
    mask = FaceMaskAndFeatheringEngine.create_feather_mask(size=96, radius_px=10)
    assert mask.shape == (96, 96, 1)
    assert 0.0 <= mask.min() <= mask.max() <= 1.0
    # Mouth center should have high alpha weight
    assert mask[int(96 * 0.72), 48, 0] > 0.8
    # Outer top border should be zero
    assert mask[5, 5, 0] < 0.05

    # Crop and align face
    frame = np.full((200, 300, 3), 128, dtype=np.uint8)
    bbox = FaceBBox(x=50, y=30, w=100, h=120)
    face_crop, aligned_bbox = FaceMaskAndFeatheringEngine.crop_and_align_face(frame, bbox, target_size=96)
    assert face_crop.shape == (96, 96, 3)
    assert aligned_bbox.w == 100
    assert aligned_bbox.h == 120


def test_temporal_smoothing_filter() -> None:
    filter_ = TemporalSmoothingFilter(alpha=0.5)
    s1 = np.array([0.0, 0.0], dtype=np.float32)
    s2 = np.array([1.0, 1.0], dtype=np.float32)

    r1 = filter_.smooth(s1)
    np.testing.assert_allclose(r1, [0.0, 0.0])

    # Step response should be smoothed to 0.5
    r2 = filter_.smooth(s2)
    np.testing.assert_allclose(r2, [0.5, 0.5])


def test_neural_lipsync_synthesis_warp() -> None:
    engine = NeuralLipSyncEngine()
    face_crop = np.full((96, 96, 3), 180, dtype=np.uint8)
    mel_chunk = np.zeros((80, 16), dtype=np.float32)
    # Simulate speech formant energy
    mel_chunk[10:30, :] = -0.5
    mask = FaceMaskAndFeatheringEngine.create_feather_mask(size=96, radius_px=8)

    warped = engine.synthesize_face_warp(face_crop, mel_chunk, mask)
    assert warped.shape == (96, 96, 3)
    assert warped.dtype == np.uint8


def test_neural_lipsync_render_sequence_full_pipeline() -> None:
    config = LipSyncConfig(fps=25.0, crop_size=96, feather_radius_px=10)
    engine = NeuralLipSyncEngine(config=config)

    # 10 test frames
    frames = [np.full((120, 160, 3), 50, dtype=np.uint8) for _ in range(10)]
    clip = AudioClipData.synthesize_speech_like(duration=0.4, sample_rate=16000)

    progress_reports: list[LipSyncRenderProgress] = []

    def on_progress(p: LipSyncRenderProgress) -> None:
        progress_reports.append(p)

    result = engine.render_sequence(
        frames=frames,
        audio_clip=clip,
        progress_callback=on_progress,
    )

    assert result.total_frames == 10
    assert result.duration_s == 0.4
    assert result.average_lse_c >= 6.0
    assert result.average_lse_d <= 7.5
    assert result.output_path.exists()
    assert len(progress_reports) == 10
    assert progress_reports[-1].percent_complete == 100.0


def test_neural_lipsync_studio_dialog_ui_and_signals() -> None:
    if not _QT:
        pytest.skip("PySide6 required")

    clip = AudioClipData.synthesize_speech_like(duration=0.5, sample_rate=16000)
    frames = [np.full((120, 160, 3), 50, dtype=np.uint8) for _ in range(6)]
    dlg = NeuralLipSyncStudioDialog(audio_clip=clip, video_frames=frames)

    assert dlg.combo_model.count() >= 3

    # Switch model architecture
    dlg.combo_model.setCurrentIndex(1)
    assert dlg.config.model_type == NeuralModelType.MUSETALK
    assert dlg.config.crop_size == 256
    assert "MuseTalk" in dlg.lbl_badge.text()

    # Switch back to Wav2Lip
    dlg.combo_model.setCurrentIndex(0)
    assert dlg.config.model_type == NeuralModelType.WAV2LIP

    # Audition audio
    dlg._audition_audio()
    assert "Auditioning" in dlg.lbl_status.text()

    # Run neural rendering sequence
    dlg._run_render()
    assert dlg.result is not None
    assert dlg.result.total_frames == 6
    assert dlg.btn_apply.isEnabled() is True
    assert dlg.prog_bar.value() == 100

    # Test Apply to Timeline signal
    emitted: list[LipSyncResult] = []
    dlg.lipsync_applied.connect(emitted.append)
    dlg._apply_to_timeline()
    assert len(emitted) == 1
    assert emitted[0].total_frames == 6
