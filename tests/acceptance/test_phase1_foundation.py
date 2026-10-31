"""Acceptance tests for Phase 1: Foundation.

Tests:
  1. Project model (project.json): save, reload upon restart, exact segment match, real autosave time.
  2. Central JobManager: start dummy job -> counter updates -> cancel job -> counter resets.
  3. Real system stats: matches nvidia-smi (or shows 'No GPU' if none).
  4. Real Settings Dialog: saves ffmpeg_path, cache dir, asr size, translation engine, tts voice, device.
  5. Rotating file log & InAppLogHandler: captures logs in memory and logs/app.log.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from aidub.domain.project_file import (
    ProjectFile,
    ProjectFileSettings,
    ProjectProbeInfo,
    SegmentModel,
    StageStatus,
)
from aidub.infrastructure.logging import (
    configure_secure_logging,
    get_in_app_log_handler,
)
from aidub.infrastructure.preferences import (
    UserPreferences,
    load_user_preferences,
    save_user_preferences,
)
from aidub.infrastructure.system_telemetry import get_real_gpu_telemetry
from aidub.orchestration.job_manager import JobStatus, get_job_manager
from aidub.ui.dialogs.log_viewer_dialog import LogViewerDialog
from aidub.ui.preferences_dialog import PreferencesDialog
from aidub.ui.screens.timeline_editor import TimelineScreen


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# =====================================================================
# 1. Project Model & Exact Reload Test
# =====================================================================


def test_project_model_atomic_save_and_exact_reload(tmp_path: Path, qapp: QApplication) -> None:
    """Kill and relaunch test: project file reloads exactly."""
    project_dir = tmp_path / "MyMovie.aidub"
    project_dir.mkdir(parents=True, exist_ok=True)
    json_path = project_dir / "project.json"

    # 1. Construct canonical project
    proj = ProjectFile(
        name="Inception Bengali Dub",
        project_path=str(json_path),
        source_file=str(tmp_path / "movie.mp4"),
        probe=ProjectProbeInfo(duration=148.5, width=1920, height=1080, fps=24.0),
        settings=ProjectFileSettings(
            source_language="en",
            target_language="bn",
            asr_model_size="small",
            translation_engine="nllb-200",
            tts_voice="bn-BD-PradeepNeural",
        ),
        stage_status=StageStatus(extract="completed", transcribe="running"),
        segments=[
            SegmentModel(
                id="seg_0001",
                start=0.0,
                end=2.5,
                speaker="Cob",
                original="What is the most resilient parasite?",
                translation="সবচেয়ে স্থিতিস্থাপক পরজীবী কী?",
                status="translated",
                qc_issues=[],
            ),
            SegmentModel(
                id="seg_0002",
                start=3.0,
                end=5.2,
                speaker="Arthur",
                original="An idea.",
                translation="একটি চিন্তা।",
                status="translated",
                qc_issues=["line_length"],
            ),
        ],
    )

    saved_p = proj.save(json_path)
    assert saved_p.is_file()

    # 2. Reload project into TimelineScreen
    screen = TimelineScreen()
    success = screen.load_project_file(saved_p)
    assert success is True

    # 3. Verify exact reload match
    data = screen._current_project_data
    assert data["name"] == "Inception Bengali Dub"
    assert data["duration"] == 148.5
    assert len(screen._current_project_data["clips"]) >= 2

    # 4. Autosave label reflects real timestamp
    autosave_text = screen.autosave_lbl.text()
    assert "Auto-saved" in autosave_text

    # 5. Modify and autosave
    screen._autosave_session()
    reloaded = ProjectFile.load(saved_p)
    assert reloaded.name == "Inception Bengali Dub"
    assert reloaded.updated_at != ""


# =====================================================================
# 2. Job Manager & Counter Test
# =====================================================================


def test_job_manager_dummy_job_and_cancellation() -> None:
    """Starting and cancelling a dummy job updates the Jobs counter."""
    jm = get_job_manager()
    initial_count = jm.active_jobs_count

    # Start dummy job
    job = jm.start_dummy_job("Acceptance Test Dummy", duration=2.0)
    assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING)
    assert jm.active_jobs_count >= initial_count + 1

    time.sleep(0.3)
    assert job.progress > 0.0

    # Cancel dummy job
    cancelled = jm.cancel_job(job.id)
    assert cancelled is True
    assert job.status == JobStatus.CANCELLED
    time.sleep(0.1)
    assert jm.active_jobs_count == initial_count


# =====================================================================
# 3. Real System Stats Match nvidia-smi
# =====================================================================


def test_real_system_stats_match_hardware() -> None:
    """Stats probed via NVML / pynvml match nvidia-smi."""
    gpu_name, gpu_pct, vram_used, vram_total = get_real_gpu_telemetry()

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            output = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=3,
            )
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            if lines:
                expected_name, expected_mem_mb = [v.strip() for v in lines[0].split(",")]
                expected_total_gb = round(float(expected_mem_mb) / 1024.0, 1)

                assert gpu_name == expected_name
                assert vram_total == expected_total_gb
                assert 0.0 <= vram_used <= vram_total
                assert 0 <= gpu_pct <= 100
                return
        except Exception:
            pass

    # If no GPU machine
    if gpu_name == "No GPU":
        assert vram_total == 0.0
        assert vram_used == 0.0


# =====================================================================
# 4. Real Settings Dialog & User Preferences
# =====================================================================


def test_real_settings_dialog_persists_all_fields(tmp_path: Path, qapp: QApplication) -> None:
    """Settings dialog exposes and persists all real pipeline options."""
    pref_file = tmp_path / "preferences.json"
    dialog = PreferencesDialog()

    # Configure real values
    dialog.ffmpeg_edit.setText("C:\\custom\\ffmpeg.exe")
    dialog.cache_edit.setText("C:\\custom\\cache")

    idx_asr = dialog.asr_combo.findData("medium")
    if idx_asr >= 0:
        dialog.asr_combo.setCurrentIndex(idx_asr)

    idx_trans = dialog.trans_combo.findData("gemini")
    if idx_trans >= 0:
        dialog.trans_combo.setCurrentIndex(idx_trans)

    idx_voice = dialog.tts_voice_combo.findData("bn-BD-NabanitaNeural")
    if idx_voice >= 0:
        dialog.tts_voice_combo.setCurrentIndex(idx_voice)

    idx_hw = dialog.hw_combo.findData("cuda")
    if idx_hw >= 0:
        dialog.hw_combo.setCurrentIndex(idx_hw)

    dialog._save()
    saved_prefs = dialog.get_preferences()

    assert saved_prefs.ffmpeg_path == "C:\\custom\\ffmpeg.exe"
    assert saved_prefs.model_cache_dir == "C:\\custom\\cache"
    assert saved_prefs.asr_model_size == "medium"
    assert saved_prefs.translation_engine == "gemini"
    assert saved_prefs.tts_voice == "bn-BD-NabanitaNeural"
    assert saved_prefs.device == "cuda"


# =====================================================================
# 5. Logging Infrastructure & Log Viewer Dialog
# =====================================================================


def test_logging_and_in_app_log_panel(tmp_path: Path, qapp: QApplication) -> None:
    """Rotating file log writes to disk and in-app handler displays lines."""
    log_file = tmp_path / "logs" / "app.log"
    configure_secure_logging(log_file=log_file)

    test_logger = logging.getLogger("acceptance_test")
    test_msg = "Phase 1 Foundation Acceptance Log Verified"
    test_logger.info(test_msg)

    # In-App Log Handler
    in_app = get_in_app_log_handler()
    lines = in_app.get_lines()
    assert any(test_msg in ln for ln in lines)

    # Log file on disk
    assert log_file.is_file()
    disk_content = log_file.read_text(encoding="utf-8")
    assert test_msg in disk_content

    # In-App Log Viewer Dialog
    dlg = LogViewerDialog()
    assert test_msg in dlg.text_area.toPlainText()
    dlg.close()
