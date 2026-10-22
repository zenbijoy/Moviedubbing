"""
Comprehensive unit tests for Advanced Mathematical Dubbing and Lip-Sync Engines:
  - Vectorized WSOLA time-stretching with tempo clamping
  - Broadcast dynamic sidechain music ducking with exponential attack/release
  - Active speaker cross-modal Pearson audio-visual correlation disambiguation
  - Shot-boundary isolated Kalman face tracking
  - Subtitle timing re-synchronization
  - Continuous 3D VAD emotional distance and prosody parameter calculation
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from aidub.ai.vision.active_speaker import ActiveSpeakerDetector
from aidub.ai.vision.face_tracker import (
    FaceBoundingBox,
    FaceTracker,
    FrameFaceDetection,
)
from aidub.ai.vision.shot_detector import ShotBoundary
from aidub.ai.voice.emotion_engine import (
    compute_continuous_prosody_params,
    compute_vad_distance,
)
from aidub.media.dsp_engine import VectorizedDspEngine
from aidub.media.mixer_bus import DuckingSettings, SidechainDucker
from aidub.subtitles.bilingual import resync_subtitles_to_fitted_timing


def test_wsola_time_stretch_clamps_and_resizes():
    dsp = VectorizedDspEngine()
    sr = 44100
    # Generate 1.0 second test tone (440 Hz)
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    tone = np.sin(2 * np.pi * 440 * t)

    # 1. Test speeding up by 1.2x (tempo_factor = 1.2)
    sped_up = dsp.process_time_stretch(tone, tempo_factor=1.2, sample_rate=sr)
    expected_len = int(round(sr / 1.2))
    assert abs(sped_up.size - expected_len) <= 100
    assert not np.isnan(sped_up).any()
    assert np.max(np.abs(sped_up)) > 0.1

    # 2. Test slowing down by 0.9x (tempo_factor = 0.9)
    slowed = dsp.process_time_stretch(tone, tempo_factor=0.9, sample_rate=sr)
    expected_len_slow = int(round(sr / 0.9))
    assert abs(slowed.size - expected_len_slow) <= 100

    # 3. Test clamp bounds (e.g., requesting extreme 2.5x gets clamped to 1.35x)
    extreme = dsp.process_time_stretch(tone, tempo_factor=2.5, sample_rate=sr)
    clamped_expected = int(round(sr / 1.35))
    assert abs(extreme.size - clamped_expected) <= 100


def test_dynamic_ducking_attenuates_music_during_speech():
    dsp = VectorizedDspEngine()
    sr = 44100
    n = sr  # 1 second
    music = np.full(n, 0.5, dtype=np.float32)

    # Vocal is loud in middle 0.2s - 0.7s, silent elsewhere
    vocal = np.zeros(n, dtype=np.float32)
    vocal[int(0.2 * sr) : int(0.7 * sr)] = 0.8

    ducked = dsp.process_dynamic_ducking(
        music_samples=music,
        vocal_samples=vocal,
        threshold_db=-30.0,
        duck_db=14.0,
        sample_rate=sr,
    )

    # Music should be untouched during initial silence
    assert math.isclose(ducked[int(0.05 * sr)], 0.5, abs_tol=0.01)

    # Music should be significantly ducked during vocal activity (-14 dB attenuation)
    active_level = float(np.mean(ducked[int(0.35 * sr) : int(0.55 * sr)]))
    expected_active_level = 0.5 * (10.0 ** (-14.0 / 20.0))
    assert math.isclose(active_level, expected_active_level, abs_tol=0.08)


def test_sidechain_ducker_buffer_interface():
    ducker = SidechainDucker(DuckingSettings(enabled=True, duck_reduction_db=12.0))
    sr = 44100
    music = np.ones(sr, dtype=np.float32) * 0.4
    vocal = np.ones(sr, dtype=np.float32) * 0.8

    ducked = ducker.duck_buffers(music, vocal, sample_rate=sr)
    assert ducked.size == sr
    assert float(np.mean(ducked[int(0.3 * sr) : int(0.7 * sr)])) < 0.4


def test_active_speaker_cross_modal_correlation_disambiguation():
    # Setup 10 video frames matching audio
    num_frames = 10
    sr = 16000
    audio = np.zeros(sr, dtype=np.float32)
    # Put speech energy in the first half of the audio
    audio[: sr // 2] = 0.7

    # Face 0 has high mouth motion in first half (speaking)
    face0_boxes = [
        FaceBoundingBox(x_min=0.1, y_min=0.1, width=0.2, height=0.3 if i < 5 else 0.2)
        for i in range(num_frames)
    ]
    # Face 1 is static or moves in second half (listener)
    face1_boxes = [
        FaceBoundingBox(x_min=0.6, y_min=0.1, width=0.2, height=0.2 if i < 5 else 0.3)
        for i in range(num_frames)
    ]

    faces_per_frame = [[face0_boxes[i], face1_boxes[i]] for i in range(num_frames)]

    chosen_face_idx = ActiveSpeakerDetector.disambiguate_active_speaker_face(
        faces_per_frame=faces_per_frame,
        audio_samples=audio,
    )

    assert chosen_face_idx == 0


def test_shot_boundary_isolated_face_tracking():
    tracker = FaceTracker(iou_threshold=0.3)
    shots = [
        ShotBoundary(
            shot_id="shot_1",
            start_frame=0,
            end_frame=2,
            start_ms=0,
            end_ms=100,
            cut_type="hard_cut",
        ),
        ShotBoundary(
            shot_id="shot_2",
            start_frame=3,
            end_frame=5,
            start_ms=100,
            end_ms=200,
            cut_type="hard_cut",
        ),
    ]

    # Frame detections across shot 1 (left side) and shot 2 (right side)
    detections = [
        FrameFaceDetection(
            frame_index=i,
            faces=[
                FaceBoundingBox(
                    x_min=0.1 if i < 3 else 0.8,
                    y_min=0.2,
                    width=0.2,
                    height=0.2,
                )
            ],
        )
        for i in range(6)
    ]

    tracks = tracker.track_faces_with_shot_boundaries(shots, detections)
    # Must produce separate tracks for each shot, not bleed across shot 1 and shot 2
    assert len(tracks) == 2
    assert tracks[0].shot_id == "shot_1"
    assert tracks[1].shot_id == "shot_2"


def test_subtitle_resync_to_fitted_timing():
    segments = [
        {"id": "utt_1", "start": 1.0, "end": 2.5, "text": "Hello", "tgt": "হ্যালো"},
        {"id": "utt_2", "start": 3.0, "end": 4.0, "text": "Friend", "tgt": "বন্ধু"},
    ]
    fitted_durations = {
        "utt_1": 1800,  # 1.8 seconds (expanded from 1.5s)
    }

    resynced = resync_subtitles_to_fitted_timing(segments, fitted_durations)
    assert resynced[0]["start"] == 1.0
    assert resynced[0]["end"] == 2.8  # 1.0 + 1.8s
    assert resynced[1]["start"] == 3.0
    assert resynced[1]["end"] == 4.0


def test_vad_distance_and_continuous_prosody():
    vad_neutral = (0.0, 0.0, 0.0)
    vad_excited = (0.8, 0.8, 0.6)
    dist = compute_vad_distance(vad_neutral, vad_excited)
    assert dist > 0.5

    params = compute_continuous_prosody_params(valence=0.7, arousal=0.8, dominance=0.5)
    assert "+" in params["pitch"]
    assert "+" in params["rate"]
    assert params["volume_db"] > 0
