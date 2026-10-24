"""Single-window production shell for AI Movie Dubbing Studio."""

from __future__ import annotations

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
        QFont,
        QKeyEvent,
        QKeySequence,
        QLinearGradient,
        QMouseEvent,
        QPainter,
        QPaintEvent,
        QPen,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
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

        def run(self) -> None:
            from aidub.infrastructure.system_telemetry import (
                probe_system_telemetry,
            )

            self.completed.emit(probe_system_telemetry(Path.cwd()))

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
                0.12 + 0.88 * abs(math.sin(i * 0.22) * math.cos(i * 0.08) * math.sin(i * 0.41 + 0.2))
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
        """Quick action card with glowing icon badge matching Image 1."""

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
                f"  background: #141722; border: 1px solid #232C3E; border-radius: 12px; padding: 12px 14px;"
                f"}}"
                f"QFrame:hover {{"
                f"  background: #191E2C; border-color: {icon_bg};"
                f"}}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(12)

            badge = QLabel(icon_char, self)
            badge.setFixedSize(44, 44)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {icon_bg}; color: #FFFFFF; border-radius: 22px; font-size: 20px;"
            )
            layout.addWidget(badge)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t_lbl = QLabel(title, self)
            t_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #F8FAFC;")
            s_lbl = QLabel(subtitle, self)
            s_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #94A3B8;")
            text_col.addWidget(t_lbl)
            text_col.addWidget(s_lbl)
            layout.addLayout(text_col, 1)

            plus_btn = QPushButton("+", self)
            plus_btn.setFixedSize(28, 28)
            plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            plus_btn.setStyleSheet(
                "QPushButton { background: #1E2738; color: #E2E8F0; border-radius: 14px; font-size: 16px; font-weight: 700; border: none; }"
                "QPushButton:hover { background: #2563EB; color: #FFF; }"
            )
            if callback:
                plus_btn.clicked.connect(callback)
            layout.addWidget(plus_btn)

            self._callback = callback

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self._callback:
                self._callback()
            super().mousePressEvent(event)

    class _ProjectCard(QFrame):
        """Card representing a video project matching Image 1."""

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
                "  background: #131722; border: 1px solid #1E2738; border-radius: 10px; padding: 14px;"
                "}"
                "QFrame:hover {"
                "  background: #171C2B; border-color: #38BDF8;"
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
                "background: #1E293B; color: #38BDF8; border-radius: 6px; font-size: 15px;"
            )
            top_row.addWidget(v_badge)

            title_box = QVBoxLayout()
            title_box.setSpacing(2)
            t_lbl = QLabel(title, self)
            t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F8FAFC;")
            c_lbl = QLabel(created_text, self)
            c_lbl.setStyleSheet("font-size: 10px; color: #64748B;")
            title_box.addWidget(t_lbl)
            title_box.addWidget(c_lbl)
            top_row.addLayout(title_box, 1)

            dots_btn = QPushButton("⋮", self)
            dots_btn.setFixedSize(24, 24)
            dots_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #64748B; border: none; font-size: 15px; font-weight: bold; }"
                "QPushButton:hover { color: #FFF; background: #1E293B; border-radius: 4px; }"
            )
            top_row.addWidget(dots_btn)
            layout.addLayout(top_row)

            pill_row = QHBoxLayout()
            pill_lbl = QLabel(f"Dubbed to: {dubbed_pill_text}", self)
            pill_lbl.setStyleSheet(
                "background: #0B111D; color: #94A3B8; border: 1px solid #1E293B; border-radius: 4px;"
                "padding: 4px 8px; font-size: 10px; font-weight: 600;"
            )
            pill_row.addWidget(pill_lbl)
            pill_row.addStretch()
            layout.addLayout(pill_row)

            self._on_open = on_open
            self._video_path = video_path

        def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self._on_open:
                if self._video_path:
                    self._on_open(self._video_path)
                else:
                    self._on_open()
            super().mousePressEvent(event)

    class _HomeDashboardPanel(QFrame):
        """Ultra-Modern AI Studio Hub & Dashboard (Replicating Image 1)."""

        def __init__(self, window: AIDubStudioWindow) -> None:
            super().__init__(window)
            self._window = window
            self.setObjectName("HomeDashboardPanel")
            self.setStyleSheet("QFrame#HomeDashboardPanel{background:#0B0E14;color:#F8FAFC;}")

            root_layout = QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # =================================================================
            # 1. Left Sidebar Navigation (Matching Image 1)
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
            sec1.setStyleSheet("font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;")
            sb_layout.addWidget(sec1)
            sb_layout.addWidget(_nav_btn("🏠  Home", is_active=True))
            sb_layout.addWidget(_nav_btn("🎥  Dubbed Videos", cb=window.show_studio))
            sb_layout.addWidget(_nav_btn("🎙️  Text To Speech", cb=window.open_voice_model_dialog))
            sb_layout.addWidget(_nav_btn("🔤  Text Translate", cb=window.open_isometric_dialog))
            sb_layout.addWidget(_nav_btn("☁️  Kaggle Cloud GPU", cb=window.open_kaggle_dialog))
            sb_layout.addWidget(_nav_btn("📊  Insights  ✦ PRO", cb=window.open_broadcast_export_dialog))

            sb_layout.addSpacing(10)

            # Section: PERSONAL
            sec2 = QLabel("PERSONAL", sidebar)
            sec2.setStyleSheet("font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;")
            sb_layout.addWidget(sec2)
            sb_layout.addWidget(_nav_btn("👥  Voice Library (RVC)", cb=window.open_casting_dialog))
            sb_layout.addWidget(_nav_btn("🎬  Timeline Editor", cb=window.show_studio))

            sb_layout.addSpacing(10)

            # Section: RESOURCES
            sec3 = QLabel("RESOURCES", sidebar)
            sec3.setStyleSheet("font-size: 9px; font-weight: 800; color: #475569; letter-spacing: 1px; padding-left: 6px;")
            sb_layout.addWidget(sec3)
            sb_layout.addWidget(_nav_btn("🔌  Integrations", cb=window.open_preferences_dialog))
            sb_layout.addWidget(_nav_btn("❓  Help Center", cb=window.open_keyboard_shortcuts))

            sb_layout.addStretch()
            root_layout.addWidget(sidebar)

            # =================================================================
            # 2. Main Dashboard Area (Right of Sidebar)
            # =================================================================
            main_pane = QFrame(self)
            main_pane.setStyleSheet("background: #0B0E14;")
            mp_lay = QVBoxLayout(main_pane)
            mp_lay.setContentsMargins(36, 24, 36, 24)
            mp_lay.setSpacing(20)

            # Top Breadcrumb & User Profile Row
            top_bar = QHBoxLayout()
            h_lbl = QLabel("HOME", main_pane)
            h_lbl.setStyleSheet("font-size: 11px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
            top_bar.addWidget(h_lbl)
            top_bar.addStretch()

            user_pill = QFrame(main_pane)
            user_pill.setStyleSheet("background: #141822; border: 1px solid #232C3E; border-radius: 16px; padding: 2px 8px;")
            u_lay = QHBoxLayout(user_pill)
            u_lay.setContentsMargins(4, 2, 6, 2)
            u_lay.setSpacing(6)
            u_av = QLabel("TM", user_pill)
            u_av.setFixedSize(22, 22)
            u_av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            u_av.setStyleSheet("background: #7C3AED; color: #FFF; font-size: 10px; font-weight: 800; border-radius: 11px;")
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
            greet_title.setStyleSheet("font-size: 24px; font-weight: 900; color: #F8FAFC;")
            greet_sub = QLabel("There's a lot you can do here! Start automated movie dubbing or explore studio tools.", main_pane)
            greet_sub.setStyleSheet("font-size: 13px; font-weight: 500; color: #94A3B8;")
            greet_col.addWidget(greet_title)
            greet_col.addWidget(greet_sub)
            mp_lay.addLayout(greet_col)

            # -----------------------------------------------------------------
            # 3. Four Quick Action Cards (Directly Matching Image 1)
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

            mp_lay.addLayout(actions_layout)

            mp_lay.addSpacing(6)

            # -----------------------------------------------------------------
            # 4. Project Explorer & Tabs (Matching Image 1)
            # -----------------------------------------------------------------
            proj_header_row = QHBoxLayout()

            # Left Tabs: My Projects | Folders
            tabs_pill = QFrame(main_pane)
            tabs_pill.setStyleSheet("background: #141722; border: 1px solid #1E2738; border-radius: 6px; padding: 2px;")
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
            proj_header_row.addWidget(search_input)

            filter_btn = QPushButton("⚙", main_pane)
            filter_btn.setFixedSize(28, 28)
            filter_btn.setStyleSheet(
                "QPushButton { background: #131722; color: #94A3B8; border: 1px solid #1E2738; border-radius: 5px; font-size: 13px; }"
                "QPushButton:hover { background: #1E2738; color: #FFF; }"
            )
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
            # 5. Project Cards Grid (Matching Image 1)
            # -----------------------------------------------------------------
            projects_grid = QHBoxLayout()
            projects_grid.setSpacing(14)

            # Project 1: clip_2min.mp4
            p1 = _ProjectCard(
                title="Camb AI video dubbing",
                created_text="clip_2min.mp4 • Created 1 min ago",
                dubbed_pill_text="English (India) +2",
                video_path="clip_2min.mp4",
                on_open=window.load_movie_and_show_editor,
                parent=main_pane,
            )
            projects_grid.addWidget(p1, stretch=1)

            # Project 2: clip.mp4
            p2 = _ProjectCard(
                title="Camb AI video dubbing",
                created_text="clip.mp4 • Created 2 hrs ago",
                dubbed_pill_text="English (India) +2",
                video_path="clip.mp4",
                on_open=window.load_movie_and_show_editor,
                parent=main_pane,
            )
            projects_grid.addWidget(p2, stretch=1)

            # Project 3: Demo / Master
            p3 = _ProjectCard(
                title="Camb AI video dubbing",
                created_text="movie.mp4 • Created 2 hrs ago",
                dubbed_pill_text="English (India) +2",
                video_path="clip_2min.mp4",
                on_open=window.load_movie_and_show_editor,
                parent=main_pane,
            )
            projects_grid.addWidget(p3, stretch=1)

            # Project 4: Import New Movie Tile
            import_tile = QFrame(main_pane)
            import_tile.setCursor(Qt.CursorShape.PointingHandCursor)
            import_tile.setStyleSheet(
                "QFrame { background: rgba(19, 23, 34, 0.4); border: 2px dashed #2B384E; border-radius: 10px; padding: 14px; }"
                "QFrame:hover { background: rgba(37, 99, 235, 0.08); border-color: #38BDF8; }"
            )
            it_lay = QVBoxLayout(import_tile)
            it_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            it_lay.setSpacing(6)
            it_ico = QLabel("+", import_tile)
            it_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            it_ico.setStyleSheet("font-size: 26px; font-weight: 300; color: #38BDF8;")
            it_lbl = QLabel("Import New Movie", import_tile)
            it_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            it_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #F1F5F9;")
            it_lay.addWidget(it_ico)
            it_lay.addWidget(it_lbl)

            def _on_import_click(event: QMouseEvent) -> None:
                if event.button() == Qt.MouseButton.LeftButton:
                    window.open_dub_dialog()

            import_tile.mousePressEvent = _on_import_click  # type: ignore[assignment]
            projects_grid.addWidget(import_tile, stretch=1)

            mp_lay.addLayout(projects_grid)
            mp_lay.addStretch()

            root_layout.addWidget(main_pane, 1)

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
            logo.setStyleSheet("color:#E11D48;font-size:18px;font-weight:900;letter-spacing:-1px;")
            layout.addWidget(logo)
            self.app_label = QLabel("AI DUBBING STUDIO", self)
            self.app_label.setFixedWidth(148)
            self.app_label.setStyleSheet("color:#F8FAFC;font-size:12px;font-weight:800;letter-spacing:0.5px;")
            layout.addWidget(self.app_label)

            # Modern Top Navigation Switcher: Dub vs Timeline
            self.nav_dub_btn = QPushButton("◫  Dub", self)
            self.nav_dub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_dub_btn.setStyleSheet(
                "QPushButton{background:#E11D48;color:#FFF;border:none;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:700;}"
            )
            self.nav_dub_btn.clicked.connect(self._select_dub_home)
            layout.addWidget(self.nav_dub_btn)

            self.nav_studio_btn = QPushButton("🎬  Timeline", self)
            self.nav_studio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_studio_btn.setStyleSheet(
                "QPushButton{background:#162030;color:#94A3B8;border:1px solid #233045;border-radius:4px;"
                "padding:4px 14px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#202B40;color:#FFF;}"
            )
            self.nav_studio_btn.clicked.connect(self._select_timeline_studio)
            layout.addWidget(self.nav_studio_btn)

            layout.addSpacing(8)

            self.menu_bar = QMenuBar(self)
            self.menu_bar.setNativeMenuBar(False)
            self.menu_bar.setMinimumWidth(360)
            self.menu_bar.setMaximumWidth(460)
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

            self.dub_btn = QPushButton("🎙 Dub Movie", self)
            self.dub_btn.setToolTip("Dub Movie (pick language & Fast/Quality profile) — Ctrl+Enter")
            self.dub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dub_btn.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #4F46E5);"
                "  color: #FFF; border: none; border-radius: 4px;"
                "  padding: 4px 14px; font-size: 11px; font-weight: 800;"
                "}"
                "QPushButton:hover { background: #3B82F6; }"
                "QPushButton:disabled { background: #1C2431; color: #64748B; }"
            )
            self.dub_btn.clicked.connect(window.open_dub_dialog)
            layout.addWidget(self.dub_btn)

            layout.addStretch(1)

            self.project_label = QLabel("Inception - Bengali Dub ⌄", self)
            self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_label.setFixedWidth(240)
            self.project_label.setStyleSheet("color:#E2E8F0;font-size:11px;font-weight:700;")
            layout.addWidget(self.project_label)
            layout.addStretch(2)

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
            toolbar.setVisible(False)  # Hidden to eliminate clutter; chrome tabs provide sleek navigation!
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

        def load_movie_and_show_editor(self, video_path: str) -> None:
            self.show_studio()
            if video_path and Path(video_path).is_file():
                self.studio.load_project(video_path)

        def open_voice_model_dialog(self) -> None:
            self.studio._open_voice_model_selector()

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

        def open_keyboard_shortcuts(self) -> None:
            self.show_keyboard_shortcuts()

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
