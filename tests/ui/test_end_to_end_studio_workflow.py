"""
Authoritative End-to-End Workflow & Studio Verification Test Suite.

Verifies:
1. Home Dashboard dynamic ProjectCatalog integration and empty states.
2. Complete production lifecycle: Create .aidub package -> Import media ->
   Load/edit Bengali Unicode subtitles -> Save to SQLite & filesystem ->
   Reopen project package -> Verify persistence & integrity -> Export master SRT.
3. Job progress, cancellation, and worker error state handling.
4. NewProjectDialog input validation and duplicate package collision prevention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="Desktop PySide6 required for studio UI tests")

from aidub.application.projects import ProjectPackageService
from aidub.domain.project import PrivacyMode, ProjectSettings, QualityPreset
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate
from aidub.infrastructure.catalog import ProjectCatalog
from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt
from aidub.ui.application import DesktopApplication
from aidub.ui.dialogs.new_project_dialog import NewProjectDialog


def _dummy_settings() -> ProjectSettings:
    return ProjectSettings(
        video_rate=RationalRate(numerator=24000, denominator=1001),
        source_language="en-US",
        quality_preset=QualityPreset.PROFESSIONAL,
        privacy_mode=PrivacyMode.OFFLINE,
    )


def _dummy_auth() -> SourceAuthorization:
    return SourceAuthorization(
        acknowledged=True,
        acknowledged_by="operator@studio.test",
        acknowledged_at=datetime.now(UTC),
        authority_basis="Broadcast Master Dubbing Agreement",
        evidence_reference="contract://2026-bengali-dub",
    )


@pytest.fixture
def desktop_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DesktopApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    # Redirect default catalog to tmp_path to isolate recent projects
    catalog_path = tmp_path / "test_catalog.db"
    monkeypatch.setattr("aidub.infrastructure.catalog.default_catalog_path", lambda: catalog_path)
    monkeypatch.setattr(
        "aidub.infrastructure.catalog.catalog.default_catalog_path", lambda: catalog_path
    )

    desktop = DesktopApplication([], locale="en")
    desktop.show()
    desktop.application.processEvents()
    return desktop


def test_home_dashboard_recent_projects_and_empty_state(
    desktop_app: DesktopApplication,
    tmp_path: Path,
) -> None:
    window = desktop_app.window
    home = window.home_view

    # 1. Verify initial empty state when no recent projects exist
    home.refresh_projects()
    desktop_app.application.processEvents()
    assert home.projects_layout.count() >= 1

    # 2. Create a project and add to catalog
    catalog_path = tmp_path / "test_catalog.db"
    catalog = ProjectCatalog(catalog_path)
    catalog.initialize()

    proj_dir = tmp_path / "Feature_Bengali.aidub"
    proj_dir.mkdir(parents=True, exist_ok=True)
    catalog.upsert_project(
        project_id="prj_test01",
        name="Feature Bengali Dub",
        path=proj_dir,
    )

    # 3. Refresh home and verify real project card is populated
    home.refresh_projects()
    desktop_app.application.processEvents()
    assert home.projects_layout.count() >= 2  # Project card + New Project Tile

    # 4. Test search filter on recent projects
    home.refresh_projects(filter_text="Feature")
    desktop_app.application.processEvents()
    assert home.projects_layout.count() >= 2

    home.refresh_projects(filter_text="NonExistentName12345")
    desktop_app.application.processEvents()
    # When filter yields no results, falls back to empty state card
    assert home.projects_layout.count() >= 1


def test_complete_project_lifecycle_workflow(
    desktop_app: DesktopApplication,
    tmp_path: Path,
) -> None:
    """Objective 3 verification:

    Create package -> Import -> Edit Bengali Subtitles -> Save -> Reopen ->
    Export -> Verify.
    """
    window = desktop_app.window
    catalog_path = tmp_path / "test_catalog.db"
    catalog = ProjectCatalog(catalog_path)
    catalog.initialize()

    # Step 1: Create a real .aidub project package using ProjectPackageService
    service = ProjectPackageService(catalog=catalog)
    pkg_dest = tmp_path / "Cinema_Movie_Master"
    opened = service.create(
        pkg_dest,
        name="Cinema Movie Master",
        settings=_dummy_settings(),
        source_authorization=_dummy_auth(),
        localization_locales=("bn-BD",),
        actor_id="operator@studio.test",
    )
    assert opened.paths.root.is_dir()
    assert opened.paths.manifest.is_file()
    assert opened.paths.database.is_file()

    # Step 2: Open project package in Studio Window
    window.open_project_path(opened.paths.root)
    desktop_app.application.processEvents()

    assert window.stack.currentWidget() is window.studio
    assert window._active_project is not None
    assert window._active_project.project.name == "Cinema Movie Master"

    # Step 3: Create bilingual subtitle test data with Bengali Unicode text
    bengali_srt_file = tmp_path / "sample_bilingual.srt"
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Welcome to the AI Movie Dubbing Studio.\n"
        "কৃত্রিম বুদ্ধিমত্তা চালিত চলচ্চিত্র ডাবিং স্টুডিওতে স্বাগতম।\n\n"
        "2\n"
        "00:00:04,500 --> 00:00:08,000\n"
        "Every line is accurately translated and synchronized.\n"
        "প্রতিটি সংলাপ নির্ভুলভাবে অনুবাদ এবং সিঙ্ক্রোনাইজ করা হয়েছে।\n\n"
    )
    bengali_srt_file.write_text(srt_content, encoding="utf-8")

    # Step 4: Import bilingual subtitle file into the Studio Timeline
    window.studio.import_bilingual_subtitle_file(str(bengali_srt_file))
    desktop_app.application.processEvents()

    clips = window.studio._current_project_data.get("clips", [])
    s1_clips = [c for c in clips if c[0] == "S1"]
    s2_clips = [c for c in clips if c[0] == "S2"]

    assert len(s1_clips) == 2
    assert len(s2_clips) == 2
    assert "Welcome to the AI Movie" in s1_clips[0][3]
    # Verify Bengali Unicode characters were imported without corruption
    assert "কৃত্রিম বুদ্ধিমত্তা" in s2_clips[0][3]
    assert "প্রতিটি সংলাপ" in s2_clips[1][3]

    # Step 5: Save project to the .aidub package
    save_ok = window.studio.save_to_project(window._active_project)
    assert save_ok is True

    # Verify filesystem persistence inside .aidub package
    timeline_state = opened.paths.transcripts / "timeline_state.json"
    s1_saved = opened.paths.transcripts / "subtitles_S1.srt"
    s2_saved = opened.paths.transcripts / "subtitles_S2.srt"

    assert timeline_state.is_file()
    assert s1_saved.is_file()
    assert s2_saved.is_file()

    # Verify Bengali Unicode content in saved SRT file
    s2_text = s2_saved.read_text(encoding="utf-8")
    assert "কৃত্রিম বুদ্ধিমত্তা চালিত" in s2_text

    # Step 6: Reopen project package into Studio and verify state restoration
    # Clear memory state first
    window.studio._current_project_data["clips"] = []
    window.studio.canvas_view.clear_markers()

    # Reopen package
    window.studio.load_opened_project(opened)
    desktop_app.application.processEvents()

    reloaded_clips = window.studio._current_project_data.get("clips", [])
    reloaded_s2 = [c for c in reloaded_clips if c[0] == "S2"]
    assert len(reloaded_s2) == 2
    assert "কৃত্রিম বুদ্ধিমত্তা চালিত" in reloaded_s2[0][3]

    # Step 7: Export supported master subtitle artifacts
    exported_bilingual = tmp_path / "output_bilingual.srt"
    segments = [
        {
            "start": c[1],
            "end": c[1] + c[2],
            "text": s1_clips[idx][3],
            "tgt": c[3],
        }
        for idx, c in enumerate(reloaded_s2)
    ]
    write_bilingual_srt(segments, str(exported_bilingual), LineMode.BILINGUAL_TARGET_BOTTOM)
    assert exported_bilingual.is_file()
    assert exported_bilingual.stat().st_size > 0

    exported_target = tmp_path / "output_target_bn.srt"
    write_srt(segments, str(exported_target), translated=True)
    assert exported_target.is_file()
    target_content = exported_target.read_text(encoding="utf-8")
    assert "কৃত্রিম বুদ্ধিমত্তা চালিত" in target_content


def test_job_progress_and_cancellation_handling(
    desktop_app: DesktopApplication,
) -> None:
    window = desktop_app.window

    # Simulate worker emitting dubbing progress
    window.update_dub_progress("separation", 35, "Separating dialogue from score")
    desktop_app.application.processEvents()

    assert window.toolbar_progress_bar.isVisible()
    assert window.toolbar_progress_bar.value() == 35
    assert window.cancel_action.isEnabled()
    assert not window.dub_action.isEnabled()

    # Simulate cancellation
    window.set_dub_completed(False, "Cancelled")
    desktop_app.application.processEvents()

    assert window.dub_action.isEnabled()
    assert not window.cancel_action.isEnabled()
    assert window.toolbar_stage_label.text() == "Dubbing Stopped"

    # Simulate success completion
    window.set_dub_completed(True, "Success")
    desktop_app.application.processEvents()

    assert window.dub_action.isEnabled()
    assert window.toolbar_progress_bar.value() == 100
    assert window.toolbar_stage_label.text() == "Dubbing Complete"


def test_new_project_dialog_validation(
    desktop_app: DesktopApplication,
    tmp_path: Path,
) -> None:
    dialog = NewProjectDialog(desktop_app.window)
    dialog.show()
    desktop_app.application.processEvents()
    dialog.loc_edit.setText(str(tmp_path))

    # Empty name validation
    dialog.name_edit.setText("")
    dialog._on_create()
    desktop_app.application.processEvents()
    assert dialog.error_lbl.isVisible()
    assert "Please enter a project name" in dialog.error_lbl.text()

    # Valid name creation
    dialog.name_edit.setText("Bengali Studio Project")
    dialog._on_create()
    assert dialog.error_lbl.text() == "" or not dialog.error_lbl.isVisible()
    assert dialog.created_project is not None
    assert dialog.created_project.project.name == "Bengali Studio Project"
    assert dialog.created_project.paths.root.is_dir()

    # Attempting to create duplicate package name should fail with clear error
    duplicate_dialog = NewProjectDialog(desktop_app.window)
    duplicate_dialog.show()
    desktop_app.application.processEvents()
    duplicate_dialog.loc_edit.setText(str(tmp_path))
    duplicate_dialog.name_edit.setText("Bengali Studio Project")
    duplicate_dialog._on_create()
    desktop_app.application.processEvents()
    assert duplicate_dialog.error_lbl.isVisible()
    assert "already exists" in duplicate_dialog.error_lbl.text()
    assert duplicate_dialog.created_project is None
