"""
Unit tests for DubbingEngine integration with Isometric Alignment, RIR Reverb, Broadcast QC, and NLE Interchange.
"""

from __future__ import annotations

import io
import json
import math
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from aidub.pipeline.config import PipelineConfig
from aidub.pipeline.engine import DubbingEngine
from aidub.pipeline.manifest import PipelineManifest, PipelineOutputs


def create_mock_wav(path: Path, duration_s: float = 2.0, fs: int = 48000) -> Path:
    """Generate mock 48kHz audio wav file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)
    samples = 0.5 * np.sin(2.0 * np.pi * 440.0 * t)
    int16_samples = (samples * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(int16_samples.tobytes())
    return path


def test_pipeline_config_studio_defaults() -> None:
    cfg = PipelineConfig(input=Path("test.mp4"), output=Path("out.mp4"))
    assert cfg.isometric_alignment is True
    assert cfg.acoustic_preset == "none"
    assert cfg.broadcast_spec == "netflix"


def test_pipeline_manifest_outputs_include_qc_and_nle() -> None:
    outputs = PipelineOutputs(
        origin_video="in.mp4",
        origin_audio="in.wav",
        dubbed_video="out.mp4",
        qc_certificate_json="qc.json",
        qc_certificate_txt="qc.txt",
        fcpxml_path="project.fcpxml",
        edl_path="project.edl",
    )
    assert outputs.qc_certificate_json == "qc.json"
    assert outputs.fcpxml_path == "project.fcpxml"
    assert outputs.edl_path == "project.edl"


def test_dubbing_engine_qc_and_nle_generation(tmp_path: Path) -> None:
    # Set up mock working directory and assets
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    in_video = tmp_path / "movie.mp4"
    in_video.touch()
    out_video = tmp_path / "movie_bn.mp4"

    cfg = PipelineConfig(
        input=in_video,
        output=out_video,
        work_dir=work_dir,
        tgt_lang="bn",
        isometric_alignment=True,
        acoustic_preset="living_room",
        broadcast_spec="netflix",
    )

    # Mock audio files in work_dir
    dub_vocals = create_mock_wav(work_dir / "dubbed_vocals.wav", duration_s=3.0)
    final_audio = create_mock_wav(work_dir / "dubbed_audio.wav", duration_s=3.0)

    # Test Broadcast QC engine direct generation on final_audio
    from aidub.analysis.broadcast_qc import BroadcastQCEngine, DeliverySpec
    qc_metrics = BroadcastQCEngine.analyze_wav_file(final_audio)
    qc_cert = BroadcastQCEngine.evaluate_compliance(qc_metrics, spec=DeliverySpec.NETFLIX, media_name=out_video.name)

    assert qc_cert.target_spec == DeliverySpec.NETFLIX
    assert isinstance(qc_cert.gain_correction_db, float)

    # Test NLE EDL & FCPXML generation on test dialogue segments
    from aidub.interchange.edl_fcpxml_adapter import EDLFCPXMLAdapter
    from aidub.interchange.otio_adapter import OTIOClip, OTIOTimeline, OTIOTrack
    from aidub.contracts.base import Identifier

    clip = OTIOClip(
        clip_id=Identifier("c1"),
        name="Dialogue_001",
        source_range_start_ms=0,
        source_range_duration_ms=3000,
        media_reference_path=str(dub_vocals),
    )
    track = OTIOTrack(track_id=Identifier("t1"), kind="Audio", clips=[clip])
    timeline = OTIOTimeline(timeline_id=Identifier("tl"), name="Test_Film", frame_rate=24.0, tracks=[track])

    adapter = EDLFCPXMLAdapter()
    edl_out = adapter.export_cmx3600_edl(timeline)
    fcpxml_out = adapter.export_fcpxml(timeline)

    assert "TITLE: TEST_FILM" in edl_out
    assert "<fcpxml" in fcpxml_out
    assert "Dialogue_001" in fcpxml_out
