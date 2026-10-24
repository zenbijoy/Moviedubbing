"""
Unit tests for Selective Face-Gated Lip-Sync Pipeline Engine.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from aidub.media.selective_lipsync import (
    SelectiveFaceGateLipSyncEngine,
)


def test_merge_speech_intervals() -> None:
    engine = SelectiveFaceGateLipSyncEngine(min_interval_duration_s=0.3, merge_gap_s=0.5)

    raw_segments = [
        {"start": 1.0, "end": 2.5, "speaker": "SPEAKER_00"},
        {"start": 2.8, "end": 4.0, "speaker": "SPEAKER_00"},  # Gap = 0.3s (merged with prev)
        {"start": 7.0, "end": 8.0, "speaker": "SPEAKER_01"},  # Gap = 3.0s (distinct)
        {"start": 10.0, "end": 10.1, "speaker": "SPEAKER_00"},  # 0.1s < min 0.3s (filtered out)
    ]

    merged = engine.merge_speech_intervals(raw_segments, total_duration_s=20.0)

    assert len(merged) == 2
    # First merged interval spans 1.0s to 4.0s
    assert merged[0].start_s == 1.0
    assert merged[0].end_s == 4.0
    assert pytest.approx(merged[0].duration_s, 0.01) == 3.0

    # Second interval spans 7.0s to 8.0s
    assert merged[1].start_s == 7.0
    assert merged[1].end_s == 8.0


def test_selective_lipsync_no_intervals_returns_fallback(tmp_path: Path) -> None:
    engine = SelectiveFaceGateLipSyncEngine()

    vid = Path("clip.mp4")
    aud = tmp_path / "dub.wav"
    out_vid = tmp_path / "out_synced.mp4"

    # Synthetic audio
    sr = 44100
    sf.write(aud, np.zeros(sr * 2, dtype=np.float32), sr)

    if vid.is_file():
        report = engine.run_selective_lipsync(
            source_video_path=vid,
            dubbed_audio_path=aud,
            speech_segments=[],
            output_video_path=out_vid,
            work_dir=tmp_path,
        )

        assert report.total_speech_intervals == 0
        assert report.compute_savings_percent == 100.0
        assert Path(report.output_video_path).is_file()
