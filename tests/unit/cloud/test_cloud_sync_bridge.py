"""
Unit tests for CloudSyncEngine, ColabLiveWebhookServer, and Kaggle/Colab Live Synchronization.
"""

from __future__ import annotations

import json
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from aidub.cloud.cloud_sync_bridge import (
    CloudSyncEngine,
    CloudSyncResult,
    ColabLiveWebhookServer,
)
from aidub.cloud.kaggle_accelerator import KaggleClient, KaggleCredentials
from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_colab_input_bundle_packaging(tmp_path: Path) -> None:
    work_dir = tmp_path / "project_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    movie_path = work_dir / "sample_scene.mp4"
    movie_path.write_bytes(b"TEST_MOVIE_HEADER_PAYLOAD")

    segments_path = work_dir / "asr_segments.json"
    segments_path.write_text(json.dumps([{"start": 0.0, "end": 2.0, "text": "Hello"}]), encoding="utf-8")

    ref_dir = work_dir / "speaker_references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "speaker_00.wav").write_bytes(b"RIFF_FAKE_WAV_BYTES")

    bundle_zip = CloudSyncEngine.create_colab_input_bundle(
        work_dir=work_dir,
        movie_path=movie_path,
        target_language="bn",
        voice_engine="rvc_v2",
    )

    assert bundle_zip.is_file()
    assert zipfile.is_zipfile(bundle_zip)

    with zipfile.ZipFile(bundle_zip, "r") as z:
        names = z.namelist()
        assert "project_meta.json" in names
        assert "sample_scene.mp4" in names
        assert "asr_segments.json" in names
        assert "speaker_references/speaker_00.wav" in names

        meta = json.loads(z.read("project_meta.json").decode("utf-8"))
        assert meta["target_language"] == "bn"
        assert meta["voice_engine"] == "rvc_v2"


def test_import_cloud_output_bundle(tmp_path: Path) -> None:
    work_dir = tmp_path / "destination_project"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy cloud output ZIP
    zip_path = tmp_path / "aidub_cloud_master_bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("dubbed_master.mp4", b"MP4_VIDEO_BYTES")
        z.writestr("dubbed_audio.wav", b"WAV_AUDIO_BYTES")
        z.writestr("bilingual.srt", "1\n00:00:01,000 --> 00:00:03,000\nHello\nহ্যালো\n")
        z.writestr("asr_segments.json", json.dumps([{"start": 1.0, "end": 3.0, "text": "Hello"}]))

    res: CloudSyncResult = CloudSyncEngine.import_cloud_output_bundle(
        bundle_path_or_dir=zip_path,
        project_work_dir=work_dir,
    )

    assert res.success is True
    assert res.total_files >= 4
    assert res.dubbed_video_path is not None
    assert res.dubbed_video_path.name == "dubbed_master.mp4"
    assert res.dubbed_audio_path is not None
    assert res.dubbed_audio_path.name == "dubbed_audio.wav"
    assert res.subtitle_path is not None
    assert res.subtitle_path.name == "bilingual.srt"

    # Verify promoted to standard project paths
    assert (work_dir / "dubbed_audio.wav").is_file()
    assert (work_dir / "bilingual.srt").is_file()


def test_poll_and_sync_kaggle_job_success(tmp_path: Path) -> None:
    work_dir = tmp_path / "kaggle_proj"
    work_dir.mkdir(parents=True, exist_ok=True)

    creds = KaggleCredentials("testuser", "testkey123")
    client = KaggleClient(creds)

    # Mock client methods
    status_sequence = ["running", "complete"]
    def _mock_get_status(slug: str) -> tuple[str, str]:
        return status_sequence.pop(0), "OK"

    def _mock_download(slug: str, dest_dir: Path) -> list[Path]:
        out_v = dest_dir / "dubbed_master.mp4"
        out_v.write_bytes(b"KAGGLE_MASTER_VIDEO")
        out_a = dest_dir / "dubbed_audio.wav"
        out_a.write_bytes(b"KAGGLE_MASTER_AUDIO")
        return [out_v, out_a]

    progress_ticks: list[tuple[int, str]] = []
    def _cb(pct: int, msg: str) -> None:
        progress_ticks.append((pct, msg))

    with patch.object(client, "get_kernel_status", side_effect=_mock_get_status), \
         patch.object(client, "download_kernel_output", side_effect=_mock_download):

        res = CloudSyncEngine.poll_and_sync_kaggle_job(
            client=client,
            kernel_slug="aidub-movie-test",
            project_work_dir=work_dir,
            max_wait_seconds=10,
            poll_interval_seconds=0,
            progress_cb=_cb,
        )

        assert res.success is True
        assert res.dubbed_video_path is not None
        assert res.dubbed_audio_path is not None
        assert len(progress_ticks) >= 1


def test_colab_live_webhook_server(tmp_path: Path) -> None:
    work_dir = tmp_path / "webhook_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    received_bundles: list[CloudSyncResult] = []
    def _on_received(res: CloudSyncResult) -> None:
        received_bundles.append(res)

    port = 8991
    server = ColabLiveWebhookServer(
        target_work_dir=work_dir,
        port=port,
        on_bundle_received=_on_received,
    )

    started = server.start()
    assert started is True
    assert server.is_running is True

    try:
        # 1. Test Health endpoint
        health_req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(health_req, timeout=3.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
            assert data["status"] == "ready"

        # 2. Test Unauthorized POST
        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/colab/sync",
            data=b"DUMMY_ZIP_DATA",
            headers={"X-AIDub-Token": "INVALID_TOKEN"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_req, timeout=3.0)  # noqa: S310
        assert exc_info.value.code == 403

        # 3. Test Authorized POST with valid ZIP payload
        zip_buf_path = tmp_path / "payload.zip"
        with zipfile.ZipFile(zip_buf_path, "w") as z:
            z.writestr("dubbed_master.mp4", b"COLAB_LIVE_VIDEO_STREAM")
            z.writestr("dubbed_audio.wav", b"COLAB_LIVE_AUDIO_STREAM")

        valid_payload = zip_buf_path.read_bytes()
        good_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/colab/sync",
            data=valid_payload,
            headers={
                "X-AIDub-Token": server.auth_token,
                "Content-Type": "application/zip",
            },
            method="POST",
        )
        with urllib.request.urlopen(good_req, timeout=5.0) as resp:  # noqa: S310
            resp_json = json.loads(resp.read().decode())
            assert resp_json["status"] == "success"

        assert len(received_bundles) == 1
        assert received_bundles[0].dubbed_video_path is not None
        assert (work_dir / "dubbed_audio.wav").is_file()

    finally:
        server.stop()
        assert server.is_running is False


def test_kaggle_accelerator_dialog_auto_sync_lifecycle(qapp, tmp_path: Path) -> None:
    movie_file = tmp_path / "scene.mp4"
    movie_file.write_bytes(b"MOVIE_CONTENT")

    dlg = KaggleAcceleratorDialog(
        movie_path=str(movie_file),
        target_language="bn",
        voice_engine="rvc_v2",
    )

    assert hasattr(dlg, "colab_pack_btn")
    assert hasattr(dlg, "import_colab_btn")
    assert hasattr(dlg, "webhook_toggle_btn")
    assert dlg.get_sync_result() is None

    # Test Colab Input Pack button
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        dlg._pack_colab_input()
    assert (tmp_path / "aidub_colab_input.zip").is_file()
