"""UI widget classes for the Studio window."""

from __future__ import annotations

from ._studio_common import *
from ._studio_common import _QT

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
            dots_btn.clicked.connect(self._show_options_menu)
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
            h_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;"
            )
            top_bar.addWidget(h_lbl)
            top_bar.addStretch()

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
            greet_title.setStyleSheet("font-size: 24px; font-weight: 900; color: #F8FAFC;")
            greet_sub = QLabel(
                "There's a lot you can do here! Start automated movie dubbing or explore studio tools.",
                main_pane,
            )
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
            root_layout.addWidget(main_pane, 1)

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
                    "QFrame { background: rgba(19, 23, 34, 0.4); border: 2px dashed #2B384E; border-radius: 10px; padding: 14px; }"
                    "QFrame:hover { background: rgba(37, 99, 235, 0.08); border-color: #38BDF8; }"
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
            self.app_label.setStyleSheet(
                "color:#F8FAFC;font-size:12px;font-weight:800;letter-spacing:0.5px;"
            )
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
                self.gpu_label.setStyleSheet("color:#63D46E;font-size:11px;font-weight:700;")
                self.vram_label.setText(f"VRAM  {vram_used:.1f} / {vram_total:.1f} GB")
                self.vram_label.setStyleSheet("color:#57A5F8;font-size:11px;font-weight:700;")
            else:
                self.gpu_label.setText("GPU  No GPU")
                self.gpu_label.setStyleSheet("color:#8C94A2;font-size:11px;font-weight:600;")
                self.vram_label.setText("VRAM  No GPU")
                self.vram_label.setStyleSheet("color:#8C94A2;font-size:11px;font-weight:600;")

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


__all__ = [
    "_TelemetryWorker",
    "_WaveformCanvas",
    "_ModernActionCard",
    "_ProjectCard",
    "_HomeDashboardPanel",
    "_StudioChrome",
]
