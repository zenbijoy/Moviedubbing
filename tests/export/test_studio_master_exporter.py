"""
Unit tests for StudioMasterExporter (Feature 5: 1-Click Studio Master Exporter).
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from unittest.mock import patch

from aidub.export.studio_master_exporter import (
    StudioMasterBundleResult,
    StudioMasterExporter,
)
from aidub.pipeline.utterance_store import UtteranceStore


def _make_dummy_wav(path: Path, duration_s: float = 1.0, freq_hz: float = 440.0) -> Path:
    sr = 48000
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(duration_s * sr)):
            val = int(8000 * math.sin(2 * math.pi * freq_hz * (i / sr)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return path


def test_studio_master_bundle_generation(tmp_path: Path) -> None:
    work_dir = tmp_path / "project_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup mock assets
    src_video = work_dir / "input.mp4"
    src_video.write_bytes(b"MOCK_MP4_SOURCE_VIDEO_PAYLOAD")

    dubbed_audio = _make_dummy_wav(work_dir / "dubbed_audio.wav", duration_s=4.0, freq_hz=440.0)
    orig_audio = _make_dummy_wav(work_dir / "vocals.wav", duration_s=4.0, freq_hz=220.0)

    sub_file = work_dir / "bilingual.srt"
    sub_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello friend\nহ্যালো বন্ধু\n", encoding="utf-8"
    )

    # Save utterances in store
    store = UtteranceStore("bn", work_dir)
    store.save_utterances(
        [
            {"start": 1.0, "end": 3.5, "text": "Hello friend", "tgt": "হ্যালো বন্ধু", "speaker": 0},
        ]
    )

    pkg_output_dir = tmp_path / "final_dist_package"

    progress_log: list[tuple[int, str]] = []

    def _progress_cb(pct: int, msg: str) -> None:
        progress_log.append((pct, msg))

    # Mock subprocess.run for ffmpeg dual-audio muxing
    def _mock_run(cmd: list[str], *args: object, **kwargs: object) -> None:
        out_file = Path(cmd[-1])
        out_file.write_bytes(b"MATROSKA_DUAL_AUDIO_VERIFIED_MASTER")

    with patch("subprocess.run", side_effect=_mock_run):
        result: StudioMasterBundleResult = StudioMasterExporter.export_master_bundle(
            work_dir=work_dir,
            output_dir=pkg_output_dir,
            source_video_path=src_video,
            dubbed_audio_path=dubbed_audio,
            original_audio_path=orig_audio,
            subtitle_path=sub_file,
            target_language="bn",
            source_language="en",
            delivery_spec="netflix",
            c2pa_signing_key="studio_test_secret_key_2026",
            progress_cb=_progress_cb,
        )

    # 2. Verify Result and Deliverable Artifacts
    assert result.success is True
    assert result.package_dir == pkg_output_dir
    assert result.total_files >= 6
    assert result.total_size_bytes > 0
    assert len(progress_log) >= 4

    # Dual-audio container
    assert result.dual_audio_mkv_path.is_file()
    assert result.dual_audio_mkv_path.name == "master_dual_audio_bn.mkv"

    # Certified Broadcast QC
    assert result.qc_certificate_json_path.is_file()
    assert result.qc_certificate_txt_path.is_file()
    qc_data = json.loads(result.qc_certificate_json_path.read_text(encoding="utf-8"))
    assert "integrated_lufs" in qc_data
    assert "true_peak_dbtp" in qc_data
    assert qc_data["spec"] == "netflix"

    # NLE Interchange
    assert result.fcpxml_path.is_file()
    assert result.edl_path.is_file()
    fcpxml_text = result.fcpxml_path.read_text(encoding="utf-8")
    assert "<fcpxml" in fcpxml_text
    assert "Bengali" in fcpxml_text or "bn" in fcpxml_text
    edl_text = result.edl_path.read_text(encoding="utf-8")
    assert "001" in edl_text

    # C2PA Provenance Manifest
    assert result.c2pa_manifest_path.is_file()
    c2pa_json = json.loads(result.c2pa_manifest_path.read_text(encoding="utf-8"))
    assert "digital_signature_sha256" in c2pa_json
    assert len(c2pa_json["digital_signature_sha256"]) == 64

    # Packaging Inventory Manifest
    assert result.package_manifest_path.is_file()
    pkg_manifest = json.loads(result.package_manifest_path.read_text(encoding="utf-8"))
    assert pkg_manifest["target_language"] == "bn"
    assert len(pkg_manifest["files"]) >= 6
    for file_entry in pkg_manifest["files"]:
        assert "filename" in file_entry
        assert "sha256" in file_entry
        assert len(file_entry["sha256"]) == 64
