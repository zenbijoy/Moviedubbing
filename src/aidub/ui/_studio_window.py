"""Main AIDubStudioWindow class."""

from __future__ import annotations

from ._studio_common import *
from ._studio_common import _QT
from ._studio_widgets import (
    _HomeDashboardPanel,
    _StudioChrome,
)

if _QT:
    class AIDubStudioWindow(QMainWindow):
        """One authoritative Studio surface with stacked Home overview and Timeline Screens."""

        def __init__(
            self,
            locale_service: LocaleService | None = None,
            parent: Any | None = None,
        ) -> None:
            super().__init__(parent)
            if locale_service is None:
                from aidub.i18n import LocaleService

                locale_service = LocaleService()

            from aidub.ui.screens.timeline_editor import TimelineScreen

            self._locale_service = locale_service
            self._unsubscribe_locale = self._locale_service.subscribe(self._apply_locale)
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinMaxButtonsHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            self.stack = QStackedWidget(self)
            self.studio = TimelineScreen(self)
            self.home_view = _HomeDashboardPanel(self)
            self.stack.addWidget(self.home_view)
            self.stack.addWidget(self.studio)
            self.stack.setCurrentWidget(self.home_view)
            self.setCentralWidget(self.stack)
            self._active_project: Any | None = None

            self.setObjectName("AIDubStudioWindow")
            self.setAcceptDrops(True)
            self.setMinimumSize(1_200, 760)
            self.resize(1_600, 960)
            self.chrome = _StudioChrome(self)
            self.setMenuWidget(self.chrome)
            self._build_toolbar()
            self._build_menus()
            from aidub.orchestration.job_manager import get_job_manager

            self._job_manager = get_job_manager()
            if self._job_manager.signals is not None:
                self._job_manager.signals.active_count_changed.connect(self.chrome.set_jobs)
            self._jobs_timer = QTimer(self)
            self._jobs_timer.setInterval(1000)
            self._jobs_timer.timeout.connect(
                lambda: self.chrome.set_jobs(self._job_manager.active_jobs_count)
            )
            self._jobs_timer.start()
            self._telemetry_worker = _TelemetryWorker(self)
            self._telemetry_worker.completed.connect(self.chrome.set_telemetry)
            self._telemetry_worker.start()
            self._apply_locale(self._locale_service.locale)

            from aidub.infrastructure.preferences import load_user_preferences

            self._user_prefs = load_user_preferences()
            if self._user_prefs.theme != "studio_dark":
                try:
                    self._set_theme(self._user_prefs.theme)
                except Exception:
                    pass

        def _build_toolbar(self) -> None:
            toolbar = QToolBar("Main Dubbing Toolbar", self)
            toolbar.setObjectName("MainToolBar")
            toolbar.setMovable(False)
            toolbar.setVisible(
                False
            )  # Hidden to eliminate clutter; chrome tabs provide sleek navigation!
            toolbar.setStyleSheet(
                "QToolBar#MainToolBar {"
                "  background: #0B0E14;"
                "  border-bottom: 1px solid #1E2838;"
                "  spacing: 8px;"
                "  padding: 4px 14px;"
                "}"
                "QToolBar#MainToolBar QToolButton {"
                "  background: #18202D;"
                "  color: #F7F9FC;"
                "  border: 1px solid #2B384E;"
                "  border-radius: 4px;"
                "  padding: 5px 14px;"
                "  font-size: 11px;"
                "  font-weight: 700;"
                "}"
                "QToolBar#MainToolBar QToolButton:hover {"
                "  background: #2563EB;"
                "  border-color: #3B82F6;"
                "}"
                "QToolBar#MainToolBar QToolButton:disabled {"
                "  color: #64748B;"
                "  background: #0F141C;"
                "  border-color: #1A222E;"
                "}"
            )
            self.dub_action = toolbar.addAction("Dub")
            self.dub_action.setToolTip(
                "Dub Movie (pick language & Fast/Quality profile) — Ctrl+Enter"
            )
            self.dub_action.setShortcut(QKeySequence("Ctrl+Enter"))
            self.dub_action.triggered.connect(self.open_dub_dialog)

            self.cancel_action = toolbar.addAction("Cancel")
            self.cancel_action.setToolTip("Cancel Active Dubbing Job — Esc")
            self.cancel_action.setEnabled(False)
            self.cancel_action.triggered.connect(self.cancel_dub_job)

            toolbar.addSeparator()

            self.toolbar_stage_label = QLabel("", toolbar)
            self.toolbar_stage_label.setStyleSheet(
                "color:#38BDF8;font-size:11px;font-weight:600;padding:0 6px;"
            )
            self.toolbar_stage_label.setVisible(False)
            toolbar.addWidget(self.toolbar_stage_label)

            self.toolbar_progress_bar = QProgressBar(toolbar)
            self.toolbar_progress_bar.setRange(0, 100)
            self.toolbar_progress_bar.setValue(0)
            self.toolbar_progress_bar.setFixedWidth(200)
            self.toolbar_progress_bar.setFixedHeight(14)
            self.toolbar_progress_bar.setTextVisible(True)
            self.toolbar_progress_bar.setStyleSheet(
                "QProgressBar{background:#111722;border:1px solid #283446;border-radius:3px;text-align:center;color:#E2E8F0;font-size:10px;font-weight:700;}"
                "QProgressBar::chunk{background:#2563EB;border-radius:2px;}"
            )
            self.toolbar_progress_bar.setVisible(False)
            toolbar.addWidget(self.toolbar_progress_bar)

            self.addToolBar(toolbar)
            self.toolbar = toolbar

        def open_dub_dialog(self) -> None:
            self.show_studio()
            self.studio.open_dub_dialog()

        def cancel_dub_job(self) -> None:
            self.studio.cancel_active_job()

        def update_dub_progress(self, stage: str, percent: int, message: str) -> None:
            if hasattr(self, "toolbar"):
                self.toolbar.setVisible(True)
            if hasattr(self, "toolbar_progress_bar"):
                self.toolbar_progress_bar.setVisible(True)
                self.toolbar_progress_bar.setValue(percent)
                self.toolbar_progress_bar.setFormat(f"{percent}%")
            if hasattr(self, "toolbar_stage_label"):
                self.toolbar_stage_label.setVisible(True)
                self.toolbar_stage_label.setText(f"Stage: {stage.upper()} · {message}")
            if hasattr(self, "cancel_action"):
                self.cancel_action.setEnabled(True)
            if hasattr(self, "dub_action"):
                self.dub_action.setEnabled(False)
            if hasattr(self.chrome, "dub_btn"):
                self.chrome.dub_btn.setEnabled(False)

        def set_dub_completed(self, success: bool, message: str = "") -> None:
            if hasattr(self, "dub_action"):
                self.dub_action.setEnabled(True)
            if hasattr(self, "cancel_action"):
                self.cancel_action.setEnabled(False)
            if hasattr(self.chrome, "dub_btn"):
                self.chrome.dub_btn.setEnabled(True)
            if hasattr(self, "toolbar_progress_bar"):
                if success:
                    self.toolbar_progress_bar.setValue(100)
                    self.toolbar_progress_bar.setFormat("100% · Complete")
                else:
                    self.toolbar_progress_bar.setVisible(False)
            if hasattr(self, "toolbar_stage_label"):
                if success:
                    self.toolbar_stage_label.setText("Dubbing Complete")
                else:
                    self.toolbar_stage_label.setText(
                        "Dubbing Stopped" if message == "Cancelled" else f"Failed: {message}"
                    )

        def show_home(self) -> None:
            self.stack.setCurrentWidget(self.home_view)
            if hasattr(self, "chrome"):
                self.chrome.nav_dub_btn.setStyleSheet(
                    "QPushButton{background:#E11D48;color:#FFF;border:none;border-radius:4px;"
                    "padding:4px 14px;font-size:11px;font-weight:700;}"
                )
                self.chrome.nav_studio_btn.setStyleSheet(
                    "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                    "padding:4px 14px;font-size:11px;font-weight:600;}"
                    "QPushButton:hover{background:#202B40;color:#FFF;}"
                )

        def show_studio(self) -> None:
            self.stack.setCurrentWidget(self.studio)
            if hasattr(self, "chrome"):
                self.chrome.nav_studio_btn.setStyleSheet(
                    "QPushButton{background:#2563EB;color:#FFF;border:none;border-radius:4px;"
                    "padding:4px 14px;font-size:11px;font-weight:700;}"
                )
                self.chrome.nav_dub_btn.setStyleSheet(
                    "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                    "padding:4px 14px;font-size:11px;font-weight:600;}"
                    "QPushButton:hover{background:#202B40;color:#FFF;}"
                )

        def import_from_home(self) -> None:
            self.show_studio()
            self.studio.import_media_dialog()

        def create_new_project_dialog(self) -> None:
            from aidub.ui.dialogs.new_project_dialog import NewProjectDialog

            dialog = NewProjectDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.created_project:
                opened = dialog.created_project
                self._active_project = opened
                self.studio.load_opened_project(opened)
                self.chrome.set_project(
                    opened.project.name,
                    target_lang=opened.project.settings.source_language,
                )
                self.show_studio()
                self.home_view.refresh_projects()

        def open_project_dialog(self) -> None:
            selected = QFileDialog.getExistingDirectory(
                self,
                "Open .aidub Project Package Directory",
                str(Path.home() / "Documents" / "AIDubStudioProjects"),
            )
            if selected:
                self.open_project_path(selected)

        def open_project_path(self, path_str: str | Path) -> None:
            path = Path(path_str).resolve()
            if (path.is_dir() and path.suffix.casefold() == ".aidub") or (
                path.is_dir() and (path / "project.db").is_file()
            ):
                from aidub.application.projects import ProjectPackageService
                from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

                catalog = ProjectCatalog(default_catalog_path())
                try:
                    catalog.initialize()
                except Exception:
                    pass
                service = ProjectPackageService(catalog=catalog)
                try:
                    opened = service.open(path)
                    self._active_project = opened
                    self.studio.load_opened_project(opened)
                    self.chrome.set_project(opened.project.name)
                    self.show_studio()
                    self.home_view.refresh_projects()
                except Exception as exc:
                    QMessageBox.critical(
                        self, "Open Project Failed", f"Failed to open project package:\n{exc}"
                    )
            elif path.is_file():
                self.load_movie_and_show_editor(str(path))
            else:
                QMessageBox.warning(self, "Invalid Path", f"Project path does not exist:\n{path}")

        def save_current_project(self) -> None:
            if hasattr(self, "_active_project") and self._active_project is not None:
                success = self.studio.save_to_project(self._active_project)
                if success:
                    self.chrome.set_project(self._active_project.project.name)
                    self.home_view.refresh_projects()
            else:
                reply = QMessageBox.question(
                    self,
                    "Save Project",
                    "No active .aidub project package is open.\n"
                    "Would you like to create a new project package to save this timeline?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.create_new_project_dialog()
                    if hasattr(self, "_active_project") and self._active_project is not None:
                        self.save_current_project()

        def load_movie_and_show_editor(self, video_path: str) -> None:
            self.show_studio()
            if video_path and Path(video_path).exists():
                self.studio.load_project(video_path)

        def open_voice_model_dialog(self) -> None:
            self.studio._open_voice_model_selector()

        def open_voice_studio_dialog(self) -> None:
            from aidub.ui.dialogs.voice_studio_dialog import VoiceStudioDialog

            dlg = VoiceStudioDialog(self)
            dlg.exec()

        def open_audio_review_dialog(self) -> None:
            from aidub.ui.dialogs.audio_review_panel import AudioReviewDialog

            dlg = AudioReviewDialog(self)
            dlg.exec()

        def open_casting_dialog(self) -> None:
            self.studio._open_character_casting_studio()

        def open_isometric_dialog(self) -> None:
            self.show_studio()
            self.studio.open_isometric_dialog()

        def open_kaggle_dialog(self) -> None:
            self.studio._open_kaggle_accelerator()

        def open_broadcast_export_dialog(self) -> None:
            self.studio._open_broadcast_export()

        def open_preferences_dialog(self) -> None:
            self.open_preferences()

        def open_preferences(self) -> None:
            from aidub.ui.preferences_dialog import PreferencesDialog

            dlg = PreferencesDialog(self)
            dlg.preferences_saved.connect(self._on_preferences_saved)
            dlg.exec()

        def _on_preferences_saved(self, prefs: Any) -> None:
            if hasattr(prefs, "theme"):
                self._set_theme(prefs.theme)

        def open_keyboard_shortcuts(self) -> None:
            self.show_keyboard_shortcuts()

        def show_keyboard_shortcuts(self) -> None:
            from aidub.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog

            dlg = KeyboardShortcutsDialog(self)
            dlg.exec()

        def export_diagnostic_bundle(self) -> None:
            from aidub.diagnostics.support_bundle import SupportBundleGenerator
            from aidub.infrastructure.logging import get_default_log_file

            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Diagnostic Support Bundle",
                "aidub_support_bundle.zip",
                "ZIP Archives (*.zip)",
            )
            if not out_path:
                return

            gen = SupportBundleGenerator()
            log_file = get_default_log_file()
            extra_logs = [str(log_file)] if log_file.is_file() else []
            try:
                dest_parent = Path(out_path).parent
                res = gen.generate_support_bundle(
                    output_directory=str(dest_parent),
                    extra_log_files=extra_logs,
                )
                generated_zip = Path(res.zip_path)
                target_zip = Path(out_path)
                if generated_zip != target_zip and target_zip.suffix.lower() == ".zip":
                    generated_zip.replace(target_zip)
                    res.zip_path = str(target_zip)

                QMessageBox.information(
                    self,
                    "Support Bundle Created",
                    f"Sanitized diagnostic bundle saved:\n{res.zip_path}\n\n"
                    f"Included files: {res.file_count}\n"
                    f"Redacted sensitive tokens: {res.redacted_tokens_count}\n\n"
                    "No passwords, API keys, or media files are included in this bundle.",
                )
            except Exception as exc:
                QMessageBox.critical(
                    self, "Diagnostics Error", f"Failed to generate support bundle:\n{exc}"
                )

        def open_logs_directory(self) -> None:
            import platformdirs

            log_dir = Path(platformdirs.user_log_dir("aidub", "AIDubStudio"))
            log_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

        def show_troubleshooting_guide(self) -> None:
            QMessageBox.information(
                self,
                "Troubleshooting & Support Guide",
                "Common Solutions:\n\n"
                "1. Missing FFmpeg / Codec Errors:\n"
                "   Install FFmpeg to your system PATH or place ffmpeg.exe and ffprobe.exe "
                "in the application bin/ directory.\n\n"
                "2. Voice Synthesis / TTS Failures:\n"
                "   Verify network connectivity for Edge-TTS neural voices, or select an offline "
                "voice model. Check proxy/firewall settings.\n\n"
                "3. GPU / VRAM Out of Memory:\n"
                "   Switch to Fast Profile in Dub Dialog, or select CPU in Studio Preferences "
                "(Edit -> Preferences -> Force CPU Only).\n\n"
                "4. Corrupted Projects / Power Cuts:\n"
                "   Automatic backup recovery restores timeline_state.json.bak if an interrupted "
                "write was detected.\n\n"
                "For further assistance, export a sanitized bundle via Help -> Export Diagnostic Support Bundle.",
            )

        def _run_hardware_wizard(self) -> None:
            from PySide6.QtWidgets import QDialog

            from aidub.ui.first_run_wizard import FirstRunHardwareWizardWidget

            dialog = QDialog(self)
            dialog.setWindowTitle("Hardware Setup & Self-Test")
            dialog.setMinimumSize(540, 360)
            layout = QVBoxLayout(dialog)
            wizard = FirstRunHardwareWizardWidget(dialog)
            layout.addWidget(wizard)
            dialog.exec()

        def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
            if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
                self.showNormal()
                self.chrome.set_maximized(False)
                event.accept()
                return
            super().keyPressEvent(event)

        def _build_menus(self) -> None:
            menu_bar = self.chrome.menu_bar
            menu_bar.clear()

            file_menu = menu_bar.addMenu("File")
            self._add_action(
                file_menu,
                "New Project…",
                self.create_new_project_dialog,
                "Ctrl+N",
            )
            self._add_action(
                file_menu,
                "Open Project Package (.aidub)…",
                self.open_project_dialog,
                "Ctrl+Shift+O",
            )
            self._add_action(
                file_menu,
                "Save Project",
                self.save_current_project,
                "Ctrl+S",
            )
            file_menu.addSeparator()
            self._add_action(
                file_menu,
                "Import Source Movie…",
                self.studio.import_media_dialog,
                "Ctrl+O",
            )
            self._add_action(
                file_menu,
                "Import Source Subtitles (SRT/VTT)…",
                self.studio.import_subtitle_dialog,
                "Ctrl+Shift+I",
            )
            self._add_action(
                file_menu,
                "Import Target Subtitles (SRT/VTT)…",
                lambda: self.studio.import_subtitle_dialog(target=True),
            )
            self._add_action(
                file_menu,
                "Import Bilingual Subtitles (SRT/VTT)…",
                self.studio.import_bilingual_subtitle_dialog,
            )
            self._add_action(
                file_menu,
                "Import Audio Track…",
                self.studio.import_audio_dialog,
            )
            file_menu.addSeparator()
            self._add_action(
                file_menu,
                "Export Dubbed Master Video…",
                self.studio.export_dubbed_video,
                "Ctrl+E",
            )
            self._add_action(
                file_menu,
                "Broadcast Master Delivery (Surround/LUFS)…",
                self.open_broadcast_export_dialog,
                "Ctrl+Shift+B",
            )
            self._add_action(
                file_menu,
                "Export Source Subtitles (SRT)…",
                lambda: self.studio.export_subtitles_dialog(target=False),
            )
            self._add_action(
                file_menu,
                "Export Target Subtitles (SRT)…",
                lambda: self.studio.export_subtitles_dialog(target=True),
            )
            self._add_action(
                file_menu,
                "Export Bilingual Subtitles (SRT)…",
                lambda: self.studio.export_subtitles_dialog(bilingual=True),
            )
            self._add_action(
                file_menu,
                "Export Current Frame…",
                self.studio.export_snapshot,
                "Ctrl+Shift+E",
            )
            file_menu.addSeparator()
            self._add_action(file_menu, "Exit", self.close, "Alt+F4")

            edit_menu = menu_bar.addMenu("Edit")
            self._add_action(
                edit_menu,
                "Undo",
                self.studio.undo,
                "Ctrl+Z",
            )
            self._add_action(
                edit_menu,
                "Redo",
                self.studio.redo,
                "Ctrl+Y",
            )
            edit_menu.addSeparator()
            self._add_action(
                edit_menu,
                "Command Palette…",
                self._open_command_palette,
                "Ctrl+K",
            )
            edit_menu.addSeparator()
            self._add_action(
                edit_menu,
                "Rewrite Selected Translation",
                self.studio.rewrite_selected_translation,
            )
            self._add_action(
                edit_menu,
                "Shorten Selected Translation",
                lambda: self.studio.rewrite_selected_translation(shorten=True),
            )
            self._add_action(
                edit_menu,
                "Match Selected Timing",
                self.studio.match_selected_timing,
            )
            edit_menu.addSeparator()
            self._add_action(
                edit_menu,
                "Preferences…",
                self.open_preferences,
                "Ctrl+,",
            )

            clip_menu = menu_bar.addMenu("Clip")
            self._add_action(
                clip_menu,
                "Auto-Detect Movie Characters",
                self.studio.auto_detect_characters,
            )
            self._add_action(
                clip_menu,
                "Regenerate Selected Voice",
                self.studio.regenerate_selected_voice,
            )
            self._add_action(
                clip_menu,
                "Character & Speaker Manager…",
                self.studio._open_character_manager,
            )
            self._add_action(
                clip_menu,
                "Audio Analysis & Speech Tools…",
                self.studio._open_audio_analysis,
            )
            self._add_action(
                clip_menu,
                "AI Voice Studio & Dialogue Lab…",
                self.open_voice_studio_dialog,
                "Ctrl+Shift+V",
            )
            self._add_action(
                clip_menu,
                "Dialogue Audio Review & QC Panel…",
                self.open_audio_review_dialog,
                "Ctrl+Shift+R",
            )
            clip_menu.addSeparator()
            self._add_action(
                clip_menu,
                "Play / Pause",
                self.studio.play_pause,
                "Space",
            )
            self._add_action(
                clip_menu,
                "Previous Frame",
                self.studio.step_backward,
                "Left",
            )
            self._add_action(
                clip_menu,
                "Next Frame",
                self.studio.step_forward,
                "Right",
            )

            sequence_menu = menu_bar.addMenu("Sequence")
            self._add_action(
                sequence_menu,
                "Dub Movie…",
                self.open_dub_dialog,
                "Ctrl+Enter",
            )
            self._add_action(
                sequence_menu,
                "Set Target Language…",
                self.studio.configure_target_language,
            )
            self._add_action(
                sequence_menu,
                "Auto Dub Master",
                self.studio.run_auto_dub,
            )
            self._add_action(
                sequence_menu,
                "Cancel Active Job",
                self.cancel_dub_job,
                "Esc",
            )

            dub_menu = menu_bar.addMenu("Dub")
            self._add_action(
                dub_menu,
                "Dub Movie…",
                self.open_dub_dialog,
                "Ctrl+Enter",
            )
            self._add_action(
                dub_menu,
                "Cancel Active Job",
                self.cancel_dub_job,
                "Esc",
            )
            sequence_menu.addSeparator()
            self._add_action(
                sequence_menu,
                "Subtitle Quality Control (QC)…",
                self.studio._run_subtitle_qc,
            )
            self._add_action(
                sequence_menu,
                "Dubbing Pipeline Readiness…",
                self.studio._show_pipeline_readiness,
            )

            markers_menu = menu_bar.addMenu("Markers")
            self._add_action(
                markers_menu,
                "Mark In",
                self.studio.mark_in,
                "I",
            )
            self._add_action(
                markers_menu,
                "Mark Out",
                self.studio.mark_out,
                "O",
            )

            graphics_menu = menu_bar.addMenu("Graphics")
            self._add_action(
                graphics_menu,
                "Export Current Frame…",
                self.studio.export_snapshot,
                "Ctrl+Shift+E",
            )
            graphics_menu.addSeparator()
            self._add_action(
                graphics_menu,
                "Import Source Subtitles…",
                self.studio.import_subtitle_dialog,
                "Ctrl+Shift+I",
            )
            self._add_action(
                graphics_menu,
                "Import Target Subtitles…",
                lambda: self.studio.import_subtitle_dialog(target=True),
            )
            self._add_action(
                graphics_menu,
                "Import Audio Asset…",
                self.studio.import_audio_dialog,
            )

            view_menu = menu_bar.addMenu("View")
            self._add_action(view_menu, "Toggle Full Screen", self._toggle_full_screen, "F11")
            theme_menu = view_menu.addMenu("Theme")
            for theme_mode, theme_label in (
                ("studio_dark", "Studio Dark (Default)"),
                ("broadcast_gray", "Broadcast Gray"),
                ("cyber_dark", "Cyber Dark"),
                ("high_contrast", "High Contrast"),
                ("light_studio", "Light Studio"),
            ):
                self._add_action(
                    theme_menu,
                    theme_label,
                    lambda mode=theme_mode: self._set_theme(mode),
                )

            window_menu = menu_bar.addMenu("Window")
            self._add_action(window_menu, "Home Dashboard", self.show_home, "Ctrl+H")
            self._add_action(window_menu, "Dubbing Workspace", self.show_studio)
            self._add_action(
                window_menu,
                "Hardware Diagnostics…",
                self._run_hardware_wizard,
            )

            help_menu = menu_bar.addMenu("Help")
            self._add_action(help_menu, "Command Palette…", self._open_command_palette, "Ctrl+K")
            self._add_action(help_menu, "Keyboard Shortcuts", self.show_keyboard_shortcuts, "F1")
            help_menu.addSeparator()
            self._add_action(
                help_menu,
                "Export Diagnostic Support Bundle…",
                self.export_diagnostic_bundle,
            )
            self._add_action(
                help_menu,
                "Open Logs Folder",
                self.open_logs_directory,
            )
            self._add_action(
                help_menu,
                "Troubleshooting Guide",
                self.show_troubleshooting_guide,
            )
            help_menu.addSeparator()
            self._add_action(help_menu, "About", self._show_about)

        def _open_command_palette(self) -> None:
            from aidub.ui.command_palette import CommandPaletteDialog
            from aidub.ui.commands import Command, CommandRegistry

            registry = CommandRegistry()
            registry.register_many(
                [
                    Command(
                        "media.import",
                        "Import Source Movie",
                        self.studio.import_media_dialog,
                        shortcuts=("Ctrl+O",),
                    ),
                    Command(
                        "ai.autodub",
                        "Dub Movie (Choose Settings)…",
                        self.open_dub_dialog,
                        shortcuts=("Ctrl+Enter",),
                    ),
                    Command(
                        "ai.cancel",
                        "Cancel Active Dub Job",
                        self.cancel_dub_job,
                        shortcuts=("Esc",),
                    ),
                    Command(
                        "clip.rewrite",
                        "Rewrite Selected Translation",
                        self.studio.rewrite_selected_translation,
                    ),
                    Command(
                        "clip.voice",
                        "Regenerate Selected Voice",
                        self.studio.regenerate_selected_voice,
                    ),
                    Command(
                        "export.snapshot",
                        "Export Current Frame",
                        self.studio.export_snapshot,
                        shortcuts=("Ctrl+Shift+E",),
                    ),
                    Command(
                        "view.fullscreen",
                        "Toggle Full Screen",
                        self._toggle_full_screen,
                        shortcuts=("F11",),
                    ),
                ]
            )
            dialog = CommandPaletteDialog(registry, self._locale_service, self)
            dialog.exec()

        def _set_theme(self, mode_name: str) -> None:
            from PySide6.QtWidgets import QApplication

            from aidub.ui.theme import (
                ThemeMode,
                build_enterprise_stylesheet,
                get_theme_tokens,
            )

            tokens = get_theme_tokens(ThemeMode(mode_name))
            style = build_enterprise_stylesheet(tokens)
            app = QApplication.instance()
            if app and hasattr(app, "setStyleSheet"):
                app.setStyleSheet(style)

        @staticmethod
        def _add_action(
            menu: Any,
            label: str,
            callback: Any,
            shortcut: str | None = None,
        ) -> QAction:
            action = QAction(label, menu)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
            return action

        def _apply_locale(self, _locale: str) -> None:
            self.setWindowTitle(self._locale_service("app.title"))
            self.chrome.app_label.setText("AI DUBBING STUDIO")

        def _on_project_loaded(self, project_name: str) -> None:
            self.chrome.set_project(project_name)
            self.setWindowTitle(f"{project_name} — {self._locale_service('app.title')}")

        def _toggle_maximized(self) -> None:
            if self.isMaximized():
                self.showNormal()
                self.chrome.set_maximized(False)
            else:
                self.showMaximized()
                self.chrome.set_maximized(True)

        def _toggle_full_screen(self) -> None:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

        def _show_about(self) -> None:
            QMessageBox.information(
                self,
                "AI Movie Dubbing Studio",
                "Single-workspace AI dubbing production environment.\n\n"
                "Import a movie, configure a target language, and run the agentic "
                "production graph. Generated masters remain review-gated until real QC "
                "measurements are available.",
            )

        def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
            urls = event.mimeData().urls()
            if any(url.isLocalFile() for url in urls):
                event.acceptProposedAction()

        def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
            for url in event.mimeData().urls():
                if not url.isLocalFile():
                    continue
                path = Path(url.toLocalFile())
                if path.is_file():
                    self.studio.open_media_path(path)
            event.acceptProposedAction()

        def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
            if self.studio.has_active_job():
                answer = QMessageBox.question(
                    self,
                    "Dubbing Job Running",
                    "Cancel the active dubbing job and close the Studio?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer is not QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                self.studio.cancel_active_job()
            if hasattr(self, "_jobs_timer"):
                self._jobs_timer.stop()
            if hasattr(self, "_telemetry_worker"):
                self._telemetry_worker.stop()
                self._telemetry_worker.wait(2_000)
            self._unsubscribe_locale()
            event.accept()

__all__ = ["AIDubStudioWindow"]
