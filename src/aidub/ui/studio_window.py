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
        QPushButton,
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
            from aidub.infrastructure.system_telemetry import (  # noqa: PLC0415
                probe_system_telemetry,
            )

            self.completed.emit(probe_system_telemetry(Path.cwd()))


    class _StudioChrome(QFrame):
        """Frameless title/menu bar matching the production reference."""

        def __init__(self, window: "AIDubStudioWindow") -> None:
            super().__init__(window)
            self._window = window
            self.setFixedHeight(42)
            self.setObjectName("StudioChrome")
            self.setStyleSheet(
                "QFrame#StudioChrome{background:#080B10;border-bottom:1px solid #161F2E;}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(12, 0, 8, 0)
            layout.setSpacing(8)

            logo = QLabel("AI", self)
            logo.setStyleSheet(
                "color:#9B6DFF;font-size:16px;font-weight:900;letter-spacing:-1px;"
            )
            layout.addWidget(logo)
            self.app_label = QLabel("AI DUBBING STUDIO", self)
            self.app_label.setStyleSheet("color:#F7F9FC;font-size:11px;font-weight:800;")
            layout.addWidget(self.app_label)

            self.menu_bar = QMenuBar(self)
            self.menu_bar.setNativeMenuBar(False)
            self.menu_bar.setStyleSheet(
                "QMenuBar{background:transparent;color:#A9B2C3;font-size:10px;}"
                "QMenuBar::item{padding:5px 7px;background:transparent;}"
                "QMenuBar::item:selected{background:#1C2636;color:#FFF;border-radius:3px;}"
                "QMenu{background:#111722;color:#E2E8F0;border:1px solid #283446;}"
                "QMenu::item{padding:6px 26px 6px 12px;}"
                "QMenu::item:selected{background:#2563EB;color:#FFF;}"
                "QMenu::separator{height:1px;background:#283446;margin:4px 8px;}"
            )
            layout.addWidget(self.menu_bar)
            layout.addStretch(2)

            self.project_label = QLabel("NO PROJECT", self)
            self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_label.setMinimumWidth(220)
            self.project_label.setStyleSheet("color:#CBD5E1;font-size:10px;font-weight:600;")
            layout.addWidget(self.project_label)
            layout.addStretch(2)

            self.gpu_label = QLabel("GPU  —", self)
            self.vram_label = QLabel("VRAM  —", self)
            self.jobs_label = QLabel("JOBS  0", self)
            for label in (self.gpu_label, self.vram_label, self.jobs_label):
                label.setStyleSheet("color:#8C9BAE;font-size:10px;font-weight:600;")
                layout.addWidget(label)

            for text, tooltip, callback in (
                ("—", "Minimize", window.showMinimized),
                ("□", "Maximize / Restore", window._toggle_maximized),
                ("×", "Close", window.close),
            ):
                button = QPushButton(text, self)
                button.setToolTip(tooltip)
                button.setFixedSize(30, 26)
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#A9B2C3;border:none;"
                    "font-size:13px;}QPushButton:hover{background:#1C2636;color:#FFF;}"
                )
                if text == "×":
                    button.setStyleSheet(
                        "QPushButton{background:transparent;color:#A9B2C3;border:none;"
                        "font-size:16px;}QPushButton:hover{background:#B4232E;color:#FFF;}"
                    )
                button.clicked.connect(callback)
                layout.addWidget(button)

        def set_project(self, project_name: str) -> None:
            self.project_label.setText(project_name.upper())

        def set_telemetry(self, report: object) -> None:
            gpu_usage = int(getattr(report, "gpu_usage_pct", 0))
            vram_used = float(getattr(report, "vram_used_gb", 0.0))
            vram_total = float(getattr(report, "vram_total_gb", 0.0))
            gpu_name = str(getattr(report, "gpu_name", "Unavailable"))
            self.gpu_label.setText(
                f"GPU  {gpu_usage}%" if gpu_name != "Unavailable" else "GPU  N/A"
            )
            self.gpu_label.setToolTip(gpu_name)
            self.vram_label.setText(
                f"VRAM  {vram_used:.1f} / {vram_total:.1f} GB"
                if vram_total > 0
                else "VRAM  N/A"
            )

        def set_jobs(self, count: int) -> None:
            self.jobs_label.setText(f"JOBS  {count}")

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
        """One authoritative Studio surface; no secondary screen registry."""

        def __init__(
            self,
            locale_service: LocaleService | None = None,
            parent: Any | None = None,
        ) -> None:
            super().__init__(parent)
            if locale_service is None:
                from aidub.i18n import LocaleService  # noqa: PLC0415

                locale_service = LocaleService()

            from aidub.ui.screens.timeline_editor import TimelineScreen  # noqa: PLC0415

            self._locale_service = locale_service
            self._unsubscribe_locale = self._locale_service.subscribe(self._apply_locale)
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowSystemMenuHint
            )
            self.studio = TimelineScreen(self)
            self.setCentralWidget(self.studio)
            self.setObjectName("AIDubStudioWindow")
            self.setAcceptDrops(True)
            self.setMinimumSize(1_200, 760)
            self.resize(1_600, 960)
            self.chrome = _StudioChrome(self)
            self.setMenuWidget(self.chrome)
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
            file_menu.addSeparator()
            self._add_action(file_menu, "Exit", self.close, "Alt+F4")

            edit_menu = menu_bar.addMenu("Edit")
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
                "Regenerate Selected Voice",
                self.studio.regenerate_selected_voice,
            )
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
                "Set Target Language…",
                self.studio.configure_target_language,
            )

            ai_menu = menu_bar.addMenu("AI")
            self._add_action(
                ai_menu,
                "Auto Dub Master",
                self.studio.run_auto_dub,
                "Ctrl+Enter",
            )
            self._add_action(
                ai_menu,
                "Cancel Active Job",
                self.studio.cancel_active_job,
                "Esc",
            )

            audio_menu = menu_bar.addMenu("Audio")
            self._add_action(
                audio_menu,
                "Import Audio Asset…",
                self.studio.import_audio_dialog,
            )

            subtitle_menu = menu_bar.addMenu("Subtitle")
            self._add_action(
                subtitle_menu,
                "Import Source Subtitles…",
                self.studio.import_subtitle_dialog,
                "Ctrl+Shift+I",
            )
            self._add_action(
                subtitle_menu,
                "Import Target Subtitles…",
                lambda: self.studio.import_subtitle_dialog(target=True),
            )

            render_menu = menu_bar.addMenu("Render")
            self._add_action(
                render_menu,
                "Auto Dub Master",
                self.studio.run_auto_dub,
            )
            self._add_action(
                render_menu,
                "Export Current Frame…",
                self.studio.export_snapshot,
                "Ctrl+Shift+E",
            )

            view_menu = menu_bar.addMenu("View")
            self._add_action(view_menu, "Toggle Full Screen", self._toggle_full_screen, "F11")

            help_menu = menu_bar.addMenu("Help")
            self._add_action(help_menu, "About", self._show_about)

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
            self.chrome.app_label.setText(self._locale_service("app.title").upper())

        def _on_project_loaded(self, project_name: str) -> None:
            self.chrome.set_project(project_name)
            self.setWindowTitle(f"{project_name} — {self._locale_service('app.title')}")

        def _toggle_maximized(self) -> None:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

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
            if self._telemetry_worker.isRunning():
                self._telemetry_worker.wait(4_000)
            self._unsubscribe_locale()
            event.accept()


else:

    class AIDubStudioWindow:  # pragma: no cover
        """Import-safe diagnostic when the optional desktop dependency is absent."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("PySide6 is required for the desktop Studio")


__all__ = ["AIDubStudioWindow"]
