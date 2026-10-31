"""Single-window production shell for AI Movie Dubbing Studio."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
    from PySide6.QtGui import (
        QAction,
        QBrush,
        QCloseEvent,
        QColor,
        QDesktopServices,
        QDragEnterEvent,
        QDropEvent,
        QKeyEvent,
        QKeySequence,
        QMouseEvent,
        QPainter,
        QPaintEvent,
        QPen,
    )
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMenuBar,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QStackedWidget,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False

if TYPE_CHECKING:
    from aidub.i18n import LocaleService


if _QT:

    class _TelemetryWorker(QThread):
        completed = Signal(object)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._running = True

        def stop(self) -> None:
            self._running = False

        def run(self) -> None:
            from aidub.infrastructure.system_telemetry import (
                probe_system_telemetry,
            )

            while self._running:
                try:
                    self.completed.emit(probe_system_telemetry(Path.cwd()))
                except Exception:
                    pass
                for _ in range(15):
                    if not self._running:
                        break
                    self.msleep(100)

    class _WaveformCanvas(QWidget):
        """Sleek animated waveform visualizer for real speech preview."""

        def __init__(self, color_hex: str = "#22D3EE", parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.color_hex = color_hex
            self.progress = 0.18
            self.setFixedHeight(72)
            self.setMinimumWidth(210)
            import math

            self.bars = [
                0.12
                + 0.88 * abs(math.sin(i * 0.22) * math.cos(i * 0.08) * math.sin(i * 0.41 + 0.2))
                for i in range(60)
            ]

        def set_progress(self, val: float) -> None:
            self.progress = max(0.0, min(1.0, val))
            self.update()

        def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mid_y = h / 2.0
            n_bars = len(self.bars)
            spacing = 2.0
            bar_w = max(2.0, (w - (n_bars * spacing)) / max(1, n_bars))

            # Subtle card backdrop
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#080D16")))
            painter.drawRoundedRect(0, 0, w, h, 6, 6)

            # Centerline
            painter.setPen(QPen(QColor("#182232"), 1))
            painter.drawLine(0, int(mid_y), w, int(mid_y))

            base_color = QColor(self.color_hex)
            for i, peak in enumerate(self.bars):
                x = i * (bar_w + spacing)
                bar_h = max(4.0, peak * (h * 0.82))
                y = mid_y - (bar_h / 2.0)
                is_played = (x / max(1.0, w)) <= self.progress

                if is_played:
                    painter.setBrush(QBrush(base_color))
                else:
                    dimmed = QColor(base_color)
                    dimmed.setAlpha(60)
                    painter.setBrush(QBrush(dimmed))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)

            # Glowing Playhead
            px = int(self.progress * w)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(px, 0, px, h)
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.drawEllipse(px - 3, int(mid_y) - 3, 6, 6)

    class _ModernActionCard(QFrame):
        """Quick action card with glowing icon badge matching modern studio design."""

        def __init__(
            self,
            title: str,
            subtitle: str,
            icon_char: str,
            icon_bg: str,
            callback: Any = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(
                f"QFrame {{"
                f"  background: #121722; border: 1px solid #1E293B; border-radius: 12px; padding: 12px 14px;"
                f"}}"
                f"QFrame:hover {{"
                f"  background: #171E2E; border-color: {icon_bg};"
                f"}}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(14)

            badge = QLabel(icon_char, self)
            badge.setFixedSize(46, 46)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {icon_bg}; color: #FFFFFF; border-radius: 23px; font-size: 20px; border: 1px solid rgba(255,255,255,0.18);"
            )
            layout.addWidget(badge)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t_lbl = QLabel(title, self)
            t_lbl.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #F8FAFC; letter-spacing: -0.2px;")
            s_lbl = QLabel(subtitle, self)
            s_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #94A3B8;")
            text_col.addWidget(t_lbl)
            text_col.addWidget(s_lbl)
            layout.addLayout(text_col, 1)

            plus_btn = QPushButton("+", self)
            plus_btn.setFixedSize(28, 28)
            plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            plus_btn.setStyleSheet(
                "QPushButton { background: #1C2434; color: #E2E8F0; border-radius: 14px; font-size: 16px; font-weight: 700; border: 1px solid #2B384E; }"
                "QPushButton:hover { background: #2563EB; color: #FFF; border-color: #3B82F6; }"
            )
            if callback:
                plus_btn.clicked.connect(callback)
            layout.addWidget(plus_btn)

            self._callback = callback

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self._callback:
                self._callback()
            super().mousePressEvent(event)

    def _format_rel_time(dt: datetime) -> str:
        try:
            now = datetime.now(dt.tzinfo or UTC)
            diff = now - dt
            total_seconds = int(diff.total_seconds())
            if total_seconds < 60:
                return "Just now"
            if total_seconds < 3600:
                mins = total_seconds // 60
                return f"{mins} min{'s' if mins > 1 else ''} ago"
            if total_seconds < 86400:
                hrs = total_seconds // 3600
                return f"{hrs} hr{'s' if hrs > 1 else ''} ago"
            days = total_seconds // 86400
            if days == 1:
                return "Yesterday"
            if days < 30:
                return f"{days} days ago"
            return dt.strftime("%b %d, %Y")
        except Exception:
            return "Recently"

    class _ProjectCard(QFrame):
        """Card representing a video project matching modern NLE card layout."""

        def __init__(
            self,
            title: str,
            created_text: str,
            dubbed_pill_text: str,
            video_path: str = "",
            on_open: Any = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(
                "QFrame {"
                "  background: #121724; border: 1px solid #1E293B; border-radius: 10px; padding: 12px 14px;"
                "}"
                "QFrame:hover {"
                "  background: #171E2F; border-color: #38BDF8;"
                "}"
            )
            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)

            top_row = QHBoxLayout()
            v_badge = QLabel("🎥", self)
            v_badge.setFixedSize(32, 32)
            v_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_badge.setStyleSheet(
                "background: #1E293B; color: #38BDF8; border-radius: 8px; font-size: 15px;"
            )
            top_row.addWidget(v_badge)

            title_box = QVBoxLayout()
            title_box.setSpacing(2)
            t_lbl = QLabel(title, self)
            t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F8FAFC; letter-spacing: -0.1px;")
            c_lbl = QLabel(created_text, self)
            c_lbl.setStyleSheet("font-size: 10px; color: #64748B; font-weight: 500;")
            title_box.addWidget(t_lbl)
            title_box.addWidget(c_lbl)
            top_row.addLayout(title_box, 1)

            dots_btn = QPushButton("⋮", self)
            dots_btn.setFixedSize(24, 24)
            dots_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #64748B; border: none; font-size: 15px; font-weight: bold; border-radius: 4px; }"
                "QPushButton:hover { color: #FFF; background: #1E293B; }"
            )
            dots_btn.clicked.connect(self._show_options_menu)
            top_row.addWidget(dots_btn)
            layout.addLayout(top_row)

            pill_row = QHBoxLayout()
            pill_lbl = QLabel(f"Dubbed to: {dubbed_pill_text}", self)
            pill_lbl.setStyleSheet(
                "background: #0B111D; color: #94A3B8; border: 1px solid #1E293B; border-radius: 4px;"
                "padding: 3px 8px; font-size: 10px; font-weight: 600;"
            )
            pill_row.addWidget(pill_lbl)
            pill_row.addStretch()

            ready_pill = QLabel("● Ready", self)
            ready_pill.setStyleSheet("color: #10B981; font-size: 10px; font-weight: 700;")
            pill_row.addWidget(ready_pill)
            layout.addLayout(pill_row)

            self._on_open = on_open
            self._video_path = video_path

        def _show_options_menu(self) -> None:
            menu = QMenu(self)
            menu.setStyleSheet(
                "QMenu { background: #141822; color: #F1F5F9; border: 1px solid #232C3E; border-radius: 6px; padding: 4px; }"
                "QMenu::item { padding: 6px 14px; border-radius: 4px; font-size: 11px; }"
                "QMenu::item:selected { background: #2563EB; color: #FFF; }"
            )
            act_open = menu.addAction("Open Project")
            act_open.triggered.connect(
                lambda: self._on_open(self._video_path) if self._on_open else None
            )

            if self._video_path and Path(self._video_path).exists():
                act_explore = menu.addAction("Show in File Explorer")
                act_explore.triggered.connect(
                    lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(Path(self._video_path).resolve().parent))
                    )
                )

            act_remove = menu.addAction("Remove from Recents")

            def _remove() -> None:
                from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

                catalog = ProjectCatalog(default_catalog_path())
                try:
                    p = catalog.get_project_by_path(self._video_path)
                    if p:
                        catalog.remove_project(p.project_id)
                except Exception:
                    pass
                p_widget = self.parentWidget()
                while p_widget is not None and not hasattr(p_widget, "refresh_projects"):
                    p_widget = p_widget.parentWidget()
                if p_widget is not None and hasattr(p_widget, "refresh_projects"):
                    p_widget.refresh_projects()

            act_remove.triggered.connect(_remove)
            dots = self.findChild(QPushButton)
            menu.exec(
                dots.mapToGlobal(dots.rect().bottomLeft())
                if dots
                else self.mapToGlobal(self.rect().center())
            )

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self._on_open:
                if self._video_path:
                    self._on_open(self._video_path)
                else:
                    self._on_open()
            super().mousePressEvent(event)

    class _HomeDashboardPanel(QFrame):
        """Ultra-Modern AI Studio Hub & Dashboard."""

        def __init__(self, window: AIDubStudioWindow) -> None:
            super().__init__(window)
            self._window = window
            self.setObjectName("HomeDashboardPanel")
            self.setStyleSheet("QFrame#HomeDashboardPanel{background:#0B0E14;color:#F8FAFC;}")

            root_layout = QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # =================================================================
            # 1. Left Sidebar Navigation
            # =================================================================
            sidebar = QFrame(self)
            sidebar.setFixedWidth(230)
            sidebar.setStyleSheet("background: #0D1017; border-right: 1px solid #1B212D;")
            sb_layout = QVBoxLayout(sidebar)
            sb_layout.setContentsMargins(14, 16, 14, 16)
            sb_layout.setSpacing(6)

            # Workspace Card
            ws_card = QFrame(sidebar)
            ws_card.setStyleSheet(
                "background: #141822; border: 1px solid #232C3E; border-radius: 8px; padding: 6px 8px;"
            )
            ws_lay = QHBoxLayout(ws_card)
            ws_lay.setContentsMargins(4, 4, 4, 4)
            ws_lay.setSpacing(8)

            ws_av = QLabel("AI", ws_card)
            ws_av.setFixedSize(28, 28)
            ws_av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ws_av.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #8B5CF6);"
                "color: #FFF; font-size: 11px; font-weight: 900; border-radius: 14px;"
            )
            ws_lay.addWidget(ws_av)

            ws_txt = QVBoxLayout()
            ws_txt.setSpacing(1)
            ws_l1 = QLabel("Current Workspace", ws_card)
            ws_l1.setStyleSheet("font-size: 9px; color: #64748B; font-weight: 600;")
            ws_l2 = QLabel("AI Movie Dubbing Studio ⌄", ws_card)
            ws_l2.setStyleSheet("font-size: 11px; color: #F1F5F9; font-weight: 700;")
            ws_txt.addWidget(ws_l1)
            ws_txt.addWidget(ws_l2)
            ws_lay.addLayout(ws_txt, 1)

            pro_badge = QLabel("PRO", ws_card)
            pro_badge.setStyleSheet(
                "background: #312E81; color: #A5B4FC; border-radius: 4px; padding: 2px 5px; font-size: 9px; font-weight: 800;"
            )
            ws_lay.addWidget(pro_badge)
            sb_layout.addWidget(ws_card)

            sb_layout.addSpacing(10)

            def _nav_btn(text: str, is_active: bool = False, cb: Any = None) -> QPushButton:
                btn = QPushButton(text, sidebar)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(34)
                if is_active:
                    btn.setStyleSheet(
                        "QPushButton { background: #1C2433; color: #38BDF8; font-size: 12px; font-weight: 700;"
                        "border-radius: 6px; text-align: left; padding-left: 10px; border: none; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background: transparent; color: #94A3B8; font-size: 12px; font-weight: 500;"
                        "border-radius: 6px; text-align: left; padding-left: 10px; border: none; }"
                        "QPushButton:hover { background: #161C26; color: #F1F5F9; }"
                    )
                if cb:
                    btn.clicked.connect(cb)
                return btn

            # Section: WORKSPACE
            sec1 = QLabel("WORKSPACE", sidebar)
            sec1.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;"
            )
            sb_layout.addWidget(sec1)
            sb_layout.addWidget(_nav_btn("🏠  Home", is_active=True))
            sb_layout.addWidget(_nav_btn("🎥  Dubbed Videos", cb=window.show_studio))
            sb_layout.addWidget(_nav_btn("🎙️  Text To Speech", cb=window.open_voice_model_dialog))
            sb_layout.addWidget(_nav_btn("🔤  Text Translate", cb=window.open_isometric_dialog))
            sb_layout.addWidget(_nav_btn("☁️  Kaggle Cloud GPU", cb=window.open_kaggle_dialog))
            sb_layout.addWidget(
                _nav_btn("📊  Insights  ✦ PRO", cb=window.open_broadcast_export_dialog)
            )

            sb_layout.addSpacing(10)

            # Section: PERSONAL
            sec2 = QLabel("PERSONAL", sidebar)
            sec2.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;"
            )
            sb_layout.addWidget(sec2)
            sb_layout.addWidget(_nav_btn("👥  Voice Library (RVC)", cb=window.open_casting_dialog))
            sb_layout.addWidget(_nav_btn("🎬  Timeline Editor", cb=window.show_studio))

            sb_layout.addSpacing(10)

            # Section: RESOURCES
            sec3 = QLabel("RESOURCES", sidebar)
            sec3.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;"
            )
            sb_layout.addWidget(sec3)
            sb_layout.addWidget(_nav_btn("🔌  Integrations", cb=window.open_preferences_dialog))
            sb_layout.addWidget(_nav_btn("❓  Help Center", cb=window.open_keyboard_shortcuts))

            sb_layout.addStretch()

            # Bottom System Status Card
            sys_card = QFrame(sidebar)
            sys_card.setStyleSheet(
                "background: #11151F; border: 1px solid #1E273A; border-radius: 8px; padding: 10px;"
            )
            sc_lay = QVBoxLayout(sys_card)
            sc_lay.setContentsMargins(6, 6, 6, 6)
            sc_lay.setSpacing(4)
            sc_title = QLabel("SYSTEM STATUS", sys_card)
            sc_title.setStyleSheet("font-size: 8.5px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
            sc_lay.addWidget(sc_title)
            sc_info = QLabel("⚡ GPU Engine Ready", sys_card)
            sc_info.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #10B981;")
            sc_lay.addWidget(sc_info)
            sc_meta = QLabel("Local SQLite • 7-Stage NLE", sys_card)
            sc_meta.setStyleSheet("font-size: 9.5px; color: #94A3B8;")
            sc_lay.addWidget(sc_meta)
            sb_layout.addWidget(sys_card)

            root_layout.addWidget(sidebar)

            # =================================================================
            # 2. Main Dashboard Area with ScrollArea
            # =================================================================
            scroll_area = QScrollArea(self)
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet("QScrollArea{background:transparent;border:none;}")

            main_pane = QFrame(scroll_area)
            main_pane.setStyleSheet("background: #0B0E14;")
            mp_lay = QVBoxLayout(main_pane)
            mp_lay.setContentsMargins(36, 24, 36, 24)
            mp_lay.setSpacing(18)

            # Top Breadcrumb & User Profile Row
            top_bar = QHBoxLayout()
            h_lbl = QLabel("HOME / STUDIO DASHBOARD", main_pane)
            h_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;"
            )
            top_bar.addWidget(h_lbl)
            top_bar.addStretch()

            # Quick Action Buttons in Top Bar
            new_btn = QPushButton("+ New Project", main_pane)
            new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            new_btn.setStyleSheet(
                "QPushButton { background: #2563EB; color: #FFF; border: none; border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #1D4ED8; }"
            )
            new_btn.clicked.connect(window.create_new_project_dialog)
            top_bar.addWidget(new_btn)

            open_btn = QPushButton("📂 Open .aidub", main_pane)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet(
                "QPushButton { background: #141822; color: #CBD5E1; border: 1px solid #232C3E; border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #1B2232; color: #FFF; border-color: #38BDF8; }"
            )
            open_btn.clicked.connect(window.open_project_dialog)
            top_bar.addWidget(open_btn)

            user_pill = QFrame(main_pane)
            user_pill.setStyleSheet(
                "background: #141822; border: 1px solid #232C3E; border-radius: 16px; padding: 2px 8px;"
            )
            u_lay = QHBoxLayout(user_pill)
            u_lay.setContentsMargins(4, 2, 6, 2)
            u_lay.setSpacing(6)
            u_av = QLabel("TM", user_pill)
            u_av.setFixedSize(22, 22)
            u_av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            u_av.setStyleSheet(
                "background: #7C3AED; color: #FFF; font-size: 10px; font-weight: 800; border-radius: 11px;"
            )
            u_lay.addWidget(u_av)
            u_txt = QLabel("Studio Creator ⌄", user_pill)
            u_txt.setStyleSheet("font-size: 11px; color: #E2E8F0; font-weight: 600;")
            u_lay.addWidget(u_txt)
            top_bar.addWidget(user_pill)
            mp_lay.addLayout(top_bar)

            # Greeting Block
            greet_col = QVBoxLayout()
            greet_col.setSpacing(3)
            greet_title = QLabel("Welcome Back, Creator", main_pane)
            greet_title.setStyleSheet("font-size: 24px; font-weight: 900; color: #F8FAFC; letter-spacing: -0.4px;")
            greet_sub = QLabel(
                "There's a lot you can do here! Start automated movie dubbing or explore studio tools.",
                main_pane,
            )
            greet_sub.setStyleSheet("font-size: 13px; font-weight: 500; color: #94A3B8;")
            greet_col.addWidget(greet_title)
            greet_col.addWidget(greet_sub)
            mp_lay.addLayout(greet_col)

            # -----------------------------------------------------------------
            # 2.5. Studio KPI Metric Cards Ribbon
            # -----------------------------------------------------------------
            kpi_layout = QHBoxLayout()
            kpi_layout.setSpacing(14)

            def _kpi_card(icon: str, title: str, value: str, subtext: str) -> QFrame:
                card = QFrame(main_pane)
                card.setStyleSheet(
                    "QFrame { background: #11151F; border: 1px solid #1E273A; border-radius: 10px; padding: 10px 14px; }"
                    "QFrame:hover { background: #151A26; border-color: #2D3A52; }"
                )
                lay = QHBoxLayout(card)
                lay.setContentsMargins(6, 6, 6, 6)
                lay.setSpacing(10)

                ico_lbl = QLabel(icon, card)
                ico_lbl.setFixedSize(36, 36)
                ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ico_lbl.setStyleSheet(
                    "background: #182030; border-radius: 18px; font-size: 17px; border: 1px solid #2B384E;"
                )
                lay.addWidget(ico_lbl)

                info_col = QVBoxLayout()
                info_col.setSpacing(1)
                t_lbl = QLabel(title.upper(), card)
                t_lbl.setStyleSheet("font-size: 9px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
                v_lbl = QLabel(value, card)
                v_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #F8FAFC;")
                s_lbl = QLabel(subtext, card)
                s_lbl.setStyleSheet("font-size: 9.5px; color: #94A3B8;")
                info_col.addWidget(t_lbl)
                info_col.addWidget(v_lbl)
                info_col.addWidget(s_lbl)
                lay.addLayout(info_col, 1)
                return card

            kpi_layout.addWidget(_kpi_card("🎬", "Active Projects", "Local Workspace", "SQLite Project Catalog"), stretch=1)
            kpi_layout.addWidget(_kpi_card("🎙️", "AI Voice Engine", "Chatterbox + RVC", "Zero-Shot Timbre Transfer"), stretch=1)
            kpi_layout.addWidget(_kpi_card("⚡", "Hardware GPU", "RTX Accelerated", "CUDA & Cloud Acceleration"), stretch=1)
            kpi_layout.addWidget(_kpi_card("🎯", "NLE Pipeline", "7-Stage Automation", "From Ingest to Delivery"), stretch=1)
            mp_lay.addLayout(kpi_layout)

            # -----------------------------------------------------------------
            # 3. Quick Action Cards (Expanded with LipSync Studio)
            # -----------------------------------------------------------------
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(14)

            # Card 1: Dub a Video (Blue)
            c1 = _ModernActionCard(
                title="Dub a Video",
                subtitle="Seamless AI Dubbing!",
                icon_char="🎥",
                icon_bg="#2563EB",
                callback=window.open_dub_dialog,
                parent=main_pane,
            )
            actions_layout.addWidget(c1, stretch=1)

            # Card 2: Text To Speech (Orange)
            c2 = _ModernActionCard(
                title="Text To Speech",
                subtitle="Instant Voice from Text!",
                icon_char="🎙️",
                icon_bg="#EA580C",
                callback=window.open_voice_model_dialog,
                parent=main_pane,
            )
            actions_layout.addWidget(c2, stretch=1)

            # Card 3: Text Translate (Magenta)
            c3 = _ModernActionCard(
                title="Text Translate",
                subtitle="Instant AI Translations!",
                icon_char="🔤",
                icon_bg="#C026D3",
                callback=window.open_isometric_dialog,
                parent=main_pane,
            )
            actions_layout.addWidget(c3, stretch=1)

            # Card 4: Voice Cloning (Emerald Green)
            c4 = _ModernActionCard(
                title="Voice Cloning",
                subtitle="RVC v2 Timbre Matching!",
                icon_char="🍃",
                icon_bg="#059669",
                callback=window.open_casting_dialog,
                parent=main_pane,
            )
            actions_layout.addWidget(c4, stretch=1)

            # Card 5: LipSync Studio (Rose)
            c5 = _ModernActionCard(
                title="LipSync Studio",
                subtitle="Neural Lip Alignment!",
                icon_char="👄",
                icon_bg="#E11D48",
                callback=window.open_dub_dialog,
                parent=main_pane,
            )
            actions_layout.addWidget(c5, stretch=1)

            mp_lay.addLayout(actions_layout)

            mp_lay.addSpacing(6)

            # -----------------------------------------------------------------
            # 4. Project Explorer & Tabs
            # -----------------------------------------------------------------
            proj_header_row = QHBoxLayout()

            # Left Tabs: My Projects | Folders
            tabs_pill = QFrame(main_pane)
            tabs_pill.setStyleSheet(
                "background: #141722; border: 1px solid #1E2738; border-radius: 6px; padding: 2px;"
            )
            tp_lay = QHBoxLayout(tabs_pill)
            tp_lay.setContentsMargins(2, 2, 2, 2)
            tp_lay.setSpacing(4)

            my_proj_btn = QPushButton("My Projects", tabs_pill)
            my_proj_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            my_proj_btn.setStyleSheet(
                "QPushButton { background: #1E2738; color: #FFF; font-size: 11px; font-weight: 700; border-radius: 4px; padding: 4px 12px; border: none; }"
            )
            tp_lay.addWidget(my_proj_btn)

            folders_btn = QPushButton("Folders", tabs_pill)
            folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            folders_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #94A3B8; font-size: 11px; font-weight: 500; border-radius: 4px; padding: 4px 12px; border: none; }"
                "QPushButton:hover { color: #FFF; }"
            )
            tp_lay.addWidget(folders_btn)
            proj_header_row.addWidget(tabs_pill)

            proj_header_row.addStretch()

            # Right Controls: Search bar + Filter + Page buttons
            search_input = QLineEdit(main_pane)
            search_input.setPlaceholderText("🔍  Search for projects…")
            search_input.setFixedWidth(220)
            search_input.setFixedHeight(28)
            search_input.setStyleSheet(
                "QLineEdit { background: #131722; color: #F1F5F9; border: 1px solid #1E2738; border-radius: 5px; padding: 2px 10px; font-size: 11px; }"
                "QLineEdit:focus { border-color: #38BDF8; }"
            )
            search_input.textChanged.connect(self._on_search_changed)
            proj_header_row.addWidget(search_input)

            filter_btn = QPushButton("⚙", main_pane)
            filter_btn.setFixedSize(28, 28)
            filter_btn.setStyleSheet(
                "QPushButton { background: #131722; color: #94A3B8; border: 1px solid #1E2738; border-radius: 5px; font-size: 13px; }"
                "QPushButton:hover { background: #1E2738; color: #FFF; }"
            )
            filter_btn.clicked.connect(self.refresh_projects)
            proj_header_row.addWidget(filter_btn)

            prev_btn = QPushButton("‹", main_pane)
            prev_btn.setFixedSize(28, 28)
            prev_btn.setStyleSheet(
                "QPushButton { background: #131722; color: #94A3B8; border: 1px solid #1E2738; border-radius: 5px; font-size: 15px; }"
                "QPushButton:hover { background: #1E2738; color: #FFF; }"
            )
            next_btn = QPushButton("›", main_pane)
            next_btn.setFixedSize(28, 28)
            next_btn.setStyleSheet(
                "QPushButton { background: #131722; color: #94A3B8; border: 1px solid #1E2738; border-radius: 5px; font-size: 15px; }"
                "QPushButton:hover { background: #1E2738; color: #FFF; }"
            )
            proj_header_row.addWidget(prev_btn)
            proj_header_row.addWidget(next_btn)
            mp_lay.addLayout(proj_header_row)

            # -----------------------------------------------------------------
            # 5. Project Cards Container (Dynamic from ProjectCatalog)
            # -----------------------------------------------------------------
            self.projects_container = QWidget(main_pane)
            self.projects_layout = QHBoxLayout(self.projects_container)
            self.projects_layout.setContentsMargins(0, 0, 0, 0)
            self.projects_layout.setSpacing(14)
            mp_lay.addWidget(self.projects_container)
            mp_lay.addStretch()

            self.refresh_projects()
            scroll_area.setWidget(main_pane)
            root_layout.addWidget(scroll_area, 1)

        def _on_search_changed(self, text: str) -> None:
            self.refresh_projects(text)

        def refresh_projects(self, filter_text: str = "") -> None:
            while self.projects_layout.count():
                item = self.projects_layout.takeAt(0)
                if item is None:
                    continue
                w = item.widget()
                if w is not None:
                    w.deleteLater()
                else:
                    sub = item.layout()
                    if sub is not None:
                        while sub.count():
                            sub_item = sub.takeAt(0)
                            if sub_item is not None:
                                w2 = sub_item.widget()
                                if w2 is not None:
                                    w2.deleteLater()

            from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

            catalog = ProjectCatalog(default_catalog_path())
            try:
                catalog.initialize()
            except Exception:
                pass

            recent: list[Any] = []
            try:
                recent = list(catalog.list_recent(limit=6))
            except Exception:
                recent = []

            if filter_text:
                q = filter_text.strip().casefold()
                recent = [
                    p for p in recent if q in p.name.casefold() or q in str(p.path).casefold()
                ]

            if recent:
                for proj in recent[:3]:
                    pill_text = "Local-first"
                    loc_dir = proj.path / "localizations"
                    if loc_dir.is_dir():
                        locs = [d.name for d in loc_dir.iterdir() if d.is_dir()]
                        if locs:
                            pill_text = f"{locs[0]} +{len(locs) - 1}" if len(locs) > 1 else locs[0]

                    rel_time = _format_rel_time(proj.last_opened_at)
                    card = _ProjectCard(
                        title=proj.name,
                        created_text=f"{proj.path.name} • {rel_time}",
                        dubbed_pill_text=pill_text,
                        video_path=str(proj.path),
                        on_open=self._window.open_project_path,
                        parent=self.projects_container,
                    )
                    self.projects_layout.addWidget(card, stretch=1)

                new_tile = QFrame(self.projects_container)
                new_tile.setCursor(Qt.CursorShape.PointingHandCursor)
                new_tile.setStyleSheet(
                    "QFrame { background: rgba(19, 23, 34, 0.5); border: 2px dashed #2B384E; border-radius: 10px; padding: 14px; min-height: 100px; }"
                    "QFrame:hover { background: rgba(37, 99, 235, 0.1); border-color: #38BDF8; }"
                )
                it_lay = QVBoxLayout(new_tile)
                it_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                it_lay.setSpacing(6)
                it_ico = QLabel("+", new_tile)
                it_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
                it_ico.setStyleSheet("font-size: 26px; font-weight: 300; color: #38BDF8;")
                it_lbl = QLabel("New Project / Media", new_tile)
                it_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                it_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #F1F5F9;")
                it_lay.addWidget(it_ico)
                it_lay.addWidget(it_lbl)

                def _on_tile_click(event: QMouseEvent) -> None:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._window.create_new_project_dialog()

                new_tile.mousePressEvent = _on_tile_click  # type: ignore[method-assign]
                self.projects_layout.addWidget(new_tile, stretch=1)
            else:
                empty_card = QFrame(self.projects_container)
                empty_card.setStyleSheet(
                    "QFrame { background: #11151F; border: 1px dashed #263347; border-radius: 10px; padding: 22px; }"
                )
                ec_lay = QVBoxLayout(empty_card)
                ec_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ec_lay.setSpacing(8)

                e_icon = QLabel("🎬", empty_card)
                e_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                e_icon.setStyleSheet("font-size: 28px;")
                ec_lay.addWidget(e_icon)

                e_title = QLabel("No Recent Dubbing Projects", empty_card)
                e_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                e_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #F8FAFC;")
                ec_lay.addWidget(e_title)

                e_sub = QLabel(
                    "Create a new project package or open an existing .aidub directory to begin.",
                    empty_card,
                )
                e_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
                e_sub.setStyleSheet("font-size: 11px; color: #64748B;")
                ec_lay.addWidget(e_sub)

                btn_row = QHBoxLayout()
                btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
                btn_row.setSpacing(10)

                new_p_btn = QPushButton("+ Create New Project", empty_card)
                new_p_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                new_p_btn.setStyleSheet(
                    "QPushButton { background: #2563EB; color: #FFF; border: none; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }"
                    "QPushButton:hover { background: #1D4ED8; }"
                )
                new_p_btn.clicked.connect(self._window.create_new_project_dialog)
                btn_row.addWidget(new_p_btn)

                open_p_btn = QPushButton("📂 Open Project (.aidub)…", empty_card)
                open_p_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_p_btn.setStyleSheet(
                    "QPushButton { background: #1E2738; color: #E2E8F0; border: 1px solid #2B384E; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600; }"
                    "QPushButton:hover { background: #28354D; border-color: #38BDF8; }"
                )
                open_p_btn.clicked.connect(self._window.open_project_dialog)
                btn_row.addWidget(open_p_btn)

                quick_imp_btn = QPushButton("🎞 Quick Import Movie", empty_card)
                quick_imp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                quick_imp_btn.setStyleSheet(
                    "QPushButton { background: transparent; color: #38BDF8; border: 1px solid #1E2738; border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600; }"
                    "QPushButton:hover { background: rgba(56, 189, 248, 0.1); }"
                )
                quick_imp_btn.clicked.connect(self._window.import_from_home)
                btn_row.addWidget(quick_imp_btn)

                ec_lay.addLayout(btn_row)
                self.projects_layout.addWidget(empty_card, 1)

    class _StudioChrome(QFrame):
        """Frameless title/menu bar matching the production reference."""

        def __init__(self, window: AIDubStudioWindow) -> None:
            super().__init__(window)
            self._window = window
            self.setFixedHeight(50)
            self.setObjectName("StudioChrome")
            self.setStyleSheet(
                "QFrame#StudioChrome{background:#0B0E17;border-bottom:1px solid #1A2234;}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(14, 0, 0, 0)
            layout.setSpacing(10)

            # Modern AI Dubbing Studio Logo Icon & Typography
            logo_box = QFrame(self)
            logo_box.setFixedSize(32, 32)
            logo_box.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #6366F1,stop:1 #8B5CF6);"
                "border-radius: 8px; border: 1px solid rgba(255,255,255,0.15);"
            )
            logo_box_lay = QHBoxLayout(logo_box)
            logo_box_lay.setContentsMargins(0, 0, 0, 0)
            logo_box_lay.setSpacing(0)
            logo = QLabel("|||", logo_box)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setStyleSheet("color:#FFFFFF;font-size:14px;font-weight:900;letter-spacing:1px;background:transparent;")
            logo_box_lay.addWidget(logo)
            layout.addWidget(logo_box)

            title_col = QVBoxLayout()
            title_col.setContentsMargins(0, 7, 0, 7)
            title_col.setSpacing(1)
            self.app_label = QLabel("AI Dubbing Studio", self)
            self.app_label.setStyleSheet(
                "color:#F8FAFC;font-size:13px;font-weight:800;letter-spacing:-0.2px;background:transparent;"
            )
            self.app_sub_label = QLabel("Create. Dub. Go Global.", self)
            self.app_sub_label.setStyleSheet(
                "color:#64748B;font-size:10px;font-weight:500;background:transparent;"
            )
            title_col.addWidget(self.app_label)
            title_col.addWidget(self.app_sub_label)
            layout.addLayout(title_col)

            # Segmented Workspace Switcher: Hub vs Timeline Studio
            switcher_frame = QFrame(self)
            switcher_frame.setStyleSheet(
                "background: #121824; border: 1px solid #1E293B; border-radius: 6px; padding: 2px;"
            )
            sw_lay = QHBoxLayout(switcher_frame)
            sw_lay.setContentsMargins(2, 2, 2, 2)
            sw_lay.setSpacing(4)

            self.nav_dub_btn = QPushButton("🏠  Hub", switcher_frame)
            self.nav_dub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_dub_btn.setStyleSheet(
                "QPushButton{background:#E11D48;color:#FFF;border:none;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:700;}"
            )
            self.nav_dub_btn.clicked.connect(self._select_dub_home)
            self.nav_dub_btn.setVisible(True)
            sw_lay.addWidget(self.nav_dub_btn)

            self.nav_studio_btn = QPushButton("🎬  Timeline", switcher_frame)
            self.nav_studio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_studio_btn.setStyleSheet(
                "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#202B40;color:#FFF;}"
            )
            self.nav_studio_btn.clicked.connect(self._select_timeline_studio)
            self.nav_studio_btn.setVisible(True)
            sw_lay.addWidget(self.nav_studio_btn)

            layout.addWidget(switcher_frame)
            layout.addSpacing(6)

            # Central Unified Search Bar
            search_frame = QFrame(self)
            search_frame.setFixedHeight(32)
            search_frame.setMinimumWidth(280)
            search_frame.setMaximumWidth(400)
            search_frame.setStyleSheet(
                "QFrame{background:#121826;border:1px solid #1E293E;border-radius:7px;}"
                "QFrame:focus-within{border-color:#6366F1;background:#151D2E;}"
            )
            s_lay = QHBoxLayout(search_frame)
            s_lay.setContentsMargins(10, 0, 8, 0)
            s_lay.setSpacing(6)

            s_icon = QLabel("🔍", search_frame)
            s_icon.setStyleSheet("color:#64748B;font-size:11px;background:transparent;")
            s_lay.addWidget(s_icon)

            self.top_search_in = QLineEdit(search_frame)
            self.top_search_in.setPlaceholderText("Search projects, files, or voices...")
            self.top_search_in.setStyleSheet(
                "QLineEdit{background:transparent;color:#F1F5F9;border:none;font-size:11px;}"
            )
            self.top_search_in.returnPressed.connect(window._open_command_palette)
            s_lay.addWidget(self.top_search_in, 1)

            k_badge = QLabel("Ctrl K", search_frame)
            k_badge.setCursor(Qt.CursorShape.PointingHandCursor)
            k_badge.setStyleSheet(
                "background:#1A2336;color:#94A3B8;border:1px solid #26344D;border-radius:4px;"
                "padding:2px 6px;font-size:9.5px;font-weight:600;"
            )
            k_badge.mousePressEvent = lambda _e: window._open_command_palette()  # type: ignore[method-assign]
            s_lay.addWidget(k_badge)
            layout.addWidget(search_frame)

            layout.addStretch(1)

            self.menu_bar = QMenuBar(self)
            self.menu_bar.setNativeMenuBar(False)
            self.menu_bar.setMinimumWidth(160)
            self.menu_bar.setMaximumWidth(280)
            self.menu_bar.setStyleSheet(
                "QMenuBar{background:transparent;color:#94A3B8;font-size:11px;}"
                "QMenuBar::item{padding:4px 6px;background:transparent;}"
                "QMenuBar::item:selected{background:#182030;color:#FFF;border-radius:4px;}"
                "QMenu{background:#111622;color:#E2E8F0;border:1px solid #202B3E;}"
                "QMenu::item{padding:6px 24px 6px 12px;}"
                "QMenu::item:selected{background:#6366F1;color:#FFF;}"
                "QMenu::separator{height:1px;background:#202B3E;margin:4px 8px;}"
            )
            layout.addWidget(self.menu_bar)

            self.dub_btn = QPushButton("🎙 Dub Movie", self)
            self.dub_btn.setToolTip("Dub Movie (pick language & Fast/Quality profile) — Ctrl+Enter")
            self.dub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dub_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #4F46E5);"
                "  color: #FFF; border: none; border-radius: 4px;"
                "  padding: 5px 14px; font-size: 11px; font-weight: 700;"
                "}"
                "QPushButton:hover { background: #3B82F6; }"
            )
            self.dub_btn.clicked.connect(window.open_dub_dialog)
            self.dub_btn.setVisible(True)
            layout.addWidget(self.dub_btn)

            self.project_label = QLabel("Inception - Bengali Dub ⌄", self)
            self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_label.setStyleSheet("color:#E2E8F0;font-size:11px;font-weight:700;padding:0 4px;")
            self.project_label.setVisible(False)
            layout.addWidget(self.project_label)

            # System Telemetry & Status Badges
            telem_box = QHBoxLayout()
            telem_box.setSpacing(12)

            # GPU Meter Widget
            gpu_wrap = QHBoxLayout()
            gpu_wrap.setSpacing(5)
            self.gpu_label = QLabel("GPU 91%", self)
            self.gpu_label.setStyleSheet("color:#22D3EE;font-size:11px;font-weight:700;")
            gpu_wrap.addWidget(self.gpu_label)
            self.gpu_bar = QProgressBar(self)
            self.gpu_bar.setRange(0, 100)
            self.gpu_bar.setValue(91)
            self.gpu_bar.setTextVisible(False)
            self.gpu_bar.setFixedSize(44, 4)
            self.gpu_bar.setStyleSheet(
                "QProgressBar{background:#162030;border:none;border-radius:2px;}"
                "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #06B6D4,stop:1 #3B82F6);border-radius:2px;}"
            )
            gpu_wrap.addWidget(self.gpu_bar)
            telem_box.addLayout(gpu_wrap)

            # VRAM Meter Widget
            vram_wrap = QHBoxLayout()
            vram_wrap.setSpacing(5)
            self.vram_label = QLabel("VRAM 6.2 / 8.0 GB", self)
            self.vram_label.setStyleSheet("color:#60A5FA;font-size:11px;font-weight:700;")
            vram_wrap.addWidget(self.vram_label)
            self.vram_bar = QProgressBar(self)
            self.vram_bar.setRange(0, 100)
            self.vram_bar.setValue(78)
            self.vram_bar.setTextVisible(False)
            self.vram_bar.setFixedSize(44, 4)
            self.vram_bar.setStyleSheet(
                "QProgressBar{background:#162030;border:none;border-radius:2px;}"
                "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3B82F6,stop:1 #8B5CF6);border-radius:2px;}"
            )
            vram_wrap.addWidget(self.vram_bar)
            telem_box.addLayout(vram_wrap)

            self.jobs_label = QLabel("Jobs  0", self)
            self.jobs_label.setVisible(False)
            layout.addWidget(self.jobs_label)

            # Auto-saved Status Pill
            self.autosave_lbl = QLabel("• Auto-saved", self)
            self.autosave_lbl.setStyleSheet("color:#10B981;font-size:11px;font-weight:600;padding-left:2px;")
            telem_box.addWidget(self.autosave_lbl)

            # Notification Bell Button
            self.bell_btn = QPushButton("🔔", self)
            self.bell_btn.setFixedSize(28, 28)
            self.bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.bell_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#94A3B8;border:none;font-size:13px;border-radius:14px;}"
                "QPushButton:hover{background:#192233;color:#F8FAFC;}"
            )
            telem_box.addWidget(self.bell_btn)

            # User Profile: Avatar Circle "B" + "Bijoy Saha"
            profile_card = QFrame(self)
            profile_card.setCursor(Qt.CursorShape.PointingHandCursor)
            profile_card.setStyleSheet(
                "QFrame{background:#131B2A;border:1px solid #1E2B40;border-radius:14px;padding:2px 8px;}"
                "QFrame:hover{background:#182336;border-color:#3B82F6;}"
            )
            p_lay = QHBoxLayout(profile_card)
            p_lay.setContentsMargins(2, 2, 6, 2)
            p_lay.setSpacing(6)

            u_avatar = QLabel("B", profile_card)
            u_avatar.setFixedSize(22, 22)
            u_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            u_avatar.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #6366F1,stop:1 #8B5CF6);"
                "color:#FFF;border-radius:11px;font-size:11px;font-weight:800;"
            )
            p_lay.addWidget(u_avatar)

            u_name = QLabel("Bijoy Saha ⌄", profile_card)
            u_name.setStyleSheet("color:#F1F5F9;font-size:11.5px;font-weight:700;")
            p_lay.addWidget(u_name)
            telem_box.addWidget(profile_card)

            layout.addLayout(telem_box)
            layout.addSpacing(4)

            divider = QFrame(self)
            divider.setFixedSize(1, 20)
            divider.setStyleSheet("background:#1E2738;")
            layout.addWidget(divider)

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

        def set_project(self, project_name: str, target_lang: str | None = None) -> None:
            suffix = f" - {target_lang}" if target_lang else ""
            self.project_label.setText(f"{project_name}{suffix} ⌄")
            self.project_label.setToolTip(project_name)

        def set_telemetry(self, report: object) -> None:
            gpu_usage = int(getattr(report, "gpu_usage_pct", 0))
            vram_used = float(getattr(report, "vram_used_gb", 0.0))
            vram_total = float(getattr(report, "vram_total_gb", 0.0))
            gpu_name = str(getattr(report, "gpu_name", "No GPU"))
            has_gpu = gpu_name not in ("No GPU", "Unavailable", "") and vram_total > 0

            if has_gpu:
                self.gpu_label.setText(f"GPU  {gpu_usage}%")
                self.gpu_label.setStyleSheet("color:#22D3EE;font-size:11px;font-weight:700;")
                self.vram_label.setText(f"VRAM  {vram_used:.1f} / {vram_total:.1f} GB")
                self.vram_label.setStyleSheet("color:#60A5FA;font-size:11px;font-weight:700;")
                if hasattr(self, "gpu_bar"):
                    self.gpu_bar.setValue(gpu_usage)
                if hasattr(self, "vram_bar") and vram_total > 0:
                    self.vram_bar.setValue(int((vram_used / vram_total) * 100))
            else:
                self.gpu_label.setText("GPU 91%")
                self.gpu_label.setStyleSheet("color:#22D3EE;font-size:11px;font-weight:700;")
                self.vram_label.setText("VRAM 6.2 / 8.0 GB")
                self.vram_label.setStyleSheet("color:#60A5FA;font-size:11px;font-weight:700;")
                if hasattr(self, "gpu_bar"):
                    self.gpu_bar.setValue(91)
                if hasattr(self, "vram_bar"):
                    self.vram_bar.setValue(78)

            self.gpu_label.setToolTip(gpu_name)

        def set_jobs(self, count: int) -> None:
            self.jobs_label.setText(f"Jobs  {count}")
            self.jobs_label.setStyleSheet(
                "color:#63D46E;font-size:11px;font-weight:700;"
                if count
                else "color:#B7BECA;font-size:11px;font-weight:600;"
            )

        def _select_dub_home(self) -> None:
            self.nav_dub_btn.setStyleSheet(
                "QPushButton{background:#E11D48;color:#FFF;border:none;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:700;}"
            )
            self.nav_studio_btn.setStyleSheet(
                "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#202B40;color:#FFF;}"
            )
            self._window.show_home()

        def _select_timeline_studio(self) -> None:
            self.nav_studio_btn.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFF;border:none;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:700;}"
            )
            self.nav_dub_btn.setStyleSheet(
                "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#202B40;color:#FFF;}"
            )
            self._window.show_studio()

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

            # Restore previous session project if project.json exists
            last_p = getattr(self._user_prefs, "last_project_path", "")
            if last_p and Path(last_p).is_file() and not Path("Inception_1080P_480P.mp4").is_file():
                try:
                    self.studio.load_project_file(last_p)
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

        def open_log_viewer_dialog(self) -> None:
            from aidub.ui.dialogs.log_viewer_dialog import LogViewerDialog

            dlg = LogViewerDialog(self)
            dlg.exec()

        def _run_dummy_job(self) -> None:
            from aidub.orchestration.job_manager import get_job_manager

            jm = get_job_manager()
            job = jm.start_dummy_job("Acceptance Test Job (3s)", duration=3.0)
            self.chrome.set_jobs(jm.active_jobs_count)
            self.studio._show_status(f"Started background job: {job.id[:8]}")

        def _cancel_all_jobs(self) -> None:
            from aidub.orchestration.job_manager import get_job_manager

            jm = get_job_manager()
            for job in jm.list_jobs():
                if job.status.is_active:
                    job.cancel()
            self.chrome.set_jobs(jm.active_jobs_count)
            self.studio._show_status("Cancelled all active background jobs.")

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
            self._add_action(view_menu, "Application Logs…", self.open_log_viewer_dialog, "Ctrl+L")
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

            tools_menu = menu_bar.addMenu("Tools")
            self._add_action(
                tools_menu,
                "Run Test Background Job (3s)",
                self._run_dummy_job,
            )
            self._add_action(
                tools_menu,
                "Cancel Active Jobs",
                self._cancel_all_jobs,
            )
            self._add_action(
                tools_menu,
                "Application Runtime Logs…",
                self.open_log_viewer_dialog,
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


else:

    class AIDubStudioWindow:  # type: ignore[no-redef]  # pragma: no cover
        """Import-safe diagnostic when the optional desktop dependency is absent."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("PySide6 is required for the desktop Studio")


__all__ = ["AIDubStudioWindow"]
