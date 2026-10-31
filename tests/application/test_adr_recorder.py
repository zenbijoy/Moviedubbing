"""
Unit tests for AdrRecorderService.
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.application.audio.adr_recorder import AdrRecorderService
from aidub.media.pro_audio_editor import AudioClipData


def test_adr_take_registration_and_selection(tmp_path: pytest.TempPathFactory) -> None:
    service = AdrRecorderService(storage_dir=tmp_path)

    sr = 48000
    clip1 = AudioClipData(samples=np.ones(sr, dtype=np.float32) * 0.1, sample_rate=sr)
    clip2 = AudioClipData(samples=np.ones(sr, dtype=np.float32) * 0.2, sample_rate=sr)

    take1 = service.register_take("cue_A", clip1, notes="First take", auto_select=True)
    take2 = service.register_take("cue_A", clip2, notes="Second take", auto_select=False)

    lane = service.get_or_create_lane("cue_A")
    assert len(lane.takes) == 2
    assert lane.active_take_id == take1.take_id

    # Switch active take to take 2
    success = service.select_active_take("cue_A", take2.take_id)
    assert success
    assert lane.active_take_id == take2.take_id
    assert take2.is_selected
    assert not take1.is_selected


def test_adr_comping_assembly_with_crossfades(tmp_path: pytest.TempPathFactory) -> None:
    service = AdrRecorderService(storage_dir=tmp_path)

    sr = 48000
    # Take 1 has constant 0.3, Take 2 has constant 0.6
    clip1 = AudioClipData(samples=np.full(sr, 0.3, dtype=np.float32), sample_rate=sr)
    clip2 = AudioClipData(samples=np.full(sr, 0.6, dtype=np.float32), sample_rate=sr)

    t1 = service.register_take("cue_B", clip1)
    t2 = service.register_take("cue_B", clip2)

    # Comp 0.0s to 0.4s from Take 1, and 0.4s to 0.8s from Take 2
    service.add_comping_region("cue_B", t1.take_id, start_s=0.0, end_s=0.4, crossfade_s=0.01)
    service.add_comping_region("cue_B", t2.take_id, start_s=0.4, end_s=0.8, crossfade_s=0.01)

    comped = service.assemble_comped_take("cue_B")
    assert comped.sample_rate == sr
    # Total comped duration should be approx 0.8s (0.4 + 0.4)
    assert comped.duration_s == pytest.approx(0.8, abs=0.05)
    assert comped.samples.size > 0
