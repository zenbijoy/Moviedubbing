"""Single-window production shell for AI Movie Dubbing Studio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtGui import (
        QAction,
        QCloseEvent,
        QDragEnterEvent,
        QDropEvent,
        QKeyEvent,
        QKeySequence,
        QMouseEvent,
    )
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenuBar,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QStackedWidget,
        QToolBar,
        QVBoxLayout,
    )

    _QT = True
except ImportError:
    _QT = False

if TYPE_CHECKING:
    from aidub.i18n import LocaleService


if _QT:

    class _TelemetryWorker(QThread):
        completed = Signal(object)

        def run(self) -> None:
            from aidub.infrastructure.system_telemetry import (
                probe_system_telemetry,
            )

            self.completed.emit(probe_system_telemetry(Path.cwd()))

    class _HomeDashboardPanel(QFrame):
        """Home overview dashboard for project selection, hardware stats, and navigation."""

        def __init__(self, window: AIDubStudioWindow) -> None:
            super().__init__(window)
            self._window = window
            self.setObjectName("HomeDashboardPanel")
            self.setStyleSheet("QFrame#HomeDashboardPanel{background:#0D1118;color:#F7F9FC;}")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(40, 30, 40, 30)
            layout.setSpacing(24)

            # Hero Banner
            hero = QFrame(self)
            hero.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #161D28,stop:1 #1C2431);"
                "border:1px solid #283241;border-radius:12px;padding:24px;"
            )
            h_layout = QVBoxLayout(hero)
            title = QLabel("AI MOVIE DUBBING STUDIO", hero)
            title.setStyleSheet("font-size:24px;font-weight:900;color:#F7F9FC;letter-spacing:1px;")
            subtitle = QLabel("Local-First Professional Multilingual Editorial Workstation", hero)
            subtitle.setStyleSheet("font-size:13px;color:#9CA3AF;margin-top:4px;")
            h_layout.addWidget(title)
            h_layout.addWidget(subtitle)
            layout.addWidget(hero)

            # Cards row
            cards_layout = QHBoxLayout()
            cards_layout.setSpacing(18)

            # Card 1: Import / Open Project
            c1 = QFrame(self)
            c1.setStyleSheet(
                "QFrame{background:#161D28;border:1px solid #283241;border-radius:10px;padding:16px;}"
                "QFrame:hover{border-color:#4F8CFF;}"
            )
            c1_lay = QVBoxLayout(c1)
            c1_t = QLabel("📁  Import Source Movie", c1)
            c1_t.setStyleSheet("font-size:15px;font-weight:700;color:#F7F9FC;")
            c1_d = QLabel(
                "Load a video file to begin automated transcription, translation, and dubbing.", c1
            )
            c1_d.setWordWrap(True)
            c1_d.setStyleSheet("font-size:12px;color:#9CA3AF;margin-top:6px;")
            c1_btn = QPushButton("Open Media Movie…", c1)
            c1_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c1_btn.setStyleSheet(
                "QPushButton{background:#4F8CFF;color:#FFF;font-weight:700;padding:8px 16px;border-radius:6px;}"
                "QPushButton:hover{background:#3B82F6;}"
            )
            c1_btn.clicked.connect(window.import_from_home)
            c1_lay.addWidget(c1_t)
            c1_lay.addWidget(c1_d)
            c1_lay.addStretch()
            c1_lay.addWidget(c1_btn)
            cards_layout.addWidget(c1, stretch=1)

            # Card 2: NLE Editorial Studio Timeline
            c2 = QFrame(self)
            c2.setStyleSheet(
                "QFrame{background:#161D28;border:1px solid #283241;border-radius:10px;padding:16px;}"
                "QFrame:hover{border-color:#8B5CF6;}"
            )
            c2_lay = QVBoxLayout(c2)
            c2_t = QLabel("🎬  Timeline Editor", c2)
            c2_t.setStyleSheet("font-size:15px;font-weight:700;color:#F7F9FC;")
            c2_d = QLabel(
                "Multi-track editorial workspace with dual monitor, inspector, waveform, and AI overlay.",
                c2,
            )
            c2_d.setWordWrap(True)
            c2_d.setStyleSheet("font-size:12px;color:#9CA3AF;margin-top:6px;")
            c2_btn = QPushButton("Go to Timeline Studio →", c2)
            c2_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c2_btn.setStyleSheet(
                "QPushButton{background:#8B5CF6;color:#FFF;font-weight:700;padding:8px 16px;border-radius:6px;}"
                "QPushButton:hover{background:#7C3AED;}"
            )
            c2_btn.clicked.connect(window.show_studio)
            c2_lay.addWidget(c2_t)
            c2_lay.addWidget(c2_d)
            c2_lay.addStretch()
            c2_lay.addWidget(c2_btn)
            cards_layout.addWidget(c2, stretch=1)

            # Card 3: First Run Hardware Wizard
            c3 = QFrame(self)
            c3.setStyleSheet(
                "QFrame{background:#161D28;border:1px solid #283241;border-radius:10px;padding:16px;}"
                "QFrame:hover{border-color:#10B981;}"
            )
            c3_lay = QVBoxLayout(c3)
            c3_t = QLabel("⚡  Hardware Diagnostics", c3)
            c3_t.setStyleSheet("font-size:15px;font-weight:700;color:#F7F9FC;")
            c3_d = QLabel(
                "Probe GPU VRAM, CPU cores, FFmpeg runtime, and calibrate execution tier.", c3
            )
            c3_d.setWordWrap(True)
            c3_d.setStyleSheet("font-size:12px;color:#9CA3AF;margin-top:6px;")
            c3_btn = QPushButton("Run Hardware Self-Test", c3)
            c3_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c3_btn.setStyleSheet(
                "QPushButton{background:#10B981;color:#FFF;font-weight:700;padding:8px 16px;border-radius:6px;}"
                "QPushButton:hover{background:#059669;}"
            )
            c3_btn.clicked.connect(window._run_hardware_wizard)
            c3_lay.addWidget(c3_t)
            c3_lay.addWidget(c3_d)
            c3_lay.addStretch()
            c3_lay.addWidget(c3_btn)
            cards_layout.addWidget(c3, stretch=1)

            layout.addLayout(cards_layout)
            layout.addStretch()

    class _StudioChrome(QFrame):
        """Frameless title/menu bar matching the production reference."""

        def __init__(self, window: AIDubStudioWindow) -> None:
            super().__init__(window)
            self._window = window
            self.setFixedHeight(42)
            self.setObjectName("StudioChrome")
            self.setStyleSheet(
                "QFrame#StudioChrome{background:#080B10;border-bottom:1px solid #161F2E;}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(16, 0, 0, 0)
            layout.setSpacing(8)

            logo = QLabel("AI", self)
            logo.setFixedWidth(24)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setStyleSheet("color:#A970FF;font-size:18px;font-weight:900;letter-spacing:-2px;")
            layout.addWidget(logo)
            self.app_label = QLabel("AI DUBBING STUDIO", self)
            self.app_label.setFixedWidth(144)
            self.app_label.setStyleSheet("color:#F7F9FC;font-size:12px;font-weight:800;")
            layout.addWidget(self.app_label)

            self.menu_bar = QMenuBar(self)
            self.menu_bar.setNativeMenuBar(False)
            self.menu_bar.setMinimumWidth(440)
            self.menu_bar.setMaximumWidth(540)
            self.menu_bar.setStyleSheet(
                "QMenuBar{background:transparent;color:#C4CAD4;font-size:11px;}"
                "QMenuBar::item{padding:5px 8px;background:transparent;}"
                "QMenuBar::item:selected{background:#1C2636;color:#FFF;border-radius:3px;}"
                "QMenu{background:#111722;color:#E2E8F0;border:1px solid #283446;}"
                "QMenu::item{padding:6px 26px 6px 12px;}"
                "QMenu::item:selected{background:#2563EB;color:#FFF;}"
                "QMenu::separator{height:1px;background:#283446;margin:4px 8px;}"
            )
            layout.addWidget(self.menu_bar)

            self.dub_btn = QPushButton("🎙 Dub", self)
            self.dub_btn.setToolTip("Dub Movie (pick language & Fast/Quality profile) — Ctrl+Enter")
            self.dub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dub_btn.setStyleSheet(
                "QPushButton {"
                "  background: #2563EB; color: #FFF; border: none; border-radius: 4px;"
                "  padding: 4px 14px; font-size: 11px; font-weight: 800;"
                "}"
                "QPushButton:hover { background: #3B82F6; }"
                "QPushButton:disabled { background: #1C2431; color: #64748B; }"
            )
            self.dub_btn.clicked.connect(window.open_dub_dialog)
            layout.addWidget(self.dub_btn)

            layout.addStretch(1)

            self.project_label = QLabel("Untitled - Bengali Dub ⌄", self)
            self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_label.setFixedWidth(260)
            self.project_label.setStyleSheet("color:#E1E5EC;font-size:11px;font-weight:600;")
            layout.addWidget(self.project_label)
            layout.addStretch(3)

            self.gpu_label = QLabel("GPU  N/A", self)
            self.vram_label = QLabel("VRAM  N/A", self)
            self.jobs_label = QLabel("Jobs  0", self)
            self.gpu_label.setFixedWidth(76)
            self.vram_label.setFixedWidth(128)
            self.jobs_label.setFixedWidth(58)
            for label in (self.gpu_label, self.vram_label, self.jobs_label):
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("color:#B7BECA;font-size:11px;font-weight:600;")
                layout.addWidget(label)

            for _index in range(2):
                divider = QFrame(self)
                divider.setFixedSize(1, 22)
                divider.setStyleSheet("background:#202631;")
                insert_at = layout.count() - (2 - _index)
                layout.insertWidget(insert_at, divider)

            self.max_btn: QPushButton | None = None
            for text, tooltip, callback in (
                ("—", "Minimize", window.showMinimized),
                ("□", "Maximize / Restore", window._toggle_maximized),
                ("×", "Close", window.close),
            ):
                button = QPushButton(text, self)
                button.setToolTip(tooltip)
                button.setFixedSize(38, 42)
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#A9B2C3;border:none;"
                    "font-size:14px;padding:0;min-height:0;}"
                    "QPushButton:hover{background:#1C2636;color:#FFF;}"
                )
                if text == "□":
                    self.max_btn = button
                elif text == "×":
                    button.setStyleSheet(
                        "QPushButton{background:transparent;color:#A9B2C3;border:none;"
                        "font-size:16px;}QPushButton:hover{background:#B4232E;color:#FFF;}"
                    )
                button.clicked.connect(callback)
                layout.addWidget(button)

        def set_maximized(self, is_maximized: bool) -> None:
            if self.max_btn is not None:
                self.max_btn.setText("❐" if is_maximized else "□")

        def set_project(self, project_name: str) -> None:
            self.project_label.setText(f"{project_name} - Bengali Dub ⌄")
            self.project_label.setToolTip(project_name)

        def set_telemetry(self, report: object) -> None:
            gpu_usage = int(getattr(report, "gpu_usage_pct", 0))
            vram_used = float(getattr(report, "vram_used_gb", 0.0))
            vram_total = float(getattr(report, "vram_total_gb", 0.0))
            gpu_name = str(getattr(report, "gpu_name", "Unavailable"))
            self.gpu_label.setText(
                f"GPU  {gpu_usage}%" if gpu_name != "Unavailable" else "GPU  N/A"
            )
            self.gpu_label.setStyleSheet(
                "color:#63D46E;font-size:11px;font-weight:700;"
                if gpu_name != "Unavailable"
                else "color:#8C94A2;font-size:11px;font-weight:600;"
            )
            self.gpu_label.setToolTip(gpu_name)
            self.vram_label.setText(
                f"VRAM  {vram_used:.1f} / {vram_total:.1f} GB" if vram_total > 0 else "VRAM  N/A"
            )
            self.vram_label.setStyleSheet(
                "color:#57A5F8;font-size:11px;font-weight:700;"
                if vram_total > 0
                else "color:#8C94A2;font-size:11px;font-weight:600;"
            )

        def set_jobs(self, count: int) -> None:
            self.jobs_label.setText(f"Jobs  {count}")
            self.jobs_label.setStyleSheet(
                "color:#63D46E;font-size:11px;font-weight:700;"
                if count
                else "color:#B7BECA;font-size:11px;font-weight:600;"
            )

        def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() is Qt.MouseButton.LeftButton:
                self._window._toggle_maximized()
                event.accept()
                return
            super().mouseDoubleClickEvent(event)

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() is Qt.MouseButton.LeftButton:
                handle = self._window.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                    event.accept()
                    return
            super().mousePressEvent(event)

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
            self.home_view = _HomeDashboardPanel(self)
            self.studio = TimelineScreen(self)
            self.stack.addWidget(self.home_view)
            self.stack.addWidget(self.studio)
            self.stack.setCurrentWidget(self.studio)
            self.setCentralWidget(self.stack)

            self.setObjectName("AIDubStudioWindow")
            self.setAcceptDrops(True)
            self.setMinimumSize(1_200, 760)
            self.resize(1_600, 960)
            self.chrome = _StudioChrome(self)
            self.setMenuWidget(self.chrome)
            self._build_toolbar()
            self._build_menus()
            self.studio.project_loaded.connect(self._on_project_loaded)
            self._jobs_timer = QTimer(self)
            self._jobs_timer.setInterval(500)
            self._jobs_timer.timeout.connect(
                lambda: self.chrome.set_jobs(1 if self.studio.has_active_job() else 0)
            )
            self._jobs_timer.start()
            self._telemetry_worker = _TelemetryWorker(self)
            self._telemetry_worker.completed.connect(self.chrome.set_telemetry)
            self._telemetry_worker.start()
            self._apply_locale(self._locale_service.locale)

        def _build_toolbar(self) -> None:
            toolbar = QToolBar("Main Dubbing Toolbar", self)
            toolbar.setObjectName("MainToolBar")
            toolbar.setMovable(False)
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
            self.dub_action.setToolTip("Dub Movie (pick language & Fast/Quality profile) — Ctrl+Enter")
            self.dub_action.setShortcut(QKeySequence("Ctrl+Enter"))
            self.dub_action.triggered.connect(self.open_dub_dialog)

            self.cancel_action = toolbar.addAction("Cancel")
            self.cancel_action.setToolTip("Cancel Active Dubbing Job — Esc")
            self.cancel_action.setEnabled(False)
            self.cancel_action.triggered.connect(self.cancel_dub_job)

            toolbar.addSeparator()

            self.toolbar_stage_label = QLabel("", toolbar)
            self.toolbar_stage_label.setStyleSheet("color:#38BDF8;font-size:11px;font-weight:600;padding:0 6px;")
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

        def show_studio(self) -> None:
            self.stack.setCurrentWidget(self.studio)

        def import_from_home(self) -> None:
            self.show_studio()
            self.studio.import_media_dialog()

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
            if hasattr(self, "_telemetry_worker") and self._telemetry_worker.isRunning():
                self._telemetry_worker.quit()
                self._telemetry_worker.wait(4_000)
            self._unsubscribe_locale()
            event.accept()


else:

    class AIDubStudioWindow:  # type: ignore[no-redef]  # pragma: no cover
        """Import-safe diagnostic when the optional desktop dependency is absent."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("PySide6 is required for the desktop Studio")


__all__ = ["AIDubStudioWindow"]
