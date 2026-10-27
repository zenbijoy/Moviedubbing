"""
Unit and integration tests for Phase 5: Production Readiness, Crash Recovery,
Windows Packaging, User Preferences, Logging, and Support Diagnostics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from aidub.diagnostics.support_bundle import SupportBundleGenerator
from aidub.infrastructure.logging import configure_secure_logging, get_default_log_file
from aidub.infrastructure.packaging import PackagingSpec, WindowsPackager
from aidub.infrastructure.preferences import (
    UserPreferences,
    load_user_preferences,
    save_user_preferences,
)
from aidub.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from aidub.ui.preferences_dialog import PreferencesDialog
from aidub.ui.screens.timeline_editor import TimelineScreen


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# =====================================================================
# 1. User Preferences Persistence & Atomic Writes
# =====================================================================


def test_user_preferences_default() -> None:
    prefs = UserPreferences()
    assert prefs.theme == "studio_dark"
    assert prefs.default_target_language == "bn-BD"
    assert prefs.default_tts_engine == "edge-tts"
    assert prefs.auto_save_interval_minutes == 3
    assert prefs.hardware_acceleration == "auto"
    assert prefs.privacy_mode == "online"


def test_user_preferences_save_and_load(tmp_path: Path) -> None:
    target_file = tmp_path / "config" / "user_preferences.json"
    prefs = UserPreferences(
        theme="cyber_dark",
        default_target_language="hi-IN",
        default_tts_engine="chatterbox",
        auto_save_interval_minutes=5,
        hardware_acceleration="directml",
        privacy_mode="offline",
    )
    ok = save_user_preferences(prefs, target_file)
    assert ok is True
    assert target_file.exists()

    loaded = load_user_preferences(target_file)
    assert loaded.theme == "cyber_dark"
    assert loaded.default_target_language == "hi-IN"
    assert loaded.default_tts_engine == "chatterbox"
    assert loaded.auto_save_interval_minutes == 5
    assert loaded.hardware_acceleration == "directml"
    assert loaded.privacy_mode == "offline"


def test_user_preferences_fallback_on_corrupt_file(tmp_path: Path) -> None:
    target_file = tmp_path / "corrupt_prefs.json"
    target_file.write_text("{ this is invalid json !!!", encoding="utf-8")

    # Should safely catch error and return defaults
    loaded = load_user_preferences(target_file)
    assert loaded.theme == "studio_dark"
    assert loaded.default_target_language == "bn-BD"


# =====================================================================
# 2. Crash Recovery & Atomic Project State Saving
# =====================================================================


def test_timeline_atomic_save_and_backup_creation(qapp: QApplication, tmp_path: Path) -> None:
    editor = TimelineScreen()
    opened_mock = MagicMock()
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir(parents=True)
    opened_mock.paths.transcripts = transcripts_dir
    opened_mock.project.name = "Test Project"
    opened_mock.project.project_id = "proj_test_1"
    opened_mock.database = MagicMock()

    # Initial save
    success = editor.save_to_project(opened=opened_mock)
    assert success is True

    state_file = transcripts_dir / "timeline_state.json"
    assert state_file.is_file()

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "project_name" in data
    assert data["project_name"] == "Test Project"

    # Second save should create .bak prior to overwriting
    editor._mixer_levels["A1"] = 0.5
    success = editor.save_to_project(opened=opened_mock)
    assert success is True

    bak_file = transcripts_dir / "timeline_state.json.bak"
    assert bak_file.is_file()
    bak_data = json.loads(bak_file.read_text(encoding="utf-8"))
    assert "project_name" in bak_data

    updated_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert updated_data["mixer"]["levels"]["A1"] == 0.5


def test_timeline_recovery_from_backup_when_primary_corrupt(
    qapp: QApplication, tmp_path: Path
) -> None:
    editor = TimelineScreen()
    opened_mock = MagicMock()
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir(parents=True)
    source_links_dir = tmp_path / "source-links"
    source_links_dir.mkdir(parents=True)
    localizations_dir = tmp_path / "localizations"
    localizations_dir.mkdir(parents=True)

    opened_mock.paths.transcripts = transcripts_dir
    opened_mock.paths.source_links = source_links_dir
    opened_mock.paths.localizations = localizations_dir
    opened_mock.paths.root = tmp_path
    opened_mock.project.name = "Corrupt Recovery Project"
    opened_mock.project.project_id = "proj_corrupt_1"

    # Create backup with valid state
    bak_file = transcripts_dir / "timeline_state.json.bak"
    bak_file.write_text(
        json.dumps(
            {
                "project_name": "Corrupt Recovery Project",
                "media_path": "",
                "duration": 42.0,
                "clips": [["V1", 0.0, 42.0, "recovered_video.mp4", None]],
                "mixer": {"levels": {"master": 1.0}, "mutes": [], "solos": []},
            }
        ),
        encoding="utf-8",
    )

    # Create corrupted primary state file
    primary_file = transcripts_dir / "timeline_state.json"
    primary_file.write_text("{ INVALID_JSON_DATA_CRASH", encoding="utf-8")

    # Loading should fall back to .bak and succeed without crash
    editor.load_opened_project(opened_mock)
    assert "Corrupt Recovery Project" in editor.timeline_bar.title_label.text()


# =====================================================================
# 3. Secure Logging & Rotation
# =====================================================================


def test_logging_configuration_with_rotation(tmp_path: Path) -> None:
    log_file = tmp_path / "test_app.log"
    configure_secure_logging(level=logging.INFO, log_file=log_file)

    test_logger = logging.getLogger("aidub.test")
    test_logger.info("Normal message")
    test_logger.info("Secret API key: sk-live-1234567890abcdef1234567890")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Normal message" in content
    # Secret must be redacted
    assert "sk-live-1234567890abcdef1234567890" not in content
    assert "REDACTED" in content


def test_default_log_file_resolution() -> None:
    default_log = get_default_log_file()
    assert default_log.name == "aidub_desktop.log"
    assert "AIDubStudio" in str(default_log) or "aidub" in str(default_log)


# =====================================================================
# 4. User Preferences Dialog & Keyboard Shortcuts Dialog
# =====================================================================


def test_preferences_dialog_signals(qapp: QApplication) -> None:
    dialog = PreferencesDialog()

    emitted_prefs: list[UserPreferences] = []
    dialog.preferences_saved.connect(lambda p: emitted_prefs.append(p))

    # Change some values via UI widgets
    idx = dialog.theme_combo.findData("high_contrast")
    if idx >= 0:
        dialog.theme_combo.setCurrentIndex(idx)
    dialog.autosave_spin.setValue(15)
    idx_hw = dialog.hw_combo.findData("cuda")
    if idx_hw >= 0:
        dialog.hw_combo.setCurrentIndex(idx_hw)

    dialog._save()
    assert len(emitted_prefs) == 1
    saved = emitted_prefs[0]
    assert saved.theme == "high_contrast"
    assert saved.auto_save_interval_minutes == 15
    assert saved.hardware_acceleration == "cuda"


def test_keyboard_shortcuts_dialog(qapp: QApplication) -> None:
    dialog = KeyboardShortcutsDialog()
    assert "Keyboard Shortcuts" in dialog.windowTitle()
    # Check that shortcuts table is populated
    assert dialog.table.rowCount() > 10

    # Test search filter
    dialog.search_edit.setText("Split")
    # Verify rows are filtered
    visible_rows = [r for r in range(dialog.table.rowCount()) if not dialog.table.isRowHidden(r)]
    assert len(visible_rows) >= 1


# =====================================================================
# 5. Windows Standalone Packaging & Unicode Path Support
# =====================================================================


def test_windows_packager_assembly_and_unicode_paths(tmp_path: Path) -> None:
    # Use path containing spaces and Bengali Unicode characters
    unicode_out = tmp_path / "Movie Dubbing Studio বাংলা" / "dist"
    spec = PackagingSpec(
        app_name="MovieDubbingStudio",
        version="0.1.0",
        source_dir=Path("src/aidub"),
        output_dir=unicode_out,
        resources_dir=Path("resources"),
    )
    packager = WindowsPackager(spec)
    built_path = packager.assemble_distribution()

    assert built_path.exists()
    assert WindowsPackager.verify_distribution(built_path)

    # Verify launchers
    assert (built_path / "MovieDubbingStudio.bat").exists()
    assert (built_path / "MovieDubbingStudio.ps1").exists()
    assert (built_path / "aidub.bat").exists()
    assert (built_path / "manifest.json").exists()
    assert (built_path / "bin" / "README_FFMPEG.txt").exists()
    assert (built_path / "models" / "README_MODELS.txt").exists()

    # Verify manifest content
    manifest_data = json.loads((built_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["app_name"] == "MovieDubbingStudio"
    assert manifest_data["version"] == "0.1.0"
    assert manifest_data["platform"] == "windows"


# =====================================================================
# 6. Support Diagnostic Bundle Generation
# =====================================================================


def test_support_bundle_generator_export(tmp_path: Path) -> None:
    generator = SupportBundleGenerator()
    out_dir = tmp_path / "support_export"

    # Mock log file with sensitive string
    fake_log = tmp_path / "test.log"
    fake_log.write_text(
        "Application running. Secret: api_key=supersecrettoken123\nUser path: C:\\Users\\secret_user\\project",
        encoding="utf-8",
    )

    result = generator.generate_support_bundle(
        output_directory=str(out_dir),
        extra_log_files=[str(fake_log)],
    )
    assert Path(result.zip_path).exists()
    assert result.file_count >= 2
    assert result.redacted_tokens_count > 0
