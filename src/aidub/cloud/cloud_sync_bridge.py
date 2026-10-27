"""
Cloud GPU Synchronization Bridge & Remote Execution Manager.

Enables bidirectional synchronization between AIDub Studio desktop and free cloud GPUs:
  1. Kaggle GPU (NVIDIA T4 x2 / P100): Remote kernel job dispatch, automated polling,
     and seamless artifact downloading via Kaggle REST API v1.
  2. Google Colab Free T4 GPU: 1-Click project bundle preparation, automated deliverable
     import (.zip / Google Drive folder), and optional secure HTTP webhook receiver
     (http://localhost:8976/api/colab/sync) for automatic live sync.
"""

from __future__ import annotations

import http.server
import json
import logging
import secrets
import shutil
import socketserver
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidub.cloud.kaggle_accelerator import KaggleClient

logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_PORT = 8976


@dataclass
class CloudSyncJob:
    """Represents a tracked cloud GPU execution job."""

    job_id: str
    platform: str  # "kaggle" | "colab"
    target_language: str
    status: str  # "queued" | "running" | "completed" | "failed" | "synced"
    progress_percent: int
    message: str
    remote_url: str
    downloaded_files: list[str] = field(default_factory=list)
    project_work_dir: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


@dataclass
class CloudSyncResult:
    """Summary of downloaded and imported deliverables."""

    success: bool
    job_id: str
    platform: str
    dubbed_video_path: Path | None
    dubbed_audio_path: Path | None
    subtitle_path: Path | None
    utterances_path: Path | None
    total_files: int
    total_bytes: int
    error_message: str | None = None


class CloudSyncEngine:
    """
    Core orchestrator managing cloud execution lifecycle, polling, and workspace ingestion.
    """

    @classmethod
    def create_colab_input_bundle(
        cls,
        *,
        work_dir: Path | str,
        movie_path: Path | str,
        target_language: str = "bn",
        voice_engine: str = "rvc_v2",
        output_zip: Path | str | None = None,
    ) -> Path:
        """
        Package input project assets into a clean ZIP bundle for fast upload into Google Colab.
        """
        w_dir = Path(work_dir)
        m_path = Path(movie_path)
        out_zip = Path(output_zip) if output_zip else (w_dir / "aidub_colab_input.zip")
        out_zip.parent.mkdir(parents=True, exist_ok=True)

        meta = {
            "source_movie_name": m_path.name,
            "target_language": target_language,
            "voice_engine": voice_engine,
            "created_at": time.time(),
        }

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project_meta.json", json.dumps(meta, indent=2))
            if m_path.is_file() and m_path.stat().st_size < 100 * 1024 * 1024:
                # Include small video directly if < 100MB
                z.write(m_path, arcname=m_path.name)

            # Include existing speaker references or segments if present
            ref_dir = w_dir / "speaker_references"
            if ref_dir.is_dir():
                for ref_f in ref_dir.glob("*.wav"):
                    z.write(ref_f, arcname=f"speaker_references/{ref_f.name}")

            asr_json = w_dir / "asr_segments.json"
            if asr_json.is_file():
                z.write(asr_json, arcname="asr_segments.json")

        logger.info("Created Colab input bundle at %s (%d bytes)", out_zip, out_zip.stat().st_size)
        return out_zip

    @classmethod
    def import_cloud_output_bundle(
        cls,
        bundle_path_or_dir: Path | str,
        project_work_dir: Path | str,
    ) -> CloudSyncResult:
        """
        Unpack and link cloud-rendered deliverables into the active project workspace.
        Accepts either a .zip archive or an extracted folder.
        """
        src = Path(bundle_path_or_dir)
        w_dir = Path(project_work_dir)
        w_dir.mkdir(parents=True, exist_ok=True)
        sync_dir = w_dir / "cloud_sync"
        sync_dir.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            return CloudSyncResult(
                success=False,
                job_id="import_error",
                platform="unknown",
                dubbed_video_path=None,
                dubbed_audio_path=None,
                subtitle_path=None,
                utterances_path=None,
                total_files=0,
                total_bytes=0,
                error_message=f"Bundle path does not exist: {src}",
            )

        extracted_files: list[Path] = []
        if src.is_file() and zipfile.is_zipfile(src):
            with zipfile.ZipFile(src, "r") as z:
                z.extractall(sync_dir)
                for name in z.namelist():
                    extracted_files.append(sync_dir / name)
        elif src.is_dir():
            for item in src.iterdir():
                dest_f = sync_dir / item.name
                if item.is_file():
                    if item.resolve() != dest_f.resolve():
                        shutil.copy2(item, dest_f)
                    extracted_files.append(dest_f)
        else:
            # Single file imported directly
            dest_f = sync_dir / src.name
            if src.resolve() != dest_f.resolve():
                shutil.copy2(src, dest_f)
            extracted_files.append(dest_f)

        # Identify key deliverables
        dubbed_video: Path | None = None
        dubbed_audio: Path | None = None
        subtitle_file: Path | None = None
        utterances_file: Path | None = None

        total_bytes = 0
        for f in extracted_files:
            if not f.is_file():
                continue
            total_bytes += f.stat().st_size
            fname_lower = f.name.lower()
            if fname_lower.endswith((".mp4", ".mkv", ".mov")) and not dubbed_video:
                dubbed_video = f
            elif fname_lower.endswith((".wav", ".mp3", ".flac", ".m4a")) and (
                "dubbed" in fname_lower or "master" in fname_lower or not dubbed_audio
            ):
                dubbed_audio = f
            elif fname_lower.endswith((".srt", ".vtt", ".ass")) and not subtitle_file:
                subtitle_file = f
            elif (
                fname_lower.endswith(".json")
                and ("asr" in fname_lower or "segment" in fname_lower or "utterance" in fname_lower)
                and not utterances_file
            ):
                utterances_file = f

        # If audio found, promote to standard project locations if not already there
        target_audio = w_dir / "dubbed_audio.wav"
        if dubbed_audio and dubbed_audio.resolve() != target_audio.resolve():
            try:
                shutil.copy2(dubbed_audio, target_audio)
            except Exception as exc:
                logger.warning("Could not copy dubbed audio to standard location: %s", exc)

        target_sub = w_dir / "bilingual.srt"
        if subtitle_file and subtitle_file.resolve() != target_sub.resolve():
            try:
                shutil.copy2(subtitle_file, target_sub)
            except Exception as exc:
                logger.warning("Could not copy subtitles to standard location: %s", exc)

        target_asr = w_dir / "asr_segments.json"
        if utterances_file and utterances_file.resolve() != target_asr.resolve():
            try:
                shutil.copy2(utterances_file, target_asr)
            except Exception as exc:
                logger.warning("Could not copy segments to standard location: %s", exc)

        logger.info(
            "Cloud output bundle imported: %d files (%d bytes), video=%s, audio=%s, sub=%s",
            len(extracted_files),
            total_bytes,
            dubbed_video.name if dubbed_video else None,
            dubbed_audio.name if dubbed_audio else None,
            subtitle_file.name if subtitle_file else None,
        )

        return CloudSyncResult(
            success=True,
            job_id=f"cloud_sync_{int(time.time())}",
            platform="colab" if "colab" in src.name.lower() else "kaggle",
            dubbed_video_path=dubbed_video,
            dubbed_audio_path=dubbed_audio,
            subtitle_path=subtitle_file,
            utterances_path=utterances_file,
            total_files=len(extracted_files),
            total_bytes=total_bytes,
        )

    @classmethod
    def poll_and_sync_kaggle_job(
        cls,
        client: KaggleClient,
        kernel_slug: str,
        project_work_dir: Path | str,
        *,
        max_wait_seconds: int = 14400,
        poll_interval_seconds: int = 10,
        progress_cb: Callable[[int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> CloudSyncResult:
        """
        Poll Kaggle kernel status until completed, then automatically download and import outputs.
        """
        w_dir = Path(project_work_dir)
        start_t = time.time()
        logger.info("Starting polling for Kaggle kernel '%s'...", kernel_slug)

        while True:
            if should_cancel and should_cancel():
                logger.info("Polling canceled by user for %s", kernel_slug)
                return CloudSyncResult(
                    success=False,
                    job_id=kernel_slug,
                    platform="kaggle",
                    dubbed_video_path=None,
                    dubbed_audio_path=None,
                    subtitle_path=None,
                    utterances_path=None,
                    total_files=0,
                    total_bytes=0,
                    error_message="Canceled by user",
                )

            status, msg = client.get_kernel_status(kernel_slug)
            logger.debug("Kaggle kernel '%s' status: %s (%s)", kernel_slug, status, msg)

            if status == "complete":
                if progress_cb:
                    progress_cb(
                        90, "Kaggle GPU finished! Downloading rendered master deliverables..."
                    )
                dest_dir = w_dir / "cloud_sync"
                dest_dir.mkdir(parents=True, exist_ok=True)
                downloaded = client.download_kernel_output(kernel_slug, dest_dir)
                if progress_cb:
                    progress_cb(
                        98, f"Downloaded {len(downloaded)} items. Importing into project..."
                    )

                return cls.import_cloud_output_bundle(dest_dir, w_dir)

            if status in ("error", "failed", "cancelacknowledged"):
                err_text = f"Kaggle kernel execution failed: {msg or status}"
                logger.error(err_text)
                return CloudSyncResult(
                    success=False,
                    job_id=kernel_slug,
                    platform="kaggle",
                    dubbed_video_path=None,
                    dubbed_audio_path=None,
                    subtitle_path=None,
                    utterances_path=None,
                    total_files=0,
                    total_bytes=0,
                    error_message=err_text,
                )

            elapsed = time.time() - start_t
            if elapsed > max_wait_seconds:
                return CloudSyncResult(
                    success=False,
                    job_id=kernel_slug,
                    platform="kaggle",
                    dubbed_video_path=None,
                    dubbed_audio_path=None,
                    subtitle_path=None,
                    utterances_path=None,
                    total_files=0,
                    total_bytes=0,
                    error_message=f"Timed out after {max_wait_seconds} seconds waiting for Kaggle GPU",
                )

            if progress_cb:
                mins, secs = divmod(int(elapsed), 60)
                pct = min(88, int(12 + (elapsed / 600.0) * 73))
                progress_cb(
                    pct,
                    f"Kaggle GPU Status: {status.upper()} [{mins:02d}m {secs:02d}s elapsed] (Running Whisper Large-v3 & Stems)...",
                )

            time.sleep(poll_interval_seconds)


class ColabLiveWebhookServer:
    """
    Lightweight background HTTP bridge server receiving direct output bundles
    from Google Colab GPU runtimes.
    """

    def __init__(
        self,
        target_work_dir: Path | str,
        port: int = DEFAULT_BRIDGE_PORT,
        on_bundle_received: Callable[[CloudSyncResult], None] | None = None,
    ) -> None:
        self.work_dir = Path(target_work_dir)
        self.port = port
        self.on_bundle_received = on_bundle_received
        self.auth_token = secrets.token_hex(16)
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        """Start the background HTTP receiver."""
        if self._is_running:
            return True

        bridge_self = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                logger.debug(format, *args)

            def do_GET(self) -> None:
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"status": "ready", "engine": "AIDub Colab Bridge"}).encode()
                    )
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:
                content_len = int(self.headers.get("Content-Length", 0))
                # Validate token in headers
                token = self.headers.get("X-AIDub-Token", "")
                if token != bridge_self.auth_token:
                    if content_len > 0:
                        _ = self.rfile.read(content_len)
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"Unauthorized token")
                    return

                if self.path == "/api/colab/sync":
                    content_len = int(self.headers.get("Content-Length", 0))
                    if content_len <= 0:
                        self.send_response(400)
                        self.end_headers()
                        return

                    payload = self.rfile.read(content_len)
                    sync_dir = bridge_self.work_dir / "cloud_sync"
                    sync_dir.mkdir(parents=True, exist_ok=True)
                    zip_path = sync_dir / f"colab_live_bundle_{int(time.time())}.zip"
                    zip_path.write_bytes(payload)

                    res = CloudSyncEngine.import_cloud_output_bundle(zip_path, bridge_self.work_dir)
                    if bridge_self.on_bundle_received:
                        bridge_self.on_bundle_received(res)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(
                            {
                                "status": "success",
                                "files_imported": res.total_files,
                                "bytes": res.total_bytes,
                            }
                        ).encode()
                    )
                    return

                self.send_response(404)
                self.end_headers()

        try:
            # Allow port reuse
            socketserver.TCPServer.allow_reuse_address = True
            self._server = socketserver.TCPServer(("127.0.0.1", self.port), _Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self._is_running = True
            logger.info(
                "Colab Live Webhook Server active on http://127.0.0.1:%d/api/colab/sync", self.port
            )
            return True
        except Exception as exc:
            logger.warning("Could not start Colab Webhook Server on port %d: %s", self.port, exc)
            self._is_running = False
            return False

    def stop(self) -> None:
        """Stop the background listener."""
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as exc:
                logger.warning("Error stopping webhook server: %s", exc)
        self._is_running = False
        self._server = None
        self._thread = None
        logger.info("Colab Live Webhook Server stopped.")


__all__ = [
    "DEFAULT_BRIDGE_PORT",
    "CloudSyncEngine",
    "CloudSyncJob",
    "CloudSyncResult",
    "ColabLiveWebhookServer",
]
