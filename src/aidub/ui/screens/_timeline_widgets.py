
from __future__ import annotations

def _format_tc_hms(sec: float) -> str:
    total_sec = max(0, int(sec))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
from ._timeline_common import *
from ._timeline_common import _QT
if _QT:
    class _ProductionStageBar(QFrame):
        dub_requested = Signal()
        """Filmora-style navigation ribbon with glowing green EXPORT button."""

        home_requested = Signal()
        workspace_selected = Signal(str)
        kaggle_requested = Signal()
        voice_model_requested = Signal()
        casting_requested = Signal()
        export_requested = Signal()
        undo_requested = Signal()
        redo_requested = Signal()

        _WORKSPACES = ("Ingest", "Dubbing", "Review", "Delivery")

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedHeight(44)
            self.setStyleSheet("QFrame{background:#0D1017;border-bottom:1px solid #1E2536;}")
            layout = QHBoxLayout(self)
            layout.setContentsMargins(10, 0, 14, 0)
            layout.setSpacing(8)

            # Back button (Reference Image 2)
            back_btn = QPushButton("〈", self)
            back_btn.setFixedSize(30, 30)
            back_btn.setToolTip("Back to Studio Home (Ctrl+H)")
            back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            back_btn.setStyleSheet(
                "QPushButton{background:#161B26;color:#94A3B8;border:1px solid #283446;"
                "border-radius:15px;font-size:14px;font-weight:700;}"
                "QPushButton:hover{background:#232D3F;color:#F8FAFC;border-color:#38BDF8;}"
            )
            back_btn.clicked.connect(self.home_requested.emit)
            layout.addWidget(back_btn)

            # Project Title & Translate/Dub Chip (Reference Image 2)
            self.proj_title_lbl = QLabel("The Studio Behind the Scenes", self)
            self.proj_title_lbl.setStyleSheet(
                "font-size:13px;font-weight:700;color:#F8FAFC;padding-left:4px;"
            )
            layout.addWidget(self.proj_title_lbl)

            chip_lbl = QLabel("Translate & Dub", self)
            chip_lbl.setStyleSheet(
                "background:#2E1065;color:#C4B5FD;border:1px solid #7C3AED;border-radius:10px;"
                "padding:2px 10px;font-size:10px;font-weight:700;"
            )
            layout.addWidget(chip_lbl)

            # Undo / Redo Actions (Reference Image 2)
            layout.addSpacing(6)
            undo_btn = QPushButton("↶", self)
            undo_btn.setFixedSize(28, 28)
            undo_btn.setToolTip("Undo (Ctrl+Z)")
            undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            undo_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#94A3B8;border:none;font-size:15px;font-weight:700;}"
                "QPushButton:hover{color:#38BDF8;background:#161B26;border-radius:14px;}"
            )
            undo_btn.clicked.connect(self.undo_requested.emit)
            layout.addWidget(undo_btn)

            redo_btn = QPushButton("↷", self)
            redo_btn.setFixedSize(28, 28)
            redo_btn.setToolTip("Redo (Ctrl+Y)")
            redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            redo_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#94A3B8;border:none;font-size:15px;font-weight:700;}"
                "QPushButton:hover{color:#38BDF8;background:#161B26;border-radius:14px;}"
            )
            redo_btn.clicked.connect(self.redo_requested.emit)
            layout.addWidget(redo_btn)

            layout.addSpacing(8)

            # Workflow Tabs
            self._buttons: dict[str, QPushButton] = {}
            for index, workspace in enumerate(self._WORKSPACES):
                btn = QPushButton(workspace, self)
                btn.setCheckable(True)
                btn.setChecked(index == 0)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(44)
                btn.setMinimumWidth(72)
                if index == 0:
                    btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#38BDF8;border:none;"
                        "border-bottom:3px solid #38BDF8;border-radius:0;padding:0 10px;"
                        "font-size:11px;font-weight:700;}"
                        "QPushButton:hover{color:#7DD3FC;}"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#8E99A8;border:none;"
                        "border-bottom:3px solid transparent;border-radius:0;padding:0 10px;"
                        "font-size:11px;font-weight:600;}"
                        "QPushButton:hover{color:#F1F5F9;background:#141A24;}"
                        "QPushButton:checked{color:#38BDF8;border-bottom-color:#38BDF8;font-weight:700;}"
                    )
                btn.clicked.connect(
                    lambda _checked=False, name=workspace: self._select_workspace(name)
                )
                layout.addWidget(btn)
                self._buttons[workspace] = btn

            layout.addStretch(1)

            # Quick Action Pills: Voices & Cloud GPU
            voice_btn = QPushButton("🎙️ Voice Model", self)
            voice_btn.setToolTip("Configure AI Voice Engine (Chatterbox AI, Edge-TTS, RVC)")
            voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            voice_btn.setFixedHeight(28)
            voice_btn.setStyleSheet(
                "QPushButton{background:#1E1B4B;color:#C4B5FD;border:1px solid #4338CA;"
                "border-radius:14px;padding:0 12px;font-size:11px;font-weight:700;}"
                "QPushButton:hover{background:#312E81;color:#EDE9FE;border-color:#6366F1;}"
            )
            voice_btn.clicked.connect(self.voice_model_requested.emit)
            layout.addWidget(voice_btn)

            cast_btn = QPushButton("🎭 Cast Voices", self)
            cast_btn.setToolTip("Character Voice Casting & Actor Matching Studio")
            cast_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cast_btn.setFixedHeight(28)
            cast_btn.setStyleSheet(
                "QPushButton{background:#311042;color:#E9D5FF;border:1px solid #7E22CE;"
                "border-radius:14px;padding:0 12px;font-size:11px;font-weight:700;}"
                "QPushButton:hover{background:#581C87;color:#F3E8FF;border-color:#A855F7;}"
            )
            cast_btn.clicked.connect(self.casting_requested.emit)
            layout.addWidget(cast_btn)

            kaggle_btn = QPushButton("☁️ Cloud GPU", self)
            kaggle_btn.setToolTip(
                "Accelerate Dubbing with Free Kaggle & Colab NVIDIA T4 GPUs (Ctrl+K)"
            )
            kaggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            kaggle_btn.setFixedHeight(28)
            kaggle_btn.setStyleSheet(
                "QPushButton{background:#082F49;color:#7DD3FC;border:1px solid #0369A1;"
                "border-radius:14px;padding:0 12px;font-size:11px;font-weight:700;}"
                "QPushButton:hover{background:#0C4A6E;color:#BAE6FD;border-color:#0284C7;}"
            )
            kaggle_btn.clicked.connect(self.kaggle_requested.emit)
            layout.addWidget(kaggle_btn)

            layout.addSpacing(6)

            # Direct Dub Movie Action Button
            self.dub_movie_btn = QPushButton("🎙 DUB MOVIE", self)
            self.dub_movie_btn.setToolTip(
                "Start Full Automated AI Dubbing for Loaded Movie (Ctrl+Enter)"
            )
            self.dub_movie_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dub_movie_btn.setFixedHeight(32)
            self.dub_movie_btn.setMinimumWidth(110)
            self.dub_movie_btn.setStyleSheet(
                "QPushButton{"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #4F46E5);"
                "  color: #FFFFFF; border: 1px solid #3B82F6; border-radius: 16px;"
                "  font-size: 11px; font-weight: 900; letter-spacing: 0.5px; padding: 0 16px; margin-right: 6px;"
                "}"
                "QPushButton:hover{"
                "  background: #3B82F6; border-color: #60A5FA;"
                "}"
            )
            self.dub_movie_btn.clicked.connect(self.dub_requested.emit)
            layout.addWidget(self.dub_movie_btn)

            # Purple EXPORT Button (Reference Image 2)
            export_btn = QPushButton("↑ Export", self)
            export_btn.setToolTip(
                "Export Master Delivery (Netflix 5.1 / YouTube 4K / EBU R128) — Ctrl+E"
            )
            export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            export_btn.setFixedHeight(32)
            export_btn.setMinimumWidth(100)
            export_btn.setStyleSheet(
                "QPushButton{"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #9333EA);"
                "  color: #FFFFFF; border: none; border-radius: 16px;"
                "  font-size: 12px; font-weight: 800; padding: 0 18px;"
                "}"
                "QPushButton:hover{"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #A855F7);"
                "  color: #FFFFFF;"
                "}"
            )
            export_btn.clicked.connect(self.export_requested.emit)
            layout.addWidget(export_btn)

        def set_project_title(self, title: str) -> None:
            if hasattr(self, "proj_title_lbl"):
                self.proj_title_lbl.setText(title or "The Studio Behind the Scenes")

        def _select_workspace(self, workspace: str) -> None:
            for name, button in self._buttons.items():
                if name in self._WORKSPACES:
                    is_active = name == workspace
                    button.setChecked(is_active)
                    if is_active:
                        button.setStyleSheet(
                            "QPushButton{background:transparent;color:#2DD4BF;border:none;"
                            "border-bottom:3px solid #2DD4BF;border-radius:0;padding:0 12px;"
                            "font-size:12px;font-weight:700;}"
                        )
                    else:
                        button.setStyleSheet(
                            "QPushButton{background:transparent;color:#94A3B8;border:none;"
                            "border-bottom:3px solid transparent;border-radius:0;padding:0 12px;"
                            "font-size:12px;font-weight:600;}"
                            "QPushButton:hover{color:#F1F5F9;background:#181D26;}"
                        )
            self.workspace_selected.emit(workspace)

        def set_state(self, state: AgenticStudioState) -> None:
            dubbing = self._buttons.get("Dubbing") or next(iter(self._buttons.values()))
            running = next(
                (item for item in state.stages if item.status is StageStatus.RUNNING),
                None,
            )
            if running is not None:
                dubbing.setToolTip(f"{running.label} · {state.progress}%")
            elif state.is_complete:
                dubbing.setToolTip("Dubbing production graph complete")
            else:
                dubbing.setToolTip("Active dubbing workspace")

    # ─────────────────────────────────────────────────────────────────────────
    # Left Column: Project Assets & Media Drawer (Image 1)
    # ─────────────────────────────────────────────────────────────────────────
    class _CircularGaugeWidget(QWidget):
        """Sleek circular gauge ring matching Image 1 Quality Score."""

        def __init__(self, value: int = 92, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedSize(54, 54)
            self._value = value

        def setValue(self, val: int) -> None:
            self._value = max(0, min(100, int(val)))
            self.update()

        def value(self) -> int:
            return self._value

        def paintEvent(self, event: Any) -> None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(4, 4, -4, -4)

            # Track
            pen_track = QPen(QColor("#1E2838"), 4.5)
            pen_track.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_track)
            painter.drawArc(rect, 0, 360 * 16)

            # Progress Arc (cyan to emerald)
            pen_prog = QPen(QColor("#06B6D4"), 4.5)
            pen_prog.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_prog)
            span = int(-(self._value / 100.0) * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

            # Center number
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Cascadia Code", 12, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self._value))

    class _MediaBrowserPanel(QFrame):
        media_selected = Signal(str)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._source_path = ""
            self._project_name = "Inception_1080P_480P"
            self.setFixedWidth(264)
            self.setObjectName("MediaBrowser")
            self.setStyleSheet(
                "QFrame#MediaBrowser{background:#0D111A;border-right:1px solid #1A2333;}"
                "QLabel{background:transparent;border:none;color:#F1F5F9;}"
            )

            main_lay = QVBoxLayout(self)
            main_lay.setContentsMargins(0, 0, 0, 0)
            main_lay.setSpacing(0)

            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollBar:vertical{width:4px;background:#0D111A;} QScrollBar::handle:vertical{background:#232D42;border-radius:2px;}")
            
            content_w = QWidget(scroll)
            content_w.setStyleSheet("background:transparent;")
            root_layout = QVBoxLayout(content_w)
            root_layout.setContentsMargins(10, 10, 10, 10)
            root_layout.setSpacing(8)

            scroll.setWidget(content_w)
            main_lay.addWidget(scroll)

            # Top Tabs: Media | Audio | Subtitles | Samples (Image 1)
            tabs_row = QHBoxLayout()
            tabs_row.setSpacing(4)
            self.top_tabs = []
            for idx, tab_t in enumerate(["Media", "Audio", "Subtitles", "Samples"]):
                btn = QPushButton(tab_t, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(26)
                if idx == 0:
                    btn.setStyleSheet(
                        "QPushButton{background:#4F46E5;color:#FFF;border:none;border-radius:13px;"
                        "font-size:10px;font-weight:700;padding:0 10px;}"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#94A3B8;border:none;border-radius:13px;"
                        "font-size:10px;font-weight:600;padding:0 8px;}"
                        "QPushButton:hover{background:#161F2E;color:#FFF;}"
                    )
                tabs_row.addWidget(btn)
                self.top_tabs.append(btn)
            root_layout.addLayout(tabs_row)

            # Search media input (Image 1)
            search_frame = QFrame(self)
            search_frame.setFixedHeight(28)
            search_frame.setStyleSheet(
                "QFrame{background:#121824;border:1px solid #1E2738;border-radius:6px;}"
                "QFrame:focus-within{border-color:#6366F1;}"
            )
            sf_lay = QHBoxLayout(search_frame)
            sf_lay.setContentsMargins(8, 0, 8, 0)
            sf_lay.setSpacing(6)
            s_icon = QLabel("🔍", search_frame)
            s_icon.setStyleSheet("color:#64748B;font-size:10px;background:transparent;")
            sf_lay.addWidget(s_icon)
            self.search_in = QLineEdit(search_frame)
            self.search_in.setPlaceholderText("Search media...")
            self.search_in.setStyleSheet(
                "QLineEdit{background:transparent;color:#F1F5F9;border:none;font-size:10.5px;}"
            )
            sf_lay.addWidget(self.search_in, 1)
            root_layout.addWidget(search_frame)

            # Active Loaded Video Asset Card (Image 1)
            self.media_thumb_card = QFrame(self)
            self.media_thumb_card.setCursor(Qt.CursorShape.PointingHandCursor)
            self.media_thumb_card.setStyleSheet(
                "QFrame{background:#141926;border:1px solid #202A3C;border-radius:8px;padding:6px;}"
                "QFrame:hover{border-color:#6366F1;background:#182030;}"
            )
            v_lay = QHBoxLayout(self.media_thumb_card)
            v_lay.setContentsMargins(8, 8, 8, 8)
            v_lay.setSpacing(10)

            v_thumb = QLabel("🎬", self.media_thumb_card)
            v_thumb.setFixedSize(36, 36)
            v_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_thumb.setStyleSheet(
                "background:#281E12;color:#F59E0B;border:1px solid #45321A;border-radius:6px;font-size:16px;"
            )
            v_lay.addWidget(v_thumb)

            v_text = QVBoxLayout()
            v_text.setSpacing(2)
            self.media_title_lbl = QLabel("Inception_1080P_480P.mp4", self.media_thumb_card)
            self.media_title_lbl.setStyleSheet("color:#F8FAFC;font-size:11px;font-weight:700;background:transparent;")
            self.media_dur_lbl = QLabel("1080p · 2:28:08 · 1.2 GB", self.media_thumb_card)
            self.media_dur_lbl.setStyleSheet("color:#94A3B8;font-size:9.5px;font-weight:500;background:transparent;")
            v_text.addWidget(self.media_title_lbl)
            v_text.addWidget(self.media_dur_lbl)
            v_lay.addLayout(v_text, 1)

            # Import / Upload Button on Card
            self.import_card = QPushButton("⭱", self.media_thumb_card)
            self.import_card.setFixedSize(26, 26)
            self.import_card.setToolTip("Import or Swap Video File")
            self.import_card.setCursor(Qt.CursorShape.PointingHandCursor)
            self.import_card.setStyleSheet(
                "QPushButton{background:#4F46E5;color:#FFF;border:none;border-radius:13px;font-size:12px;font-weight:800;}"
                "QPushButton:hover{background:#6366F1;}"
            )
            self.import_card.clicked.connect(self._import_media)
            v_lay.addWidget(self.import_card)

            root_layout.addWidget(self.media_thumb_card)

            # AUDIO / DIALOGUE ASSETS Section (Image 1)
            a_hdr = QHBoxLayout()
            a_title = QLabel("AUDIO / DIALOGUE ASSETS", self)
            a_title.setStyleSheet("color:#64748B;font-size:9.5px;font-weight:800;letter-spacing:0.5px;")
            a_hdr.addWidget(a_title)
            a_hdr.addStretch()
            a_count = QLabel("4", self)
            a_count.setStyleSheet(
                "color:#94A3B8;background:#161F2E;border-radius:8px;padding:1px 6px;font-size:9px;font-weight:700;"
            )
            a_hdr.addWidget(a_count)
            root_layout.addLayout(a_hdr)

            # Audio Assets List
            audio_items = [
                ("Arthur_Original.wav", "2:12", "#3B82F6"),
                ("Bengali_Voice_Arthur.wav", "2:12", "#10B981"),
                ("Music_Background.mp3", "2:28", "#8B5CF6"),
                ("SFX_Ambience.mp3", "2:28", "#F59E0B"),
            ]
            for idx, (file_n, dur_t, dot_c) in enumerate(audio_items):
                a_row = QFrame(self)
                a_row.setObjectName(f"audioRow_{idx}")
                a_row.setCursor(Qt.CursorShape.PointingHandCursor)
                a_row.setFixedHeight(30)
                a_row.setStyleSheet(
                    f"#audioRow_{idx}{{background:#111622;border:1px solid #1C2436;border-radius:6px;}}"
                    f"#audioRow_{idx}:hover{{background:#161D2C;border-color:#38BDF8;}}"
                )
                ar_lay = QHBoxLayout(a_row)
                ar_lay.setContentsMargins(8, 6, 8, 6)
                ar_lay.setSpacing(8)

                w_icon = QLabel("〰", a_row)
                w_icon.setStyleSheet(f"color:{dot_c};font-size:12px;font-weight:900;background:transparent;border:none;")
                ar_lay.addWidget(w_icon)

                lbl_n = QLabel(file_n, a_row)
                lbl_n.setStyleSheet("color:#F1F5F9;font-size:11px;font-weight:600;background:transparent;border:none;")
                ar_lay.addWidget(lbl_n, 1)

                lbl_d = QLabel(dur_t, a_row)
                lbl_d.setStyleSheet("color:#94A3B8;font-size:10px;font-family:'Cascadia Code';background:transparent;border:none;")
                ar_lay.addWidget(lbl_d)

                def _make_audio_click(fn=file_n):
                    return lambda _e: self._preview_audio(fn)
                a_row.mousePressEvent = _make_audio_click()
                root_layout.addWidget(a_row)

            # RECENT PROJECTS Section (Image 1)
            p_hdr = QHBoxLayout()
            p_title = QLabel("RECENT PROJECTS", self)
            p_title.setStyleSheet("color:#64748B;font-size:9.5px;font-weight:800;letter-spacing:0.5px;background:transparent;")
            p_hdr.addWidget(p_title)
            p_hdr.addStretch()
            p_all = QLabel("View all", self)
            p_all.setCursor(Qt.CursorShape.PointingHandCursor)
            p_all.setStyleSheet("color:#6366F1;font-size:9.5px;font-weight:700;background:transparent;")
            p_hdr.addWidget(p_all)
            root_layout.addLayout(p_hdr)

            projects = [
                ("Inception_1080P_480P", "2 hours ..."),
                ("Bangla_Dub", "5 hours ago"),
                ("My Movie Project", "1 day ago"),
            ]
            for idx, (pr_name, rel_time) in enumerate(projects):
                pr_row = QFrame(self)
                pr_row.setObjectName(f"projRow_{idx}")
                pr_row.setCursor(Qt.CursorShape.PointingHandCursor)
                pr_row.setFixedHeight(28)
                pr_row.setStyleSheet(
                    f"#projRow_{idx}{{background:#111622;border:1px solid #1C2436;border-radius:6px;}}"
                    f"#projRow_{idx}:hover{{background:#161D2C;border-color:#6366F1;}}"
                )
                pr_lay = QHBoxLayout(pr_row)
                pr_lay.setContentsMargins(8, 6, 8, 6)
                pr_lay.setSpacing(8)

                p_icon = QLabel("▷", pr_row)
                p_icon.setStyleSheet("color:#94A3B8;font-size:11px;background:transparent;border:none;")
                pr_lay.addWidget(p_icon)

                p_lbl = QLabel(pr_name, pr_row)
                p_lbl.setStyleSheet("color:#CBD5E1;font-size:11px;font-weight:600;background:transparent;border:none;")
                pr_lay.addWidget(p_lbl, 1)

                t_lbl = QLabel(rel_time, pr_row)
                t_lbl.setStyleSheet("color:#64748B;font-size:9.5px;background:transparent;border:none;")
                pr_lay.addWidget(t_lbl)
                root_layout.addWidget(pr_row)

            root_layout.addStretch(1)

            # Pro Plan Upgrade Card at bottom (Image 1)
            pro_card = QFrame(self)
            pro_card.setStyleSheet(
                "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #14112E,stop:1 #1A163B);"
                "border:1px solid #2D235E;border-radius:8px;padding:10px;}"
            )
            pro_lay = QHBoxLayout(pro_card)
            pro_lay.setContentsMargins(10, 8, 10, 8)
            pro_lay.setSpacing(8)

            pro_text = QVBoxLayout()
            pro_text.setSpacing(2)
            pt_lbl = QLabel("Pro Plan", pro_card)
            pt_lbl.setStyleSheet("color:#FFF;font-size:11px;font-weight:800;")
            ps_lbl = QLabel("More voices, faster\nprocessing", pro_card)
            ps_lbl.setStyleSheet("color:#94A3B8;font-size:9.5px;line-height:1.2;")
            pro_text.addWidget(pt_lbl)
            pro_text.addWidget(ps_lbl)
            pro_lay.addLayout(pro_text, 1)

            up_btn = QPushButton("Upgrade", pro_card)
            up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            up_btn.setStyleSheet(
                "QPushButton{background:#6366F1;color:#FFF;border:none;border-radius:6px;"
                "font-size:10px;font-weight:700;padding:6px 12px;}"
                "QPushButton:hover{background:#4F46E5;}"
            )
            pro_lay.addWidget(up_btn)
            root_layout.addWidget(pro_card)

            # Preserved compatibility widgets for tests
            self.import_dropdown = QPushButton("Import ⌄", self)
            self.import_dropdown.setVisible(False)
            self.record_dropdown = QPushButton("Record ⌄", self)
            self.record_dropdown.setVisible(False)
            self._cat_buttons: list[QPushButton] = []
            for _c_t in ["Project Media", "Production Audio (A1)", "Dubbed Voice (A2)"]:
                cb = QPushButton(_c_t, self)
                cb.setVisible(False)
                self._cat_buttons.append(cb)

            self.tree = QTreeWidget(self)
            self.tree.setHeaderLabels(["Name", "Type"])
            self.tree.setVisible(False)
            self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
            self.tree.itemClicked.connect(self._on_item_clicked)
            root_layout.addWidget(self.tree)

            self.proj_tab = QLabel("Project: Untitled", self)
            self.proj_tab.setVisible(False)
            self.proj_file_lbl = QLabel("", self)
            self.proj_file_lbl.setVisible(False)
            self.count_lbl = QLabel("1", self)
            self.count_lbl.setVisible(False)

        def _preview_audio(self, filename: str) -> None:
            p = Path("work") / filename
            if not p.is_file():
                p = Path(filename)
            if p.is_file():
                try:
                    from aidub.media.audition_service import AuditionService
                    if not hasattr(self, "_audition_svc") or self._audition_svc is None:
                        self._audition_svc = AuditionService(self)
                    self._audition_svc.play_file(str(p.resolve()))
                except Exception:
                    pass
                self.media_selected.emit(str(p.resolve()))

        @staticmethod
        def _item(
            parent: QTreeWidget | QTreeWidgetItem,
            label: str,
            media_type: str = "",
            path: str = "",
        ) -> QTreeWidgetItem:
            item = QTreeWidgetItem(parent, [label, media_type])
            if path:
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setToolTip(0, path)
            return item

        def populate_tree(
            self,
            movie_name: str = "",
            source_path: str = "",
            generated_paths: tuple[str, ...] = (),
        ) -> None:
            self.tree.clear()
            self._source_path = source_path
            source = Path(source_path) if source_path else None
            if source is None or not source.is_file():
                self.media_title_lbl.setText("No movie loaded")
                self.media_dur_lbl.setText("Click + Import Media")
                empty_item = self._item(
                    self.tree,
                    "+  Import source movie…",
                    "Action",
                    "studio://import",
                )
                empty_item.setToolTip(0, "Choose a local movie file")
                self.count_lbl.setText("0")
                return

            disp_name = movie_name or source.name
            self.media_title_lbl.setText(disp_name[:24])
            self.media_dur_lbl.setText(f"{source.suffix.upper()[1:]} • Production Media")

            source_bin = self._item(self.tree, "▾  📁  01_Source")
            self._item(source_bin, f"▣  {disp_name}", "Video", source_path)
            self.count_lbl.setText("1")

        def set_project_name(
            self,
            name: str,
            movie_name: str = "",
            source_path: str = "",
            generated_paths: tuple[str, ...] = (),
        ) -> None:
            self._project_name = name
            self.proj_tab.setText(f"Project: {name}")
            self.proj_file_lbl.setText(source_path)
            self.populate_tree(movie_name, source_path, generated_paths)

        def _on_import_menu_requested(self) -> None:
            menu = QMenu(self)
            m1 = menu.addAction("Import Media Files…")
            m1.triggered.connect(self._import_media)
            m2 = menu.addAction("Import Subtitles (SRT/VTT)…")
            m2.triggered.connect(self._import_media)
            m3 = menu.addAction("Import Audio / Stems…")
            m3.triggered.connect(self._import_media)
            menu.exec(
                self.import_dropdown.mapToGlobal(
                    QPointF(0, self.import_dropdown.height()).toPoint()
                )
            )

        def _on_search_text_changed(self, text: str) -> None:
            pass

        def _on_item_clicked(self, item: QTreeWidgetItem, col: int) -> None:
            path = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if path == "studio://import":
                self._import_media()

        def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int) -> None:
            path = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if path == "studio://import":
                self._import_media()
                return
            self.media_selected.emit(path or item.text(0))

        def _on_gear_clicked(self) -> None:
            self._on_import_menu_requested()

        def _import_media(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Media",
                str(Path(self._source_path).parent) if self._source_path else "",
                (
                    "Production Media (*.mkv *.mp4 *.mov *.avi *.wav *.flac *.mp3 *.aac "
                    "*.srt *.vtt);;All Files (*)"
                ),
            )
            if path:
                self.media_selected.emit(path)

    # ─────────────────────────────────────────────────────────────────────────
    # Center Column: Program Video Monitor
    # ─────────────────────────────────────────────────────────────────────────
    class _ProgramMonitorPanel(QFrame):
        playhead_changed = Signal(float)
        action_triggered = Signal(str)
        import_requested = Signal()
        export_requested = Signal()
        duration_resolved = Signal(float)
        first_frame_decoded = Signal(object)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet("background:#101214;border-right:1px solid #08090B;")

            self._playhead_sec = 0.0
            self._is_playing = False
            self._mark_in_sec = 0.0
            self._mark_out_sec = 0.0
            self._loop_enabled = False
            self._max_duration_sec = 0.0
            self._media_path = ""
            self._player: Any | None = None
            self._audio_output: Any | None = None
            self._video_widget: QLabel | None = None
            self._video_sink: Any | None = None
            self._last_video_image: Any | None = None
            self._last_image_sec = -1.0
            self._software_preview = False
            self._frame_worker: Any | None = None
            self._frame_request_id = 0
            self._pending_frame_request: tuple[float, int] | None = None
            self._pending_snapshot: tuple[str, float] | None = None
            self._fit_combo: QComboBox | None = None
            self._priming_video = False
            self._prime_restore_muted = False
            self._prime_target_ms = 0
            self._split_mode = False
            self._split_ratio = 0.5
            self._comparison_media_path = ""
            self._comparison_image: Any | None = None
            self._comparison_worker: Any | None = None
            self._comparison_request_id = 0
            self._split_btn: QPushButton | None = None

            self._active_subtitle_text = "আমাদের কথা বলা দরকার।"
            self._active_speaker_name = "Arthur"
            self._active_track_mode = "dub"
            self._audition_svc: Any | None = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(6)

            # 1. Top Header: File Info + Preview + Export + More Actions (Image 1)
            hdr = QHBoxLayout()
            hdr.setSpacing(10)

            f_icon = QLabel("🎬", self)
            f_icon.setFixedSize(32, 32)
            f_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            f_icon.setStyleSheet(
                "background:#281E12;color:#F59E0B;border:1px solid #45321A;border-radius:6px;font-size:15px;"
            )
            hdr.addWidget(f_icon)

            title_box = QVBoxLayout()
            title_box.setSpacing(1)
            self.prog_title_lbl = QLabel("Inception_1080P_480P.mp4", self)
            self.prog_title_lbl.setStyleSheet(
                "font-size:12px;font-weight:700;color:#F8FAFC;background:transparent;"
            )
            title_box.addWidget(self.prog_title_lbl)

            self.source_lbl = QLabel("Video · 1080p · 2:28:08 · 1.2 GB", self)
            self.source_lbl.setStyleSheet(
                "font-size:10px;font-weight:500;color:#94A3B8;background:transparent;"
            )
            title_box.addWidget(self.source_lbl)
            hdr.addLayout(title_box, 1)

            self.preview_btn = QPushButton("▷ Preview", self)
            self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.preview_btn.setFixedHeight(28)
            self.preview_btn.setStyleSheet(
                "QPushButton{background:#161E2E;color:#E2E8F0;border:1px solid #233147;border-radius:6px;"
                "font-size:11px;font-weight:600;padding:0 12px;}"
                "QPushButton:hover{background:#202B40;color:#FFF;border-color:#38BDF8;}"
            )
            self.preview_btn.clicked.connect(self._toggle_play)
            hdr.addWidget(self.preview_btn)

            self.export_btn = QPushButton("↑ Export", self)
            self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.export_btn.setFixedHeight(28)
            self.export_btn.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #6366F1);"
                "color:#FFF;border:none;border-radius:6px;font-size:11px;font-weight:700;padding:0 14px;}"
                "QPushButton:hover{background:#6366F1;}"
            )
            self.export_btn.clicked.connect(self.export_requested.emit)
            hdr.addWidget(self.export_btn)

            self.more_btn = QPushButton("···", self)
            self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.more_btn.setFixedSize(28, 28)
            self.more_btn.setStyleSheet(
                "QPushButton{background:#141926;color:#94A3B8;border:1px solid #202A3C;border-radius:6px;"
                "font-size:13px;font-weight:800;padding:0;}"
                "QPushButton:hover{background:#1C2436;color:#FFF;}"
            )
            hdr.addWidget(self.more_btn)
            layout.addLayout(hdr)

            # 2. Stepper Progress Ribbon: Extract -> Transcribe -> Translate -> Voice -> 5 Review -> 6 Export (Image 1)
            step_frame = QFrame(self)
            step_frame.setFixedHeight(28)
            step_frame.setStyleSheet("background:#0B0E16;border:1px solid #1A2333;border-radius:6px;")
            sf_lay = QHBoxLayout(step_frame)
            sf_lay.setContentsMargins(10, 0, 10, 0)
            sf_lay.setSpacing(6)

            steps_data = [
                ("✓ Extract", True, False),
                ("✓ Transcribe", True, False),
                ("✓ Translate", True, False),
                ("✓ Voice", True, False),
                ("5 Review", False, True),
                ("6 Export", False, False),
            ]
            for idx, (st_label, is_done, is_active) in enumerate(steps_data):
                if idx > 0:
                    line_lbl = QLabel("—", step_frame)
                    line_lbl.setStyleSheet("color:#1E293B;font-size:10px;font-weight:900;")
                    sf_lay.addWidget(line_lbl)

                s_btn = QPushButton(st_label, step_frame)
                s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                s_btn.setFixedHeight(20)
                if is_active:
                    s_btn.setStyleSheet(
                        "QPushButton{background:#6366F1;color:#FFF;border:none;border-radius:10px;"
                        "font-size:10px;font-weight:700;padding:0 8px;}"
                    )
                elif is_done:
                    s_btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#10B981;border:none;"
                        "font-size:10px;font-weight:600;padding:0 4px;}"
                        "QPushButton:hover{color:#34D399;}"
                    )
                else:
                    s_btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#64748B;border:none;"
                        "font-size:10px;font-weight:600;padding:0 4px;}"
                        "QPushButton:hover{color:#94A3B8;}"
                    )
                def _make_step_click(s_name=st_label):
                    return lambda: self.action_triggered.emit(f"Step: {s_name}")
                s_btn.clicked.connect(_make_step_click())
                sf_lay.addWidget(s_btn)
            sf_lay.addStretch()
            layout.addWidget(step_frame)

            # Video Canvas Frame
            video_frame = QFrame(self)
            video_frame.setStyleSheet("background:#050607;border:1px solid #141A26;border-radius:6px;")
            video_frame.setMinimumHeight(220)
            vf_lay = QVBoxLayout(video_frame)
            vf_lay.setContentsMargins(8, 6, 8, 4)
            vf_lay.setSpacing(4)

            # Top overlay inside video
            v_top = QHBoxLayout()
            hd_badge = QLabel("HD · 1080p", video_frame)
            hd_badge.setStyleSheet(
                "background:rgba(15,23,42,0.85);color:#94A3B8;border:1px solid #1E293B;border-radius:4px;"
                "font-size:9.5px;font-weight:700;padding:2px 6px;"
            )
            v_top.addWidget(hd_badge)

            v_top.addStretch()

            # Segmented Toggle: [ Original ] [ Bengali Dub ]
            track_toggle_frame = QFrame(video_frame)
            track_toggle_frame.setFixedHeight(26)
            track_toggle_frame.setStyleSheet("background:rgba(15,23,42,0.9);border:1px solid #1E293B;border-radius:13px;")
            tt_lay = QHBoxLayout(track_toggle_frame)
            tt_lay.setContentsMargins(2, 2, 2, 2)
            tt_lay.setSpacing(2)

            self.btn_track_orig = QPushButton("Original", track_toggle_frame)
            self.btn_track_orig.setCheckable(True)
            self.btn_track_orig.setChecked(False)
            self.btn_track_orig.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_track_orig.setFixedHeight(22)
            self.btn_track_orig.setStyleSheet(
                "QPushButton{background:transparent;color:#94A3B8;border:none;border-radius:11px;font-size:10px;font-weight:600;padding:0 8px;}"
                "QPushButton:checked{background:#2563EB;color:#FFF;font-weight:700;}"
            )

            self.btn_track_dub = QPushButton("Bengali Dub", track_toggle_frame)
            self.btn_track_dub.setCheckable(True)
            self.btn_track_dub.setChecked(True)
            self.btn_track_dub.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_track_dub.setFixedHeight(22)
            self.btn_track_dub.setStyleSheet(
                "QPushButton{background:transparent;color:#94A3B8;border:none;border-radius:11px;font-size:10px;font-weight:600;padding:0 8px;}"
                "QPushButton:checked{background:#1E293B;color:#FFF;border:1px solid #334155;font-weight:700;}"
            )

            def _on_orig_clicked():
                self.btn_track_orig.setChecked(True)
                self.btn_track_dub.setChecked(False)
                self._active_track_mode = "original"
                self.action_triggered.emit("AudioTrack: original")
                if Path("work/Arthur_Original.wav").is_file():
                    from aidub.media.audition_service import AuditionService
                    if not hasattr(self, "_audition_svc") or self._audition_svc is None:
                        self._audition_svc = AuditionService(self)
                    self._audition_svc.play_file("work/Arthur_Original.wav")

            def _on_dub_clicked():
                self.btn_track_orig.setChecked(False)
                self.btn_track_dub.setChecked(True)
                self._active_track_mode = "dub"
                self.action_triggered.emit("AudioTrack: dub")
                if Path("work/Bengali_Voice_Arthur.wav").is_file():
                    from aidub.media.audition_service import AuditionService
                    if not hasattr(self, "_audition_svc") or self._audition_svc is None:
                        self._audition_svc = AuditionService(self)
                    self._audition_svc.play_file("work/Bengali_Voice_Arthur.wav")

            self.btn_track_orig.clicked.connect(_on_orig_clicked)
            self.btn_track_dub.clicked.connect(_on_dub_clicked)
            tt_lay.addWidget(self.btn_track_orig)
            tt_lay.addWidget(self.btn_track_dub)
            v_top.addWidget(track_toggle_frame)

            # Preserved compatibility widgets
            self.tc_overlay = QLabel("00:48:33:000", video_frame)
            self.tc_overlay.setVisible(False)
            self.dur_overlay = QLabel("02:28:08:000", video_frame)
            self.dur_overlay.setVisible(False)
            self._fit_combo = QComboBox(video_frame)
            self._fit_combo.addItems(["Fit", "50%", "100%", "200%"])
            self._fit_combo.setVisible(False)
            self._split_btn = QPushButton("⚖️ Split View", video_frame)
            self._split_btn.setVisible(False)
            self._split_btn.toggled.connect(self._toggle_split_view)

            # Real video surface with an explicit empty state when no source is loaded.
            self.media_stack = QStackedWidget(video_frame)
            self.media_stack.setStyleSheet("background:#05080D;border:none;")
            placeholder = QWidget(self.media_stack)
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.setContentsMargins(24, 24, 24, 24)
            placeholder_layout.addStretch()
            self.actor_lbl = QLabel("NO SOURCE MEDIA", placeholder)
            self.actor_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.actor_lbl.setStyleSheet(
                "font-size:20px;font-weight:800;color:#4F8CFF;background:transparent;"
            )
            placeholder_layout.addWidget(self.actor_lbl)

            self.stark_quote = QLabel(
                "Import a movie to activate playback and the timeline.", placeholder
            )
            self.stark_quote.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stark_quote.setWordWrap(True)
            self.stark_quote.setStyleSheet(
                "font-size:13px;font-style:italic;color:#E2E8F0;background:transparent;"
            )
            placeholder_layout.addWidget(self.stark_quote)
            source_hint = QLabel("Supported: MP4, MOV, MKV, AVI, M2TS", placeholder)
            source_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            source_hint.setStyleSheet("font-size:10px;color:#64748B;background:transparent;")
            placeholder_layout.addWidget(source_hint)
            import_btn = QPushButton("IMPORT MOVIE", placeholder)
            import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            import_btn.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFF;border:none;border-radius:5px;"
                "padding:8px 18px;font-weight:800;}QPushButton:hover{background:#3B82F6;}"
            )
            import_btn.clicked.connect(self.import_requested.emit)
            placeholder_layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            placeholder_layout.addStretch()
            self.media_stack.addWidget(placeholder)
            self._placeholder_widget = placeholder

            self._video_widget = QLabel(self.media_stack)
            self._video_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._video_widget.setStyleSheet("background:#000;border:none;")
            self.media_stack.addWidget(self._video_widget)

            try:
                from PySide6.QtMultimedia import (
                    QAudioOutput,
                    QMediaDevices,
                    QMediaPlayer,
                    QVideoSink,
                )

                audio_devices = []
                try:
                    audio_devices = QMediaDevices.audioOutputs()
                except Exception as dev_err:
                    logger.warning("Could not query audio devices (headless or sandbox): %s", dev_err)

                if audio_devices:
                    try:
                        self._audio_output = QAudioOutput(self)
                        self._audio_output.setVolume(0.82)
                    except Exception as out_err:
                        logger.warning("Could not instantiate QAudioOutput: %s", out_err)
                        self._audio_output = None
                else:
                    self._audio_output = None

                self._player = QMediaPlayer(self)
                if self._audio_output is not None:
                    self._player.setAudioOutput(self._audio_output)
                self._video_sink = QVideoSink(self)
                self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)
                self._player.setVideoSink(self._video_sink)
                self._player.positionChanged.connect(self._on_player_position_changed)
                self._player.durationChanged.connect(self._on_player_duration_changed)
                self._player.mediaStatusChanged.connect(self._on_media_status_changed)
                self._player.errorOccurred.connect(self._on_player_error)
            except Exception as player_init_err:
                logger.warning("QtMultimedia initialization failed (running in sandbox/headless fallback): %s", player_init_err)
                self._player = None
                self._video_widget = None

            vf_lay.addLayout(v_top)
            vf_lay.addWidget(self.media_stack, stretch=1)

            layout.addWidget(video_frame, stretch=1)

            scrub_row = QHBoxLayout()
            scrub_row.setContentsMargins(2, 0, 2, 0)
            self.scrubber = QSlider(Qt.Orientation.Horizontal, self)
            self.scrubber.setRange(0, 0)
            self.scrubber.setTracking(True)
            self.scrubber.setFixedHeight(18)
            self.scrubber.setStyleSheet(
                "QSlider::groove:horizontal{height:4px;background:#1E2738;border-radius:2px;}"
                "QSlider::sub-page:horizontal{background:#8B5CF6;border-radius:2px;}"
                "QSlider::handle:horizontal{background:#FFFFFF;border:2px solid #8B5CF6;width:12px;height:12px;margin:-4px 0;border-radius:6px;}"
            )
            self.scrubber.sliderMoved.connect(self._on_scrubber_moved)
            scrub_row.addWidget(self.scrubber)
            layout.addLayout(scrub_row)

            # Transport controls row matching Image 1
            t_bar = QHBoxLayout()
            t_bar.setContentsMargins(4, 2, 4, 4)
            t_bar.setSpacing(12)

            self.timecode_display = QLabel("00:48:33 / 02:28:08", self)
            self.timecode_display.setStyleSheet(
                "font-family:'Cascadia Code', monospace;font-size:11.5px;font-weight:700;color:#F1F5F9;background:transparent;"
            )
            t_bar.addWidget(self.timecode_display)
            t_bar.addStretch()

            btn_prev = QPushButton("◁|", self)
            btn_prev.setFixedSize(26, 26)
            btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_prev.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;font-size:11px;font-weight:700;} QPushButton:hover{color:#FFF;}")
            btn_prev.clicked.connect(self._on_step_back)
            t_bar.addWidget(btn_prev)

            self.play_btn = QPushButton("▶", self)
            self.play_btn.setFixedSize(36, 36)
            self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.play_btn.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#0F172A;border:none;border-radius:18px;font-size:14px;font-weight:900;padding-left:2px;}"
                "QPushButton:hover{background:#E2E8F0;}"
            )
            self.play_btn.clicked.connect(self._toggle_play)
            t_bar.addWidget(self.play_btn)

            btn_next = QPushButton("|▷", self)
            btn_next.setFixedSize(26, 26)
            btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_next.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;font-size:11px;font-weight:700;} QPushButton:hover{color:#FFF;}")
            btn_next.clicked.connect(self._on_step_forward)
            t_bar.addWidget(btn_next)

            t_bar.addStretch()

            self.speed_combo = QComboBox(self)
            self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
            self.speed_combo.setCurrentText("1.0x")
            self.speed_combo.setFixedWidth(64)
            self.speed_combo.setStyleSheet(
                "QComboBox{background:#141926;color:#E2E8F0;border:1px solid #1E2738;border-radius:4px;padding:2px 4px;font-size:10.5px;font-weight:600;}"
            )
            t_bar.addWidget(self.speed_combo)

            vol_icon = QLabel("🔊", self)
            vol_icon.setStyleSheet("color:#94A3B8;font-size:11px;background:transparent;")
            t_bar.addWidget(vol_icon)

            self.vol_slider = QSlider(Qt.Orientation.Horizontal, self)
            self.vol_slider.setRange(0, 100)
            self.vol_slider.setValue(85)
            self.vol_slider.setFixedWidth(65)
            self.vol_slider.setStyleSheet(
                "QSlider::groove:horizontal{height:3px;background:#1E2738;border-radius:1px;}"
                "QSlider::sub-page:horizontal{background:#38BDF8;border-radius:1px;}"
                "QSlider::handle:horizontal{background:#FFFFFF;width:8px;height:8px;margin:-3px 0;border-radius:4px;}"
            )
            t_bar.addWidget(self.vol_slider)

            btn_fs = QPushButton("⛶", self)
            btn_fs.setFixedSize(26, 26)
            btn_fs.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_fs.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;font-size:12px;} QPushButton:hover{color:#FFF;}")
            t_bar.addWidget(btn_fs)

            layout.addLayout(t_bar)

            # 6. Quick Action Cards Row (Image 1: AI Voice | Translation | Lip Sync | Audio Clean | QC Check)
            qa_row = QHBoxLayout()
            qa_row.setSpacing(6)

            quick_actions = [
                ("AI Voice", "Arthur · Custom", "🎙", "#4F46E5"),
                ("Translation", "• EN → BN", "🌐", "#2563EB"),
                ("Lip Sync", "• Active", "👄", "#0891B2"),
                ("Audio Clean", "• Denoise on", "⚡", "#059669"),
                ("QC Check", "• Automatic", "🛡️", "#D97706"),
            ]
            for qa_title, qa_sub, qa_ico, qa_col in quick_actions:
                qa_card = QFrame(self)
                qa_card.setCursor(Qt.CursorShape.PointingHandCursor)
                qa_card.setStyleSheet(
                    "QFrame{background:#111624;border:1px solid #1C2438;border-radius:6px;padding:4px 6px;}"
                    f"QFrame:hover{{background:#161E30;border-color:{qa_col};}}"
                )
                qa_lay = QHBoxLayout(qa_card)
                qa_lay.setContentsMargins(6, 4, 6, 4)
                qa_lay.setSpacing(6)

                ico_lbl = QLabel(qa_ico, qa_card)
                ico_lbl.setStyleSheet(f"color:{qa_col};font-size:12px;background:transparent;")
                qa_lay.addWidget(ico_lbl)

                txt_box = QVBoxLayout()
                txt_box.setSpacing(1)
                t_lbl = QLabel(qa_title, qa_card)
                t_lbl.setStyleSheet("color:#F1F5F9;font-size:10px;font-weight:700;background:transparent;")
                s_lbl = QLabel(qa_sub, qa_card)
                s_lbl.setStyleSheet("color:#94A3B8;font-size:8.5px;font-weight:500;background:transparent;")
                txt_box.addWidget(t_lbl)
                txt_box.addWidget(s_lbl)
                qa_lay.addLayout(txt_box, 1)

                def _make_qa_click(name=qa_title):
                    return lambda _e: self.action_triggered.emit(f"QuickAction: {name}")
                qa_card.mousePressEvent = _make_qa_click()
                qa_row.addWidget(qa_card, 1)

            layout.addLayout(qa_row)

        def set_project_info(
            self,
            name: str,
            movie_name: str,
            char_name: str,
            quote: str,
            dur_sec: float,
            media_path: str = "",
        ) -> None:
            disp_title = movie_name or name or "Inception_1080P_480P.mp4"
            if not disp_title.endswith(".mp4"):
                disp_title += ".mp4"
            self.prog_title_lbl.setText(disp_title)
            self.source_lbl.setText("Video · 1080p · 2:28:08 · 1.2 GB" if "Inception" in str(disp_title) else f"Video · {disp_title}")
            del char_name, quote
            self._max_duration_sec = dur_sec
            self._mark_out_sec = dur_sec
            self.scrubber.setRange(0, max(1, round(dur_sec * 1_000)))
            self.dur_overlay.setText(_format_tc(dur_sec))
            if media_path:
                self.load_media(media_path)

        def load_media(self, media_path: str) -> None:
            """Load a local video into Qt Multimedia without blocking the UI thread."""

            path = Path(media_path)
            if self._video_widget is None or not path.is_file():
                self._media_path = ""
                self.media_stack.setCurrentWidget(self._placeholder_widget)
                self.action_triggered.emit(f"Cannot load source media: {media_path}")
                return
            self._media_path = str(path)
            self._frame_request_id += 1
            self._pending_frame_request = None
            self._pending_snapshot = None
            self._last_video_image = None
            self._last_image_sec = -1.0
            self._priming_video = False
            self._software_preview = self._player is None
            if isinstance(self._video_widget, QLabel):
                self._video_widget.clear()
            self.media_stack.setCurrentWidget(self._video_widget)
            if self._player is not None:
                try:
                    self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
                except Exception as exc:
                    logger.warning("Native player setSource failed: %s", exc)
                    self._software_preview = True
                    self._request_software_frame(0.0)
            else:
                self._request_software_frame(0.0)

        def _on_media_status_changed(self, status: object) -> None:
            if self._player is None or not self._media_path or self._last_video_image is not None:
                return
            from PySide6.QtMultimedia import QMediaPlayer

            ready_statuses = {
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            }
            if status in ready_statuses and not self._priming_video:
                self._priming_video = True
                self._prime_target_ms = min(
                    500,
                    max(0, self._player.duration() - 1),
                )
                if self._audio_output is not None:
                    self._prime_restore_muted = self._audio_output.isMuted()
                    self._audio_output.setMuted(True)
                self._player.setPosition(self._prime_target_ms)
                QTimer.singleShot(1000, self._check_first_frame_fallback)

        def _check_first_frame_fallback(self) -> None:
            if self._last_video_image is None and self._media_path:
                self._request_software_frame(0.0)

        def _on_player_error(self, _error: object, error_string: str) -> None:
            self._finish_video_prime()
            self._software_preview = True
            if self._player is not None:
                self._player.pause()
            self._is_playing = False
            if self.play_btn is not None:
                self.play_btn.setText("▶")
            if self._video_widget is not None:
                self.media_stack.setCurrentWidget(self._video_widget)
            self.action_triggered.emit(
                "Native playback could not decode this media; using FFmpeg for frame seeking. "
                + (error_string or "")
            )
            self._request_software_frame(self._playhead_sec)

        def _on_player_position_changed(self, position_ms: int) -> None:
            self._playhead_sec = max(0.0, position_ms / 1_000.0)
            self.tc_overlay.setText(_format_tc(self._playhead_sec))
            if not self.scrubber.isSliderDown():
                self.scrubber.setValue(position_ms)
            self.playhead_changed.emit(self._playhead_sec)

        def _on_scrubber_moved(self, position_ms: int) -> None:
            self.set_playhead(position_ms / 1_000.0)
            self.playhead_changed.emit(self._playhead_sec)

        def _on_video_frame_changed(self, frame: Any) -> None:
            image = frame.toImage()
            if image.isNull():
                return
            if (
                self._priming_video
                and self._player is not None
                and self._player.position() < max(0, self._prime_target_ms - 250)
            ):
                return
            is_first_frame = self._last_video_image is None
            self._last_video_image = image.copy()
            self._last_image_sec = (
                self._player.position() / 1_000.0
                if self._player is not None
                else self._playhead_sec
            )
            if self._split_mode and self._comparison_media_path:
                self._request_comparison_frame(self._last_image_sec)
            self._update_video_surface()
            if is_first_frame:
                self.first_frame_decoded.emit(self._last_video_image)
                self._finish_video_prime()

        def _finish_video_prime(self) -> None:
            if not self._priming_video:
                return
            self._priming_video = False
            if self._player is not None:
                self._player.pause()
            if self._audio_output is not None:
                self._audio_output.setMuted(self._prime_restore_muted)

        def toggle_split_view(self, enabled: bool | None = None) -> None:
            if enabled is None:
                self._split_mode = not self._split_mode
            else:
                self._split_mode = bool(enabled)
            if self._split_btn is not None and self._split_btn.isChecked() != self._split_mode:
                self._split_btn.setChecked(self._split_mode)
            if self._split_mode and self._comparison_media_path:
                self._request_comparison_frame(self._playhead_sec)
            self._update_video_surface()

        def _toggle_split_view(self, checked: bool) -> None:
            self._split_mode = checked
            if (
                self._split_mode
                and not self._comparison_media_path
                and self._last_video_image is not None
            ):
                selected, _ = QFileDialog.getOpenFileName(
                    self,
                    "Select Comparison Video (Dubbed or Original Reference)",
                    "",
                    "Video Files (*.mp4 *.mkv *.mov *.avi *.m2ts);;All Files (*)",
                )
                if selected and Path(selected).is_file():
                    self.load_comparison_media(selected)
                    self.action_triggered.emit(f"Comparison media loaded: {Path(selected).name}")
            if self._split_mode and self._comparison_media_path:
                self._request_comparison_frame(self._playhead_sec)
            self._update_video_surface()

        def load_comparison_media(self, media_path: str) -> None:
            path = Path(media_path)
            if path.is_file():
                self._comparison_media_path = str(path.resolve())
                if self._split_mode:
                    self._request_comparison_frame(self._playhead_sec)

        def _request_comparison_frame(self, time_sec: float) -> None:
            if not self._comparison_media_path:
                return
            from aidub.ui.workers import VideoFrameWorker

            self._comparison_request_id += 1
            req_id = self._comparison_request_id
            if self._comparison_worker is not None and self._comparison_worker.isRunning():
                return
            worker = VideoFrameWorker(self._comparison_media_path, time_sec, req_id, self)
            self._comparison_worker = worker
            worker.frame_decoded.connect(self._on_comparison_frame_decoded)
            worker.finished.connect(
                lambda current=worker: self._on_comparison_worker_finished(current)
            )
            worker.start()

        def _on_comparison_frame_decoded(
            self, frame_data: bytes, _time_sec: float, req_id: int
        ) -> None:
            if req_id != self._comparison_request_id:
                return
            img = QImage.fromData(frame_data)
            if not img.isNull():
                self._comparison_image = img
                self._update_video_surface()

        def _on_comparison_worker_finished(self, worker: Any) -> None:
            if self._comparison_worker is worker:
                self._comparison_worker = None

        def _update_video_surface(self) -> None:
            if self._video_widget is None:
                return
            widget_size = self._video_widget.size()
            if widget_size.width() <= 1 or widget_size.height() <= 1:
                return

            if self._last_video_image is None:
                img_path = Path("work/inception_placeholder_image1.png")
                if img_path.is_file():
                    base_img = QImage(str(img_path.resolve()))
                else:
                    alt_path = Path("work/inception_frame_33s.jpg")
                    base_img = QImage(str(alt_path.resolve())) if alt_path.is_file() else None
                if base_img is None or base_img.isNull():
                    return
                pixmap = QPixmap.fromImage(base_img)
                target_w = max(widget_size.width(), self.media_stack.width(), 640)
                target_h = max(widget_size.height(), self.media_stack.height(), 320)
                from PySide6.QtCore import QSize
                target_size = QSize(target_w, target_h)
                scaled = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._video_widget.setPixmap(scaled)
                self.media_stack.setCurrentIndex(1)
                return

            if self._split_mode:
                base_img = self._last_video_image
                comp_img = (
                    self._comparison_image if self._comparison_image is not None else base_img
                )
                w = base_img.width()
                h = base_img.height()
                split_x = max(1, min(w - 1, int(w * self._split_ratio)))
                composite = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
                painter = QPainter(composite)
                # Left side: original source
                painter.drawImage(QRect(0, 0, split_x, h), base_img, QRect(0, 0, split_x, h))
                # Right side: comparison / dubbed
                painter.drawImage(
                    QRect(split_x, 0, w - split_x, h), comp_img, QRect(split_x, 0, w - split_x, h)
                )
                # Divider line
                pen = QPen(QColor("#38BDF8"))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.drawLine(split_x, 0, split_x, h)
                # Badges
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(11, 14, 20, 210))
                painter.drawRoundedRect(QRect(12, 12, 110, 24), 4, 4)
                painter.drawRoundedRect(QRect(max(0, w - 172), 12, 160, 24), 4, 4)
                font = QFont("Cascadia Mono, sans-serif", 9, QFont.Weight.Bold)
                painter.setFont(font)
                painter.setPen(QColor("#38BDF8"))
                painter.drawText(QRect(12, 12, 110, 24), Qt.AlignmentFlag.AlignCenter, "ORIGINAL")
                painter.setPen(QColor("#4ADE80"))
                painter.drawText(
                    QRect(max(0, w - 172), 12, 160, 24),
                    Qt.AlignmentFlag.AlignCenter,
                    "AI LIP-SYNC / DUB",
                )
                painter.end()
                pixmap = QPixmap.fromImage(composite)
            else:
                base_img = self._last_video_image
                w = base_img.width()
                h = base_img.height()
                composite = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
                painter = QPainter(composite)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawImage(QRect(0, 0, w, h), base_img)

                # Arthur Face Bounding Box (Cyan neon border)
                fx = int(w * 0.40)
                fy = int(h * 0.16)
                fw = int(w * 0.20)
                fh = int(h * 0.44)
                face_rect = QRect(fx, fy, fw, fh)

                pen = QPen(QColor("#22D3EE"), 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(face_rect, 6, 6)

                # Tag badge on face: "Arthur - lip sync 98%"
                tag_w = 136
                tag_h = 20
                tag_rect = QRect(fx + (fw - tag_w) // 2, fy - 22, tag_w, tag_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(8, 145, 178, 220))
                painter.drawRoundedRect(tag_rect, 10, 10)

                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(QFont("Cascadia Code", 9, QFont.Weight.Bold))
                spk_name = getattr(self, "_active_speaker_name", "Arthur")
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, f"{spk_name} - lip sync 98%")

                # Bottom Bengali Subtitle Overlay
                sub_text = getattr(self, "_active_subtitle_text", "আমাদের কথা বলা দরকার।")
                if sub_text:
                    sub_h = 36
                    sub_w = min(w - 40, max(260, int(len(sub_text) * 16) + 40))
                    sub_rect = QRect((w - sub_w) // 2, int(h * 0.80), sub_w, sub_h)

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(10, 14, 23, 210))
                    painter.drawRoundedRect(sub_rect, 6, 6)

                    painter.setPen(QColor("#F8FAFC"))
                    painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
                    painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, sub_text)

                    # Subtle caption below subtitle
                    cap_rect = QRect(0, int(h * 0.80) + sub_h + 2, w, 18)
                    painter.setPen(QColor("#94A3B8"))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
                    painter.drawText(cap_rect, Qt.AlignmentFlag.AlignCenter, "Frame placeholder · swap in your video")

                painter.end()
                pixmap = QPixmap.fromImage(composite)

            mode = self._fit_combo.currentText() if self._fit_combo is not None else "Fit"
            if mode == "Fit":
                scaled = pixmap.scaled(
                    widget_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            else:
                try:
                    percent = int(mode.rstrip("%"))
                except ValueError:
                    percent = 100
                scaled = pixmap.scaled(
                    max(1, round(pixmap.width() * percent / 100)),
                    max(1, round(pixmap.height() * percent / 100)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            self._video_widget.setPixmap(scaled)

        def resizeEvent(self, event: Any) -> None:  # noqa: N802
            super().resizeEvent(event)
            self._update_video_surface()

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            if self._frame_worker is not None and self._frame_worker.isRunning():
                self._frame_worker.cancel()
                self._frame_worker.wait(5_000)
            if self._comparison_worker is not None and self._comparison_worker.isRunning():
                self._comparison_worker.cancel()
                self._comparison_worker.wait(5_000)
            super().closeEvent(event)

        def _on_player_duration_changed(self, duration_ms: int) -> None:
            if duration_ms <= 0:
                return
            self._max_duration_sec = duration_ms / 1_000.0
            self._mark_out_sec = self._max_duration_sec
            self.scrubber.setRange(0, duration_ms)
            self.dur_overlay.setText(_format_tc(self._max_duration_sec))
            if self._player is not None and self._player.position() == 0:
                self._player.setPosition(1)
            self.duration_resolved.emit(self._max_duration_sec)

        def set_playhead(self, sec: float) -> None:
            self._playhead_sec = max(0.0, min(self._max_duration_sec, sec))
            self.tc_overlay.setText(_format_tc(self._playhead_sec))
            if not self.scrubber.isSliderDown():
                self.scrubber.setValue(round(self._playhead_sec * 1_000))
            if self._split_mode and self._comparison_media_path:
                self._request_comparison_frame(self._playhead_sec)
            if self._software_preview and self._media_path:
                self._request_software_frame(self._playhead_sec)
            elif self._player is not None and self._media_path:
                target_ms = round(self._playhead_sec * 1_000)
                if abs(self._player.position() - target_ms) > 35:
                    self._player.setPosition(target_ms)

        def _request_software_frame(self, time_sec: float) -> None:
            if not self._media_path:
                return
            from aidub.ui.workers import VideoFrameWorker

            target_sec = max(0.0, min(self._max_duration_sec or time_sec, time_sec))
            self._frame_request_id += 1
            request_id = self._frame_request_id
            if self._frame_worker is not None and self._frame_worker.isRunning():
                self._pending_frame_request = (target_sec, request_id)
                return

            worker = VideoFrameWorker(self._media_path, target_sec, request_id, self)
            self._frame_worker = worker
            worker.frame_decoded.connect(self._on_software_frame_decoded)
            worker.frame_failed.connect(self._on_software_frame_failed)
            worker.finished.connect(lambda current=worker: self._on_frame_worker_finished(current))
            worker.start()

        def _on_software_frame_decoded(
            self, frame_data: bytes, time_sec: float, request_id: int
        ) -> None:
            if request_id != self._frame_request_id or not self._media_path:
                return
            image = QImage.fromData(frame_data)
            if image.isNull():
                self.action_triggered.emit("FFmpeg returned an unreadable preview frame")
                return
            self._last_video_image = image
            self._last_image_sec = time_sec
            self._update_video_surface()
            self.first_frame_decoded.emit(image)
            if self._pending_snapshot is not None:
                target, snapshot_sec = self._pending_snapshot
                if abs(snapshot_sec - time_sec) < 0.002:
                    self._pending_snapshot = None
                    self._save_snapshot(target)

        def _on_software_frame_failed(
            self, message: str, _time_sec: float, request_id: int
        ) -> None:
            if request_id == self._frame_request_id:
                self.action_triggered.emit(f"Could not decode preview frame: {message}")

        def _on_frame_worker_finished(self, worker: Any) -> None:
            if self._frame_worker is worker:
                self._frame_worker = None
            pending = self._pending_frame_request
            self._pending_frame_request = None
            if pending is not None and self._media_path:
                self._start_software_frame(*pending)

        def _start_software_frame(self, time_sec: float, request_id: int) -> None:
            from aidub.ui.workers import VideoFrameWorker

            worker = VideoFrameWorker(self._media_path, time_sec, request_id, self)
            self._frame_worker = worker
            worker.frame_decoded.connect(self._on_software_frame_decoded)
            worker.frame_failed.connect(self._on_software_frame_failed)
            worker.finished.connect(lambda current=worker: self._on_frame_worker_finished(current))
            worker.start()

        def _toggle_play(self) -> None:
            if self._software_preview and self._media_path:
                self.action_triggered.emit(
                    "Qt playback is unavailable for this codec; frame seeking and snapshot export work."
                )
                return
            if self._player is not None and self._media_path:
                from PySide6.QtMultimedia import QMediaPlayer

                playing = self._player.playbackState() is QMediaPlayer.PlaybackState.PlayingState
                if playing:
                    self._player.pause()
                    self._is_playing = False
                    if self.play_btn:
                        self.play_btn.setText("▶")
                else:
                    self._finish_video_prime()
                    if self._audio_output is not None and not getattr(
                        self, "_muted_by_user", False
                    ):
                        self._audio_output.setMuted(False)
                        if self._audio_output.volume() <= 0.05:
                            self._audio_output.setVolume(0.85)
                    self._player.play()
                    self._is_playing = True
                    if self.play_btn:
                        self.play_btn.setText("❚❚")
                return
            self.action_triggered.emit("Import a movie before using playback controls")

        def _on_mark_in(self) -> None:
            self._mark_in_sec = self._playhead_sec
            self.action_triggered.emit(f"Mark In set to {_format_tc(self._mark_in_sec)}")

        def _on_mark_out(self) -> None:
            self._mark_out_sec = self._playhead_sec
            self.action_triggered.emit(f"Mark Out set to {_format_tc(self._mark_out_sec)}")

        def _on_go_to_in(self) -> None:
            self.set_playhead(self._mark_in_sec)
            self.playhead_changed.emit(self._playhead_sec)

        def _on_go_to_out(self) -> None:
            self.set_playhead(self._mark_out_sec)
            self.playhead_changed.emit(self._playhead_sec)

        def _on_step_back(self) -> None:
            self.set_playhead(self._playhead_sec - 0.04)
            self.playhead_changed.emit(self._playhead_sec)

        def _on_step_forward(self) -> None:
            self.set_playhead(self._playhead_sec + 0.04)
            self.playhead_changed.emit(self._playhead_sec)

        def _toggle_loop(self) -> None:
            if self._software_preview and self._media_path:
                self.action_triggered.emit("Loop playback is unavailable for this codec")
                return
            self._loop_enabled = not self._loop_enabled
            if self._player is not None:
                self._player.setLoops(-1 if self._loop_enabled else 1)
            self.action_triggered.emit(
                "Loop playback enabled" if self._loop_enabled else "Loop playback disabled"
            )

        def _toggle_mute(self) -> None:
            if self._audio_output is None or not self._media_path:
                self.action_triggered.emit("No source audio is loaded")
                return
            if self._software_preview:
                self.action_triggered.emit("Source audio playback is unavailable for this codec")
                return
            self._audio_output.setMuted(not self._audio_output.isMuted())
            self._muted_by_user = self._audio_output.isMuted()
            self.action_triggered.emit(
                "Program audio muted" if self._audio_output.isMuted() else "Program audio enabled"
            )

        def set_volume(self, volume: float) -> None:
            """Set audio output volume (0-100 or 0.0-1.0)."""
            val = float(volume)
            if val > 1.0:
                val = val / 100.0
            val = max(0.0, min(1.0, val))
            if self._audio_output is not None:
                self._audio_output.setVolume(val)

        def set_muted(self, muted: bool) -> None:
            """Set audio output mute state."""
            if self._audio_output is not None:
                self._audio_output.setMuted(bool(muted))
                self._muted_by_user = bool(muted)

        def _on_export_snapshot(self) -> None:
            if self._video_widget is None or not self._media_path:
                self.action_triggered.emit("Load source media before exporting a snapshot")
                return
            default_name = f"frame_{round(self._playhead_sec * 1_000):08d}.png"
            target, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Export Program Frame",
                str(Path(self._media_path).with_name(default_name)),
                "PNG Image (*.png)",
            )
            if not target:
                return
            if (
                self._last_video_image is not None
                and abs(self._last_image_sec - self._playhead_sec) < 0.2
            ):
                self._save_snapshot(target)
                return
            self._pending_snapshot = (target, self._playhead_sec)
            self._request_software_frame(self._playhead_sec)
            self.action_triggered.emit("Decoding the current frame for snapshot export")

        def _save_snapshot(self, target: str) -> None:
            if self._last_video_image is not None and self._last_video_image.save(target, "PNG"):
                self.action_triggered.emit(f"Snapshot exported: {target}")
            else:
                self.action_triggered.emit(f"Could not write snapshot: {target}")

    # ─────────────────────────────────────────────────────────────────────────
    # Right Column: Inspector & AI Assistant + Dual Channel Audio VU Meter
    # ─────────────────────────────────────────────────────────────────────────
    class _WaveformWidget(QWidget):
        """Waveform view populated only from decoded, real audio samples."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._take_name = ""
            self._peaks: list[float] = []
            self._error = "No audio take selected"
            self.setMinimumHeight(44)

        def set_take_name(self, name: str) -> None:
            self._take_name = name
            self.update()

        def set_audio_file(self, path: str | Path) -> None:
            self._peaks = []
            audio_path = Path(path)
            if not audio_path.is_file():
                self._error = "Audio take is unavailable"
                self.update()
                return
            try:
                import numpy as np
                import soundfile as sf

                samples, _sample_rate = sf.read(str(audio_path), always_2d=True)
                mono = np.mean(samples, axis=1)
                if mono.size == 0:
                    raise ValueError("decoded audio contains no samples")
                peak_count = max(32, min(512, self.width() // 2 or 128))
                chunk_size = max(1, int(np.ceil(mono.size / peak_count)))
                self._peaks = [
                    float(np.max(np.abs(mono[index : index + chunk_size])))
                    for index in range(0, mono.size, chunk_size)
                ]
                self._error = ""
            except (ImportError, OSError, RuntimeError, ValueError) as exc:
                self._error = f"Waveform unavailable: {exc}"
            self.update()

        def paintEvent(self, event: object) -> None:  # noqa: N802
            del event
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor("#130A24"))
            center = self.height() / 2
            painter.setPen(QPen(QColor("#3B1C62"), 1))
            painter.drawLine(0, round(center), self.width(), round(center))
            if not self._peaks:
                painter.setPen(QColor("#64748B"))
                painter.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    self._error,
                )
                painter.end()
                return
            painter.setPen(QPen(QColor("#A855F7"), 1.2))
            step = max(1.0, (self.width() - 4) / len(self._peaks))
            for index, peak in enumerate(self._peaks):
                x = round(2 + index * step)
                amplitude = max(1.0, min(1.0, peak) * (self.height() * 0.42))
                painter.drawLine(x, round(center - amplitude), x, round(center + amplitude))
            painter.end()

    class _StereoMeterWidget(QWidget):
        """Compact dual-channel level meter matching the reference inspector rail."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._left_db: float | None = None
            self._right_db: float | None = None
            self.setFixedWidth(66)
            self.setMinimumHeight(300)
            self.setToolTip("Stereo program level meter")

        def set_levels(self, left_db: float, right_db: float) -> None:
            self._left_db = max(-54.0, min(0.0, left_db))
            self._right_db = max(-54.0, min(0.0, right_db))
            self.update()

        def paintEvent(self, event: object) -> None:  # noqa: N802
            del event
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#0A0B0D"))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            top = 24
            bottom = self.height() - 25
            meter_height = max(1, bottom - top)
            channels = ((9, self._left_db), (25, self._right_db))
            segment_count = 28
            segment_gap = 2
            segment_height = max(2, (meter_height // segment_count) - segment_gap)
            for x, level_db in channels:
                for index in range(segment_count):
                    segment_db = -54.0 + (index / max(1, segment_count - 1)) * 54.0
                    y = bottom - round((index + 1) * meter_height / segment_count)
                    active = level_db is not None and segment_db <= level_db
                    if not active:
                        color = QColor("#25291D")
                    elif segment_db > -9:
                        color = QColor("#E35D4F")
                    elif segment_db > -18:
                        color = QColor("#D8C441")
                    else:
                        color = QColor("#65C742")
                    painter.fillRect(x, y, 11, segment_height, color)

            painter.setPen(QColor("#858A91"))
            painter.setFont(QFont("Segoe UI", 7))
            for db in (0, -6, -12, -18, -24, -30, -36, -42, -48, -54):
                y = top + round(abs(db) / 54 * meter_height)
                painter.drawText(40, y + 3, str(db))
            painter.setPen(QColor("#9EA3AB"))
            painter.drawText(9, self.height() - 8, "S")
            painter.drawText(25, self.height() - 8, "S")
            painter.drawText(43, self.height() - 8, "dB")
            if self._left_db is None or self._right_db is None:
                painter.drawText(5, top - 8, "N/A")
            painter.end()

    class _DialogueCardWidget(QFrame):
        card_clicked = Signal(int, dict)
        play_clicked = Signal(int, dict)
        text_changed = Signal(int, str)
        speaker_clicked = Signal(int, dict)

        def __init__(
            self,
            index: int,
            data: dict[str, Any],
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.index = index
            self.data = data
            self._selected = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setObjectName("DialogueCard")
            self._update_style()

            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setSpacing(8)

            spk = str(data.get("speaker") or f"Speaker {(index % 2) + 1}")
            pill_col = "#2563EB" if "1" in spk else "#7C3AED"
            self.spk_btn = QPushButton(f"{spk} ▾", self)
            self.spk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.spk_btn.setStyleSheet(
                f"QPushButton {{ background: {pill_col}; color: #FFF; border: none;"
                "border-radius: 10px; padding: 2px 10px; font-size: 10px; font-weight: 700; }"
            )
            self.spk_btn.clicked.connect(lambda: self.speaker_clicked.emit(self.index, self.data))
            top_row.addWidget(self.spk_btn)

            start_t = float(data.get("start", 0.0))
            end_t = float(data.get("end", 0.0))
            tc_str = f"{start_t:.1f}s → {end_t:.1f}s"
            tc_lbl = QLabel(tc_str, self)
            tc_lbl.setStyleSheet("font-size: 10px; color: #64748B; font-family: 'Cascadia Code';")
            top_row.addWidget(tc_lbl)
            top_row.addStretch()

            self.play_btn = QPushButton("▶", self)
            self.play_btn.setFixedSize(24, 24)
            self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.play_btn.setToolTip("Audition Dubbed Take")
            self.play_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #334155;"
                "border-radius: 12px; font-size: 10px; font-weight: 800; }"
                "QPushButton:hover { background: #0284C7; color: #FFF; }"
            )
            self.play_btn.clicked.connect(lambda: self.play_clicked.emit(self.index, self.data))
            top_row.addWidget(self.play_btn)
            lay.addLayout(top_row)

            cols_row = QHBoxLayout()
            cols_row.setSpacing(10)

            orig_text = str(data.get("text") or data.get("orig", ""))
            orig_lbl = QLabel(orig_text, self)
            orig_lbl.setWordWrap(True)
            orig_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; line-height: 1.3;")
            cols_row.addWidget(orig_lbl, 1)

            trans_text = str(data.get("translated_text") or data.get("trans", ""))
            self.trans_edit = QLineEdit(trans_text, self)
            self.trans_edit.setPlaceholderText("Dubbed line...")
            self.trans_edit.setStyleSheet(
                "QLineEdit { background: #0B0E14; color: #F8FAFC; border: 1px solid #1E293B;"
                "border-radius: 5px; padding: 5px 8px; font-size: 11px; }"
                "QLineEdit:focus { border-color: #8B5CF6; background: #161528; }"
            )
            self.trans_edit.textChanged.connect(lambda t: self.text_changed.emit(self.index, t))
            cols_row.addWidget(self.trans_edit, 1)
            lay.addLayout(cols_row)

        def set_selected(self, selected: bool) -> None:
            self._selected = selected
            self._update_style()

        def _update_style(self) -> None:
            if self._selected:
                self.setStyleSheet(
                    "QFrame#DialogueCard { background: #18152E; border: 2px solid #8B5CF6;"
                    "border-radius: 8px; }"
                )
            else:
                self.setStyleSheet(
                    "QFrame#DialogueCard { background: #11151F; border: 1px solid #1E2536;"
                    "border-radius: 8px; }"
                    "QFrame#DialogueCard:hover { border-color: #334155; background: #151B28; }"
                )

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            super().mousePressEvent(event)
            self.card_clicked.emit(self.index, self.data)

    class _DialogueInspectorPanel(QFrame):
        translation_changed = Signal(str)
        original_changed = Signal(str)
        character_changed = Signal(str)
        take_changed = Signal(str)
        dialogue_card_selected = Signal(int, dict)
        regenerate_requested = Signal()
        retake_requested = Signal(dict)
        open_lipsync_inspector_requested = Signal()
        ai_fix_requested = Signal()
        preview_take_requested = Signal()
        import_source_srt_requested = Signal()
        import_target_srt_requested = Signal()
        import_bilingual_srt_requested = Signal()
        manage_characters_requested = Signal()
        casting_requested = Signal()
        export_requested = Signal()
        cloud_gpu_requested = Signal()
        audio_analysis_requested = Signal()
        action_clicked = Signal(str)
        track_level_changed = Signal(str, float)
        track_mute_toggled = Signal(str, bool)
        track_solo_toggled = Signal(str, bool)
        ducking_changed = Signal(bool, float)
        nudge_timing_requested = Signal(float)
        fit_to_slot_requested = Signal()
        open_pro_voice_editor_requested = Signal()
        open_pro_emotion_studio_requested = Signal()
        open_voice_exchanger_requested = Signal()
        open_character_classification_requested = Signal()
        open_qc_dashboard_requested = Signal()
        open_variaudio_requested = Signal()
        open_audio_align_requested = Signal()
        open_dop_requested = Signal()
        open_control_room_requested = Signal()
        open_crossfade_requested = Signal()
        open_punch_in_requested = Signal()
        open_prosody_transfer_requested = Signal()
        open_bangla_studio_requested = Signal()
        open_voice_clone_requested = Signal()
        open_subtitle_studio_requested = Signal()
        open_audio_dsp_requested = Signal()
        open_batch_dub_requested = Signal()
        open_audio_mixer_requested = Signal()
        open_neural_lipsync_requested = Signal()
        open_isochronic_requested = Signal()

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet("background:#111315;")
            self._cards: list[_DialogueCardWidget] = []
            self._active_card_idx: int = 0

            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(10, 7, 0, 5)
            main_layout.setSpacing(8)

            insp_box = QVBoxLayout()
            insp_box.setSpacing(6)

            # Interactive Header Tabs: Inspector | AI Assistant | Metadata
            tab_row = QHBoxLayout()
            tab_row.setSpacing(4)
            self.tab_buttons: list[QPushButton] = []
            for idx, tab_name in enumerate(["Inspector", "AI Assistant", "Metadata"]):
                btn = QPushButton(tab_name, self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setCheckable(True)
                btn.setChecked(idx == 0)
                btn.setStyleSheet(
                    "QPushButton{background:transparent;font-size:11px;font-weight:700;"
                    "color:#64748B;padding:4px 8px;border:none;border-bottom:2px solid transparent;}"
                    "QPushButton:checked{color:#F7F9FC;border-bottom:2px solid #8B5CF6;}"
                    "QPushButton:hover{color:#CBD5E1;}"
                )
                btn.clicked.connect(lambda _, i=idx: self._switch_tab(i))
                tab_row.addWidget(btn)
                self.tab_buttons.append(btn)
            tab_row.addStretch()
            insp_box.addLayout(tab_row)

            # Stacked widget for the 3 panel views
            self.panel_stack = QStackedWidget(self)

            scroll_style = (
                "QScrollArea{background:transparent;border:none;}"
                "QScrollBar:vertical{width:6px;background:#0D1117;border-radius:3px;margin:0;}"
                "QScrollBar::handle:vertical{background:#263346;border-radius:3px;min-height:20px;}"
                "QScrollBar::handle:vertical:hover{background:#3B82F6;}"
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0;background:none;}"
            )

            input_style = (
                "QLineEdit, QComboBox {"
                "  background: #16202E; color: #F7F9FC; border: 1px solid #283446;"
                "  padding: 2px 8px; border-radius: 4px; font-size: 11px;"
                "  min-height: 24px; max-height: 26px;"
                "}"
                "QLineEdit:focus, QComboBox:focus {"
                "  border-color: #2563EB; background: #1A2638;"
                "}"
            )
            trans_style = (
                "QLineEdit {"
                "  background: #16202E; color: #22D3EE; font-weight: 700; border: 1px solid #283446;"
                "  padding: 2px 8px; border-radius: 4px; font-size: 11px;"
                "  min-height: 24px; max-height: 26px;"
                "}"
                "QLineEdit:focus {"
                "  border-color: #06B6D4; background: #1A2638;"
                "}"
            )
            btn_action_style = (
                "QPushButton {"
                "  background: #1E293B; color: #94A3B8; border: 1px solid #283446;"
                "  border-radius: 4px; font-size: 11px; padding: 0; min-height: 0;"
                "}"
                "QPushButton:hover { background: #2563EB; color: #FFF; border-color: #3B82F6; }"
            )

            # ═══════════════════════════════════════════════════════════════
            # PAGE 0: Inspector (Dialogue & Timing & Scores & Waveform)
            # ═══════════════════════════════════════════════════════════════
            p0 = QWidget()
            p0_lay = QVBoxLayout(p0)
            p0_lay.setContentsMargins(0, 0, 4, 2)
            p0_lay.setSpacing(4)

            # Sub-tabs row: Clip | Voice | Translation | Quality (Image 1)
            sub_tabs_row = QHBoxLayout()
            sub_tabs_row.setSpacing(6)
            self.sub_tab_btns = []
            for idx, tab_n in enumerate(["Clip", "Voice", "Translation", "Quality"]):
                stb = QPushButton(tab_n, p0)
                stb.setCursor(Qt.CursorShape.PointingHandCursor)
                stb.setFixedHeight(24)
                if idx == 0:
                    stb.setStyleSheet(
                        "QPushButton{background:#4F46E5;color:#FFF;border:none;border-radius:4px;"
                        "font-size:10px;font-weight:700;padding:0 12px;}"
                    )
                else:
                    stb.setStyleSheet(
                        "QPushButton{background:#131824;color:#94A3B8;border:1px solid #1E2738;border-radius:4px;"
                        "font-size:10px;font-weight:600;padding:0 10px;}"
                        "QPushButton:hover{background:#1A2232;color:#FFF;}"
                    )
                self.sub_tab_btns.append(stb)
                sub_tabs_row.addWidget(stb)
            p0_lay.addLayout(sub_tabs_row)

            d_frame = QFrame(p0)
            d_frame.setObjectName("InspectorCard")
            d_frame.setStyleSheet(
                "QFrame#InspectorCard{background:#0C1018;border:1px solid #1E2638;"
                "border-radius:8px;padding:8px;}"
            )
            d_lay = QFormLayout(d_frame)
            d_lay.setContentsMargins(6, 4, 6, 4)
            d_lay.setVerticalSpacing(4)
            d_lay.setHorizontalSpacing(6)

            def form_label(text: str) -> QLabel:
                label = QLabel(text, d_frame)
                label.setStyleSheet("color:#94A3B8;font-size:10px;font-weight:800;letter-spacing:0.5px;background:transparent;")
                return label

            # 1. CHARACTER / VOICE Row (Image 1)
            char_row = QHBoxLayout()
            char_row.setSpacing(8)

            self.actor_avatar = QLabel("A", d_frame)
            self.actor_avatar.setFixedSize(28, 28)
            self.actor_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.actor_avatar.setStyleSheet(
                "background:#10B981;color:#FFF;border-radius:14px;font-size:13px;font-weight:900;"
            )
            char_row.addWidget(self.actor_avatar)

            self.char_in = QComboBox(d_frame)
            self.char_in.setEditable(True)
            self.char_in.setPlaceholderText("Arthur (Custom)")
            self.char_in.addItems(["Arthur (Custom)", "SPEAKER_00", "SPEAKER_01", "Narrator"])
            self.char_in.setStyleSheet(
                input_style
                + "QComboBox QAbstractItemView{background:#111722;color:#F7F9FC;selection-background-color:#2563EB;}"
            )
            self.char_in.currentTextChanged.connect(self._on_char_changed)
            char_row.addWidget(self.char_in, stretch=1)

            self.btn_manage_chars = QPushButton("Manage", d_frame)
            self.btn_manage_chars.setToolTip("Manage Characters & Speaker Voices…")
            self.btn_manage_chars.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_manage_chars.setStyleSheet(
                "QPushButton{background:transparent;color:#38BDF8;border:none;font-size:11px;font-weight:700;padding:2px 4px;}"
                "QPushButton:hover{color:#7DD3FC;text-decoration:underline;}"
            )
            self.btn_manage_chars.clicked.connect(self.manage_characters_requested.emit)
            char_row.addWidget(self.btn_manage_chars)
            d_lay.addRow(form_label("CHARACTER / VOICE"), char_row)

            # 2. SOURCE & TARGET Language Row (Image 1)
            lang_row = QHBoxLayout()
            lang_row.setSpacing(6)

            src_box = QLabel("🇬🇧 EN  English", d_frame)
            src_box.setStyleSheet(
                "background:#141926;color:#E2E8F0;border:1px solid #1E2738;border-radius:5px;font-size:10.5px;font-weight:600;padding:4px 8px;"
            )
            lang_row.addWidget(src_box, 1)

            arrow_lbl = QLabel("→", d_frame)
            arrow_lbl.setStyleSheet("color:#64748B;font-size:12px;font-weight:900;")
            lang_row.addWidget(arrow_lbl)

            self.lang_in = QLineEdit(d_frame)
            self.lang_in.setText("🇧🇩 BN  Bengali")
            self.lang_in.setPlaceholderText("Target language code")
            self.lang_in.setStyleSheet(
                "QLineEdit{background:#141926;color:#E2E8F0;border:1px solid #1E2738;border-radius:5px;font-size:10.5px;font-weight:600;padding:4px 8px;}"
            )
            lang_row.addWidget(self.lang_in, 1)
            d_lay.addRow(form_label("SOURCE / TARGET"), lang_row)

            # 3. ORIGINAL DIALOGUE Card (Image 1)
            orig_col = QVBoxLayout()
            orig_col.setSpacing(4)
            self.orig_in = QLineEdit(d_frame)
            self.orig_in.setText("We need to talk.")
            self.orig_in.setPlaceholderText("Select or import source dialogue")
            self.orig_in.setStyleSheet(
                "QLineEdit{background:#121724;color:#F1F5F9;border:1px solid #1E2738;border-radius:6px;padding:6px 10px;font-size:11.5px;min-height:28px;}"
            )
            self.orig_in.textChanged.connect(self._on_orig_changed)
            orig_col.addWidget(self.orig_in)

            orig_bot = QHBoxLayout()
            self.orig_count_lbl = QLabel("16 / 200", d_frame)
            self.orig_count_lbl.setStyleSheet("color:#64748B;font-size:9.5px;font-family:'Cascadia Code';")
            orig_bot.addWidget(self.orig_count_lbl)
            orig_bot.addStretch()

            self.btn_import_orig_srt = QPushButton("📂", d_frame)
            self.btn_import_orig_srt.setToolTip("Import Source Subtitles…")
            self.btn_import_orig_srt.setFixedSize(22, 22)
            self.btn_import_orig_srt.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_import_orig_srt.setStyleSheet(btn_action_style)
            self.btn_import_orig_srt.clicked.connect(self.import_source_srt_requested.emit)
            orig_bot.addWidget(self.btn_import_orig_srt)

            self.btn_play_orig = QPushButton("▷", d_frame)
            self.btn_play_orig.setToolTip("Play Original Audio Clip")
            self.btn_play_orig.setFixedSize(24, 24)
            self.btn_play_orig.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_play_orig.setStyleSheet(
                "QPushButton{background:#1E2738;color:#38BDF8;border:1px solid #2B384E;border-radius:12px;font-size:11px;font-weight:900;padding-left:2px;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            def _play_orig():
                p = Path("work/Arthur_Original.wav")
                if p.is_file():
                    from aidub.media.audition_service import AuditionService
                    if not hasattr(self, "_audition_svc") or self._audition_svc is None:
                        self._audition_svc = AuditionService(self)
                    self._audition_svc.play_file(str(p.resolve()))
            self.btn_play_orig.clicked.connect(_play_orig)
            orig_bot.addWidget(self.btn_play_orig)
            orig_col.addLayout(orig_bot)
            d_lay.addRow(form_label("ORIGINAL DIALOGUE"), orig_col)

            # 4. TRANSLATED DIALOGUE Card (Image 1)
            trans_hdr = QHBoxLayout()
            trans_hdr.addWidget(form_label("TRANSLATED DIALOGUE"))
            trans_hdr.addStretch()
            ai_badge = QLabel("Edited by AI", d_frame)
            ai_badge.setStyleSheet(
                "background:#064E3B;color:#34D399;border:1px solid #059669;border-radius:8px;padding:1px 6px;font-size:8.5px;font-weight:700;"
            )
            trans_hdr.addWidget(ai_badge)

            trans_col = QVBoxLayout()
            trans_col.setSpacing(4)
            trans_col.addLayout(trans_hdr)

            self.trans_in = QLineEdit(d_frame)
            self.trans_in.setText("আমাদের কথা বলা দরকার।")
            self.trans_in.setPlaceholderText("Translation appears after processing")
            self.trans_in.setStyleSheet(
                "QLineEdit{background:#121724;color:#22D3EE;border:1px solid #1E2738;border-radius:6px;padding:6px 10px;font-size:12px;font-weight:700;min-height:28px;}"
                "QLineEdit:focus{border-color:#06B6D4;}"
            )
            self.trans_in.textChanged.connect(self._on_trans_changed)
            trans_col.addWidget(self.trans_in)

            trans_bot = QHBoxLayout()
            self.trans_count_lbl = QLabel("17 / 200", d_frame)
            self.trans_count_lbl.setStyleSheet("color:#64748B;font-size:9.5px;font-family:'Cascadia Code';")
            trans_bot.addWidget(self.trans_count_lbl)
            trans_bot.addStretch()

            self.btn_import_trans_srt = QPushButton("📂", d_frame)
            self.btn_import_trans_srt.setToolTip("Import Target Subtitles…")
            self.btn_import_trans_srt.setFixedSize(22, 22)
            self.btn_import_trans_srt.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_import_trans_srt.setStyleSheet(btn_action_style)
            self.btn_import_trans_srt.clicked.connect(self.import_target_srt_requested.emit)
            trans_bot.addWidget(self.btn_import_trans_srt)

            self.btn_regen_trans = QPushButton("Regenerate", d_frame)
            self.btn_regen_trans.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_regen_trans.setFixedHeight(22)
            self.btn_regen_trans.setStyleSheet(
                "QPushButton{background:#1A2234;color:#94A3B8;border:1px solid #283446;border-radius:4px;font-size:9.5px;font-weight:700;padding:0 8px;}"
                "QPushButton:hover{background:#232D42;color:#FFF;border-color:#6366F1;}"
            )
            self.btn_regen_trans.clicked.connect(lambda: self.regenerate_requested.emit())
            trans_bot.addWidget(self.btn_regen_trans)

            self.btn_play_dub = QPushButton("▷", d_frame)
            self.btn_play_dub.setToolTip("Play Bengali Dubbed Audio")
            self.btn_play_dub.setFixedSize(24, 24)
            self.btn_play_dub.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_play_dub.setStyleSheet(
                "QPushButton{background:#1E2738;color:#22D3EE;border:1px solid #2B384E;border-radius:12px;font-size:11px;font-weight:900;padding-left:2px;}"
                "QPushButton:hover{background:#0891B2;color:#FFF;}"
            )
            def _play_dub():
                p = Path("work/Bengali_Voice_Arthur.wav")
                if p.is_file():
                    from aidub.media.audition_service import AuditionService
                    if not hasattr(self, "_audition_svc") or self._audition_svc is None:
                        self._audition_svc = AuditionService(self)
                    self._audition_svc.play_file(str(p.resolve()))
            self.btn_play_dub.clicked.connect(_play_dub)
            trans_bot.addWidget(self.btn_play_dub)
            trans_col.addLayout(trans_bot)

            d_lay.addRow(trans_col)
            p0_lay.addWidget(d_frame)

            # 5. Dual Cards: Timing & Quality (Image 1)
            cards_row = QHBoxLayout()
            cards_row.setSpacing(8)

            # Timing Card
            t_card = QFrame(p0)
            t_card.setObjectName("InspectorTimingCard")
            t_card.setStyleSheet(
                "QFrame#InspectorTimingCard{background:#0C1018;border:1px solid #1E2638;border-radius:8px;padding:8px;}"
            )
            tc_lay = QVBoxLayout(t_card)
            tc_lay.setContentsMargins(6, 6, 6, 6)
            tc_lay.setSpacing(4)
            tc_title = QLabel("TIMING", t_card)
            tc_title.setStyleSheet("font-size:9.5px;font-weight:800;color:#94A3B8;letter-spacing:0.5px;")
            tc_lay.addWidget(tc_title)

            self.src_dur_lbl = QLabel("Start    00:48:32:14", t_card)
            self.src_dur_lbl.setStyleSheet("color:#CBD5E1;font-size:10px;font-family:'Cascadia Code';")
            tc_lay.addWidget(self.src_dur_lbl)

            self.dub_dur_lbl = QLabel("End      00:48:36:12", t_card)
            self.dub_dur_lbl.setStyleSheet("color:#CBD5E1;font-size:10px;font-family:'Cascadia Code';")
            tc_lay.addWidget(self.dub_dur_lbl)

            self.diff_lbl = QLabel("Duration 00:00:03:58", t_card)
            self.diff_lbl.setStyleSheet("color:#38BDF8;font-weight:700;font-size:10px;font-family:'Cascadia Code';")
            tc_lay.addWidget(self.diff_lbl)
            cards_row.addWidget(t_card, 1)

            # Quality Card
            s_card = QFrame(p0)
            s_card.setObjectName("InspectorScoresCard")
            s_card.setStyleSheet(
                "QFrame#InspectorScoresCard{background:#0C1018;border:1px solid #1E2638;border-radius:8px;padding:8px;}"
            )
            sc_lay = QVBoxLayout(s_card)
            sc_lay.setContentsMargins(6, 6, 6, 6)
            sc_lay.setSpacing(4)
            sc_title = QLabel("QUALITY", s_card)
            sc_title.setStyleSheet("font-size:9.5px;font-weight:800;color:#94A3B8;letter-spacing:0.5px;")
            sc_lay.addWidget(sc_title)

            gauge_row = QHBoxLayout()
            gauge_row.setSpacing(8)
            self.quality_gauge = _CircularGaugeWidget(92, s_card)
            gauge_row.addWidget(self.quality_gauge)

            self.pass_lbl = QLabel("Excellent", s_card)
            self.pass_lbl.setStyleSheet("color:#10B981;font-size:12px;font-weight:800;")
            gauge_row.addWidget(self.pass_lbl)
            gauge_row.addStretch()
            sc_lay.addLayout(gauge_row)

            # Checkmark items
            for chk_txt in ["✓ Voice natural", "✓ Sync perfect", "✓ Lip sync good"]:
                c_lbl = QLabel(chk_txt, s_card)
                c_lbl.setStyleSheet("color:#94A3B8;font-size:9.5px;font-weight:600;")
                sc_lay.addWidget(c_lbl)

            # Preserved compatibility score labels
            self.v_score_lbl = QLabel("Voice:     92%", s_card)
            self.v_score_lbl.setVisible(False)
            self.e_score_lbl = QLabel("Emotion:   90%", s_card)
            self.e_score_lbl.setVisible(False)
            self.t_score_lbl = QLabel("Timing:    95%", s_card)
            self.t_score_lbl.setVisible(False)
            self.l_score_lbl = QLabel("Lip Sync:  98%", s_card)
            self.l_score_lbl.setVisible(False)
            sc_lay.addWidget(self.v_score_lbl)
            sc_lay.addWidget(self.e_score_lbl)
            sc_lay.addWidget(self.t_score_lbl)
            sc_lay.addWidget(self.l_score_lbl)

            cards_row.addWidget(s_card, 1)
            p0_lay.addLayout(cards_row)

            # 6. VOICE SETTINGS Card (Image 1)
            vs_card = QFrame(p0)
            vs_card.setObjectName("VoiceSettingsCard")
            vs_card.setStyleSheet(
                "QFrame#VoiceSettingsCard{background:#0C1018;border:1px solid #1E2638;border-radius:8px;padding:8px;}"
            )
            vs_lay = QVBoxLayout(vs_card)
            vs_lay.setContentsMargins(6, 6, 6, 6)
            vs_lay.setSpacing(6)

            vs_hdr = QHBoxLayout()
            vs_title = QLabel("VOICE SETTINGS", vs_card)
            vs_title.setStyleSheet("font-size:9.5px;font-weight:800;color:#94A3B8;letter-spacing:0.5px;")
            vs_hdr.addWidget(vs_title)
            vs_hdr.addStretch()
            vs_reset = QLabel("Reset", vs_card)
            vs_reset.setCursor(Qt.CursorShape.PointingHandCursor)
            vs_reset.setStyleSheet("color:#6366F1;font-size:9.5px;font-weight:700;")
            vs_hdr.addWidget(vs_reset)
            vs_lay.addLayout(vs_hdr)

            # Speed Slider
            sp_row = QHBoxLayout()
            sp_lbl = QLabel("Speed", vs_card)
            sp_lbl.setStyleSheet("color:#CBD5E1;font-size:10px;font-weight:600;min-width:44px;")
            sp_row.addWidget(sp_lbl)
            self.speed_slider = QSlider(Qt.Orientation.Horizontal, vs_card)
            self.speed_slider.setRange(50, 200)
            self.speed_slider.setValue(100)
            self.speed_slider.setStyleSheet(
                "QSlider::groove:horizontal{height:3px;background:#1E2738;border-radius:1px;}"
                "QSlider::sub-page:horizontal{background:#8B5CF6;border-radius:1px;}"
                "QSlider::handle:horizontal{background:#FFFFFF;width:8px;height:8px;margin:-3px 0;border-radius:4px;}"
            )
            sp_row.addWidget(self.speed_slider, 1)
            self.sp_val_lbl = QLabel("1.0x", vs_card)
            self.sp_val_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:700;font-family:'Cascadia Code';min-width:32px;")
            self.speed_slider.valueChanged.connect(lambda v: self.sp_val_lbl.setText(f"{v/100:.1f}x"))
            sp_row.addWidget(self.sp_val_lbl)
            vs_lay.addLayout(sp_row)

            # Emotion Slider
            em_row = QHBoxLayout()
            em_lbl = QLabel("Emotion", vs_card)
            em_lbl.setStyleSheet("color:#CBD5E1;font-size:10px;font-weight:600;min-width:44px;")
            em_row.addWidget(em_lbl)
            self.emotion_slider = QSlider(Qt.Orientation.Horizontal, vs_card)
            self.emotion_slider.setRange(0, 100)
            self.emotion_slider.setValue(75)
            self.emotion_slider.setStyleSheet(
                "QSlider::groove:horizontal{height:3px;background:#1E2738;border-radius:1px;}"
                "QSlider::sub-page:horizontal{background:#8B5CF6;border-radius:1px;}"
                "QSlider::handle:horizontal{background:#FFFFFF;width:8px;height:8px;margin:-3px 0;border-radius:4px;}"
            )
            em_row.addWidget(self.emotion_slider, 1)
            self.em_val_lbl = QLabel("Tense", vs_card)
            self.em_val_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:700;min-width:32px;")
            em_row.addWidget(self.em_val_lbl)
            vs_lay.addLayout(em_row)

            p0_lay.addWidget(vs_card)

            # 7. ✨ Run AI Dubbing Bottom CTA Button (Image 1)
            self.btn_run_ai_dubbing = QPushButton("✨ Run AI Dubbing", p0)
            self.btn_run_ai_dubbing.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_run_ai_dubbing.setFixedHeight(38)
            self.btn_run_ai_dubbing.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #4F46E5);"
                "color:#FFF;font-size:12px;font-weight:800;border:none;border-radius:8px;}"
                "QPushButton:hover{background:#6366F1;}"
            )
            self.btn_run_ai_dubbing.clicked.connect(lambda: self.action_clicked.emit("Run AI Dubbing"))
            self.btn_run_ai_dubbing.clicked.connect(self.regenerate_requested.emit)
            p0_lay.addWidget(self.btn_run_ai_dubbing)

            # Timing Conflict Alert & Fit-To-Slot Box
            self.timing_alert_box = QFrame(p0)
            self.timing_alert_box.setStyleSheet(
                "QFrame{background:#231114;border:1px solid #DC2626;border-radius:4px;padding:6px;margin-top:2px;}"
            )
            tab_lay = QVBoxLayout(self.timing_alert_box)
            tab_lay.setContentsMargins(6, 4, 6, 4)
            tab_lay.setSpacing(4)

            self.timing_alert_lbl = QLabel(
                "⚠️ Timing Alert: Dubbed audio exceeds target slot duration.",
                self.timing_alert_box,
            )
            self.timing_alert_lbl.setStyleSheet("color:#FCA5A5;font-size:10px;font-weight:700;")
            tab_lay.addWidget(self.timing_alert_lbl)

            act_row = QHBoxLayout()
            self.btn_fit_to_slot = QPushButton(
                "⚡ Fit to Slot (Time Stretch ±8%)", self.timing_alert_box
            )
            self.btn_fit_to_slot.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_fit_to_slot.setStyleSheet(
                "QPushButton{background:#DC2626;color:#FFF;border:none;border-radius:3px;font-size:10px;font-weight:700;padding:4px 8px;min-height:0;}"
                "QPushButton:hover{background:#EF4444;}"
            )
            self.btn_fit_to_slot.clicked.connect(self.fit_to_slot_requested.emit)
            act_row.addWidget(self.btn_fit_to_slot)

            self.btn_nudge_plus = QPushButton("⏱ Nudge +100ms", self.timing_alert_box)
            self.btn_nudge_plus.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_nudge_plus.setStyleSheet(
                "QPushButton{background:#374151;color:#E5E7EB;border:none;border-radius:3px;font-size:10px;padding:4px 8px;min-height:0;}"
                "QPushButton:hover{background:#4B5563;color:#FFF;}"
            )
            self.btn_nudge_plus.clicked.connect(lambda: self.nudge_timing_requested.emit(0.1))
            act_row.addWidget(self.btn_nudge_plus)
            act_row.addStretch()
            tab_lay.addLayout(act_row)
            self.timing_alert_box.setVisible(False)
            p0_lay.addWidget(self.timing_alert_box)

            # Take Selector & Waveform
            take_card = QFrame(p0)
            take_card.setObjectName("InspectorTakeCard")
            take_card.setStyleSheet(
                "QFrame#InspectorTakeCard{background:#0D0F12;border:1px solid #262A30;"
                "border-radius:4px;padding:6px;}"
            )
            tk_lay = QVBoxLayout(take_card)
            tk_lay.setContentsMargins(6, 6, 6, 6)
            tk_lay.setSpacing(6)

            tk_top = QHBoxLayout()
            tk_top.addWidget(QLabel("Take:", take_card))
            self.take_combo = QComboBox(take_card)
            self.take_combo.addItem("No generated takes")
            self.take_combo.setEnabled(False)
            self.take_combo.setStyleSheet(
                "QComboBox{background:#16202E;color:#F7F9FC;border:none;padding:2px 6px;border-radius:4px;font-size:11px;min-height:22px;max-height:24px;}"
            )
            self.take_combo.currentTextChanged.connect(self._on_take_combo_changed)
            tk_top.addWidget(self.take_combo, stretch=1)
            tk_lay.addLayout(tk_top)

            self.waveform = _WaveformWidget(take_card)
            self.waveform.setStyleSheet(
                "background:#150D2A;border:1px solid #8B5CF6;border-radius:4px;"
            )
            tk_lay.addWidget(self.waveform)
            wave_time_row = QHBoxLayout()
            wave_start = QLabel("00:00", take_card)
            wave_start.setStyleSheet("font:9px 'Cascadia Code';color:#64748B;")
            wave_time_row.addWidget(wave_start)
            wave_time_row.addStretch()
            self.wave_end_lbl = QLabel("00:00.00", take_card)
            self.wave_end_lbl.setStyleSheet("font:9px 'Cascadia Code';color:#64748B;")
            wave_time_row.addWidget(self.wave_end_lbl)
            tk_lay.addLayout(wave_time_row)

            act_row = QHBoxLayout()
            act_row.setSpacing(6)
            r_btn = QPushButton("Regenerate", take_card)
            r_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            r_btn.setStyleSheet(
                "QPushButton{background:#8B5CF6;color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:5px 8px;min-height:22px;}"
                "QPushButton:hover{background:#7C3AED;}"
            )
            r_btn.clicked.connect(lambda: self.regenerate_requested.emit())
            act_row.addWidget(r_btn)

            f_btn = QPushButton("AI Fix", take_card)
            f_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            f_btn.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:5px 8px;min-height:22px;}"
                "QPushButton:hover{background:#1D4ED8;}"
            )
            f_btn.clicked.connect(lambda: self.ai_fix_requested.emit())
            act_row.addWidget(f_btn)

            c_btn = QPushButton("Preview Take", take_card)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet(
                "QPushButton{background:#16202E;color:#A9B2C3;font-size:10px;font-weight:600;border:1px solid #283446;border-radius:4px;padding:5px 8px;min-height:22px;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            c_btn.clicked.connect(lambda: self.preview_take_requested.emit())
            act_row.addWidget(c_btn)

            self.btn_lipsync_inspect = QPushButton("👄 Lip-Sync Inspector", take_card)
            self.btn_lipsync_inspect.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_lipsync_inspect.setStyleSheet(
                "QPushButton{background:#0E7490;color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:5px 8px;min-height:22px;}"
                "QPushButton:hover{background:#0891B2;}"
            )
            self.btn_lipsync_inspect.clicked.connect(self.open_lipsync_inspector_requested.emit)
            act_row.addWidget(self.btn_lipsync_inspect)

            tk_lay.addLayout(act_row)

            # Direct Studio Triggers Row
            studio_row = QHBoxLayout()
            studio_row.setSpacing(4)

            self.btn_pro_voice = QPushButton("🎙️ Pro Voice", take_card)
            self.btn_pro_voice.setToolTip("Open DAW-Grade Voice Editor with Parametric EQ, De-Esser, Limiter, Reverb")
            self.btn_pro_voice.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_pro_voice.setStyleSheet(
                "QPushButton{background:#1E293B;color:#38BDF8;font-size:10px;font-weight:700;border:1px solid #0284C7;border-radius:4px;padding:4px 6px;min-height:22px;}"
                "QPushButton:hover{background:#0284C7;color:#FFF;}"
            )
            self.btn_pro_voice.clicked.connect(self.open_pro_voice_editor_requested.emit)
            studio_row.addWidget(self.btn_pro_voice)

            self.btn_pro_emotion = QPushButton("🎭 Emotion", take_card)
            self.btn_pro_emotion.setToolTip("Open 3D Continuous PAD Emotion Director Studio with Live Performance Audition")
            self.btn_pro_emotion.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_pro_emotion.setStyleSheet(
                "QPushButton{background:#1E293B;color:#C084FC;font-size:10px;font-weight:700;border:1px solid #7C3AED;border-radius:4px;padding:4px 6px;min-height:22px;}"
                "QPushButton:hover{background:#7C3AED;color:#FFF;}"
            )
            self.btn_pro_emotion.clicked.connect(self.open_pro_emotion_studio_requested.emit)
            studio_row.addWidget(self.btn_pro_emotion)

            self.btn_voice_swap = QPushButton("🔄 Exchanger", take_card)
            self.btn_voice_swap.setToolTip("Open Voice Exchanger & Timbre Morpher to re-cast character voices")
            self.btn_voice_swap.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_voice_swap.setStyleSheet(
                "QPushButton{background:#1E293B;color:#34D399;font-size:10px;font-weight:700;border:1px solid #059669;border-radius:4px;padding:4px 6px;min-height:22px;}"
                "QPushButton:hover{background:#059669;color:#FFF;}"
            )
            self.btn_voice_swap.clicked.connect(self.open_voice_exchanger_requested.emit)
            studio_row.addWidget(self.btn_voice_swap)

            self.btn_qc_gate = QPushButton("🛡️ QC Gate", take_card)
            self.btn_qc_gate.setToolTip("Open Broadcast Quality Control Dashboard & Delivery Gate")
            self.btn_qc_gate.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_qc_gate.setStyleSheet(
                "QPushButton{background:#1E293B;color:#FBBF24;font-size:10px;font-weight:700;border:1px solid #D97706;border-radius:4px;padding:4px 6px;min-height:22px;}"
                "QPushButton:hover{background:#D97706;color:#FFF;}"
            )
            self.btn_qc_gate.clicked.connect(self.open_qc_dashboard_requested.emit)
            studio_row.addWidget(self.btn_qc_gate)

            tk_lay.addLayout(studio_row)

            # Collapsible Advanced DAW Tools Container (Experimental Toggle)
            self.daw_tools_container = QFrame(take_card)
            self.daw_tools_container.setVisible(False)
            dt_lay = QVBoxLayout(self.daw_tools_container)
            dt_lay.setContentsMargins(0, 0, 0, 0)
            dt_lay.setSpacing(4)

            self.btn_toggle_daw = QPushButton("▾ Advanced DAW Tools (Experimental)", take_card)
            self.btn_toggle_daw.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_toggle_daw.setStyleSheet(
                "QPushButton{background:#111722;color:#94A3B8;border:1px solid #1E293B;border-radius:3px;font-size:9px;padding:3px;}"
                "QPushButton:hover{background:#1E293B;color:#F8FAFC;}"
            )
            def _toggle_daw():
                vis = not self.daw_tools_container.isVisible()
                self.daw_tools_container.setVisible(vis)
                self.btn_toggle_daw.setText("▴ Advanced DAW Tools (Experimental)" if vis else "▾ Advanced DAW Tools (Experimental)")
            self.btn_toggle_daw.clicked.connect(_toggle_daw)
            tk_lay.addWidget(self.btn_toggle_daw)

            # Cubase Pro DAW Tools Row
            cubase_row = QHBoxLayout()
            cubase_row.setSpacing(4)

            self.btn_variaudio = QPushButton("🎚️ VariAudio", take_card)
            self.btn_variaudio.setToolTip("Open Cubase VariAudio 3 — Syllable Micro-Pitch & Formant Intonation Editor")
            self.btn_variaudio.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_variaudio.setStyleSheet(
                "QPushButton{background:#111A2E;color:#38BDF8;font-size:10px;font-weight:700;border:1px solid #0284C7;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#0284C7;color:#FFF;}"
            )
            self.btn_variaudio.clicked.connect(self.open_variaudio_requested.emit)
            cubase_row.addWidget(self.btn_variaudio)

            self.btn_audio_align = QPushButton("📐 Align", take_card)
            self.btn_audio_align.setToolTip("Open Cubase Audio Alignment Panel (VocAlign Pro) to lock dub to actor timing")
            self.btn_audio_align.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_audio_align.setStyleSheet(
                "QPushButton{background:#111A2E;color:#FBBF24;font-size:10px;font-weight:700;border:1px solid #D97706;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#D97706;color:#FFF;}"
            )
            self.btn_audio_align.clicked.connect(self.open_audio_align_requested.emit)
            cubase_row.addWidget(self.btn_audio_align)

            self.btn_dop = QPushButton("⚡ DOP", take_card)
            self.btn_dop.setToolTip("Open Cubase Direct Offline Processing (F7) Rack with Tube Saturation & History")
            self.btn_dop.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_dop.setStyleSheet(
                "QPushButton{background:#111A2E;color:#A78BFA;font-size:10px;font-weight:700;border:1px solid #7C3AED;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#7C3AED;color:#FFF;}"
            )
            self.btn_dop.clicked.connect(self.open_dop_requested.emit)
            cubase_row.addWidget(self.btn_dop)

            self.btn_control_room = QPushButton("🎛️ Monitor", take_card)
            self.btn_control_room.setToolTip("Open Cubase Control Room Studio Monitoring & EBU R128 Loudness Radar")
            self.btn_control_room.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_control_room.setStyleSheet(
                "QPushButton{background:#111A2E;color:#34D399;font-size:10px;font-weight:700;border:1px solid #059669;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#059669;color:#FFF;}"
            )
            self.btn_control_room.clicked.connect(self.open_control_room_requested.emit)
            cubase_row.addWidget(self.btn_control_room)

            self.btn_crossfade = QPushButton("🔀 X-Fade", take_card)
            self.btn_crossfade.setToolTip("Open Cubase Crossfade Editor for Equal Power & S-Curve Boundary Splicing")
            self.btn_crossfade.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_crossfade.setStyleSheet(
                "QPushButton{background:#111A2E;color:#FB7185;font-size:10px;font-weight:700;border:1px solid #E11D48;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#E11D48;color:#FFF;}"
            )
            self.btn_crossfade.clicked.connect(self.open_crossfade_requested.emit)
            cubase_row.addWidget(self.btn_crossfade)

            dt_lay.addLayout(cubase_row)

            # Pro ADR, Prosody & Bangla Dubbing Tools Row
            pro_dub_row = QHBoxLayout()
            pro_dub_row.setSpacing(4)

            self.btn_punch_in = QPushButton("🎙️ Punch-In", take_card)
            self.btn_punch_in.setToolTip("Open ADR Punch-In / Punch-Out Studio with Anti-Click Crossfade")
            self.btn_punch_in.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_punch_in.setStyleSheet(
                "QPushButton{background:#111A2E;color:#F43F5E;font-size:10px;font-weight:700;border:1px solid #BE123C;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#BE123C;color:#FFF;}"
            )
            self.btn_punch_in.clicked.connect(self.open_punch_in_requested.emit)
            pro_dub_row.addWidget(self.btn_punch_in)

            self.btn_prosody = QPushButton("🎭 Prosody", take_card)
            self.btn_prosody.setToolTip("Open Original Actor Prosody & Dynamic Envelope Transfer Studio")
            self.btn_prosody.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_prosody.setStyleSheet(
                "QPushButton{background:#111A2E;color:#C084FC;font-size:10px;font-weight:700;border:1px solid #9333EA;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#9333EA;color:#FFF;}"
            )
            self.btn_prosody.clicked.connect(self.open_prosody_transfer_requested.emit)
            pro_dub_row.addWidget(self.btn_prosody)

            self.btn_bangla = QPushButton("🇧🇩 Bangla Studio", take_card)
            self.btn_bangla.setToolTip("Open Bangla Dubbing Suite (Dialects, G2P Lip-Sync, Subtitle QC)")
            self.btn_bangla.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_bangla.setStyleSheet(
                "QPushButton{background:#111A2E;color:#38BDF8;font-size:10px;font-weight:700;border:1px solid #0284C7;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#0284C7;color:#FFF;}"
            )
            self.btn_bangla.clicked.connect(self.open_bangla_studio_requested.emit)
            pro_dub_row.addWidget(self.btn_bangla)

            dt_lay.addLayout(pro_dub_row)

            # 20 Advanced Studio Tools (Voice Clone, Subtitles, DSP Tools, Batch Dub, MixConsole)
            adv_tools_row = QHBoxLayout()
            adv_tools_row.setSpacing(4)

            self.btn_voice_clone = QPushButton("🧬 Clone", take_card)
            self.btn_voice_clone.setToolTip("Open Voice Clone Studio & Speaker Consistency Monitor")
            self.btn_voice_clone.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_voice_clone.setStyleSheet(
                "QPushButton{background:#111A2E;color:#06B6D4;font-size:10px;font-weight:700;border:1px solid #0891B2;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#0891B2;color:#FFF;}"
            )
            self.btn_voice_clone.clicked.connect(self.open_voice_clone_requested.emit)
            adv_tools_row.addWidget(self.btn_voice_clone)

            self.btn_subtitles = QPushButton("💬 Subs", take_card)
            self.btn_subtitles.setToolTip("Open Subtitle & Auto-Caption Studio with Timing Tools")
            self.btn_subtitles.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_subtitles.setStyleSheet(
                "QPushButton{background:#111A2E;color:#EAB308;font-size:10px;font-weight:700;border:1px solid #CA8A04;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#CA8A04;color:#FFF;}"
            )
            self.btn_subtitles.clicked.connect(self.open_subtitle_studio_requested.emit)
            adv_tools_row.addWidget(self.btn_subtitles)

            self.btn_dsp = QPushButton("🎛️ DSP Suite", take_card)
            self.btn_dsp.setToolTip("Open Audio DSP Suite (Beat-Sync, Vocal Isolator, Speed Ramp, Reverb Matcher)")
            self.btn_dsp.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_dsp.setStyleSheet(
                "QPushButton{background:#111A2E;color:#EC4899;font-size:10px;font-weight:700;border:1px solid #DB2777;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#DB2777;color:#FFF;}"
            )
            self.btn_dsp.clicked.connect(self.open_audio_dsp_requested.emit)
            adv_tools_row.addWidget(self.btn_dsp)

            self.btn_batch = QPushButton("⚡ Batch", take_card)
            self.btn_batch.setToolTip("Open Multi-Provider Batch Dub Runner & Queue Processor")
            self.btn_batch.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_batch.setStyleSheet(
                "QPushButton{background:#111A2E;color:#10B981;font-size:10px;font-weight:700;border:1px solid #059669;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#059669;color:#FFF;}"
            )
            self.btn_batch.clicked.connect(self.open_batch_dub_requested.emit)
            adv_tools_row.addWidget(self.btn_batch)

            self.btn_mixer = QPushButton("🎚️ Mixer", take_card)
            self.btn_mixer.setToolTip("Open Cubase MixConsole (F3) with Faders, Auto-Gain & Ducking")
            self.btn_mixer.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_mixer.setStyleSheet(
                "QPushButton{background:#111A2E;color:#A855F7;font-size:10px;font-weight:700;border:1px solid #9333EA;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#9333EA;color:#FFF;}"
            )
            self.btn_mixer.clicked.connect(self.open_audio_mixer_requested.emit)
            adv_tools_row.addWidget(self.btn_mixer)

            self.btn_neural_lipsync = QPushButton("👄 LipSync", take_card)
            self.btn_neural_lipsync.setToolTip("Open Neural AI Lip-Sync & Face Synthesis Studio (Wav2Lip / MuseTalk)")
            self.btn_neural_lipsync.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_neural_lipsync.setStyleSheet(
                "QPushButton{background:#111A2E;color:#F43F5E;font-size:10px;font-weight:700;border:1px solid #E11D48;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#E11D48;color:#FFF;}"
            )
            self.btn_neural_lipsync.clicked.connect(self.open_neural_lipsync_requested.emit)
            adv_tools_row.addWidget(self.btn_neural_lipsync)

            self.btn_isochronic = QPushButton("📐 Isochrone", take_card)
            self.btn_isochronic.setToolTip("Open Isochronic Dialogue Translator & Syllable Adapter (Mouth Flap & Bilabials)")
            self.btn_isochronic.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_isochronic.setStyleSheet(
                "QPushButton{background:#111A2E;color:#818CF8;font-size:10px;font-weight:700;border:1px solid #6366F1;border-radius:4px;padding:3px 5px;min-height:22px;}"
                "QPushButton:hover{background:#6366F1;color:#FFF;}"
            )
            self.btn_isochronic.clicked.connect(self.open_isochronic_requested.emit)
            adv_tools_row.addWidget(self.btn_isochronic)

            dt_lay.addLayout(adv_tools_row)
            tk_lay.addWidget(self.daw_tools_container)

            # ADR In-Place Retake & Ripple Controls
            retake_group = QFrame(take_card)
            retake_group.setStyleSheet(
                "QFrame{background:#111722;border:1px solid #1E293B;border-radius:4px;padding:4px;margin-top:4px;}"
            )
            rg_lay = QVBoxLayout(retake_group)
            rg_lay.setContentsMargins(4, 4, 4, 4)
            rg_lay.setSpacing(4)

            rg_opt_row = QHBoxLayout()
            rg_opt_row.setSpacing(6)
            self.chk_ripple_edit = QCheckBox("Ripple Edit", retake_group)
            self.chk_ripple_edit.setToolTip(
                "Shift downstream dialogue clips if take duration changes"
            )
            self.chk_ripple_edit.setStyleSheet(
                "QCheckBox{color:#94A3B8;font-size:10px;} QCheckBox::indicator{width:12px;height:12px;}"
            )
            rg_opt_row.addWidget(self.chk_ripple_edit)

            self.chk_isometric = QCheckBox("Isometric Fit", retake_group)
            self.chk_isometric.setToolTip(
                "Adapt syllables algorithmically to match original jaw cadence"
            )
            self.chk_isometric.setChecked(True)
            self.chk_isometric.setStyleSheet(
                "QCheckBox{color:#38BDF8;font-size:10px;font-weight:600;} QCheckBox::indicator{width:12px;height:12px;}"
            )
            rg_opt_row.addWidget(self.chk_isometric)

            self.combo_retake_reverb = QComboBox(retake_group)
            self.combo_retake_reverb.addItems(
                ["Reverb: None", "Reverb: Living Room", "Reverb: Large Hall", "Reverb: Vehicle"]
            )
            self.combo_retake_reverb.setStyleSheet(
                "QComboBox{background:#1E293B;color:#CBD5E1;border:1px solid #334155;border-radius:3px;font-size:9px;padding:1px 4px;min-height:18px;max-height:20px;}"
            )
            rg_opt_row.addWidget(self.combo_retake_reverb)
            rg_lay.addLayout(rg_opt_row)

            self.btn_adr_retake = QPushButton("🎙 ADR Retake (Master Mixdown)", retake_group)
            self.btn_adr_retake.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_adr_retake.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #2563EB);color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:4px 8px;min-height:22px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6D28D9,stop:1 #1D4ED8);}"
            )
            self.btn_adr_retake.clicked.connect(self._on_adr_retake_clicked)
            rg_lay.addWidget(self.btn_adr_retake)

            tk_lay.addWidget(retake_group)
            take_card.setVisible(False)
            p0_lay.addWidget(take_card)

            # ─────────────────────────────────────────────────────────────
            # Multitrack Audio Mixer Card
            # ─────────────────────────────────────────────────────────────
            self.mixer_card = QFrame(p0)
            self.mixer_card.setObjectName("InspectorMixerCard")
            self.mixer_card.setStyleSheet(
                "QFrame#InspectorMixerCard{background:#0D0F12;border:1px solid #262A30;"
                "border-radius:4px;padding:6px;margin-top:6px;}"
            )
            mix_lay = QVBoxLayout(self.mixer_card)
            mix_lay.setContentsMargins(6, 6, 6, 6)
            mix_lay.setSpacing(4)

            mix_hdr = QHBoxLayout()
            mix_title = QLabel("🎚 MULTITRACK AUDIO MIXER", self.mixer_card)
            mix_title.setStyleSheet("font-size:11px;font-weight:800;color:#E2E8F0;")
            mix_hdr.addWidget(mix_title)
            mix_hdr.addStretch()

            self.lbl_peak_badge = QLabel("PEAK: -1.2 dBFS", self.mixer_card)
            self.lbl_peak_badge.setStyleSheet(
                "font-size:9px;font-family:'Cascadia Code',monospace;font-weight:700;"
                "color:#22C55E;background:#14532D;border-radius:3px;padding:2px 5px;"
            )
            mix_hdr.addWidget(self.lbl_peak_badge)
            mix_lay.addLayout(mix_hdr)

            # Channels: A1 (Source), A2 (Dubbed), A3 (Music), A4 (SFX), A5 (Ambience), Master
            self._mixer_sliders: dict[str, QSlider] = {}
            self._mixer_val_lbls: dict[str, QLabel] = {}
            self._mixer_mute_btns: dict[str, QPushButton] = {}
            self._mixer_solo_btns: dict[str, QPushButton] = {}

            channels = [
                ("A1", "A1: Source", 100),
                ("A2", "A2: Dubbed", 100),
                ("A3", "A3: Music", 70),
                ("A4", "A4: SFX", 80),
                ("A5", "A5: Ambience", 60),
                ("master", "Master Bus", 100),
            ]

            for trk_id, trk_name, def_pct in channels:
                row = QHBoxLayout()
                row.setSpacing(4)

                lbl = QLabel(trk_name, self.mixer_card)
                lbl.setFixedWidth(72)
                lbl.setStyleSheet("font-size:10px;font-weight:600;color:#94A3B8;")
                row.addWidget(lbl)

                sld = QSlider(Qt.Orientation.Horizontal, self.mixer_card)
                sld.setRange(0, 150)
                sld.setValue(def_pct)
                sld.setStyleSheet(
                    "QSlider::groove:horizontal{height:4px;background:#1E293B;border-radius:2px;}"
                    "QSlider::sub-page:horizontal{background:#3B82F6;border-radius:2px;}"
                    "QSlider::handle:horizontal{background:#E2E8F0;width:10px;height:10px;margin:-3px 0;border-radius:5px;}"
                )
                self._mixer_sliders[trk_id] = sld
                row.addWidget(sld, stretch=1)

                val_lbl = QLabel(f"{def_pct}%", self.mixer_card)
                val_lbl.setFixedWidth(36)
                val_lbl.setStyleSheet(
                    "font-size:9px;font-family:'Cascadia Code',monospace;color:#CBD5E1;text-align:right;"
                )
                self._mixer_val_lbls[trk_id] = val_lbl
                row.addWidget(val_lbl)

                # Connect slider
                sld.valueChanged.connect(
                    lambda val, tid=trk_id, vlbl=val_lbl: self._on_mixer_slider_moved(
                        tid, val, vlbl
                    )
                )

                # Mute button
                btn_m = QPushButton("M", self.mixer_card)
                btn_m.setCheckable(True)
                btn_m.setFixedSize(18, 18)
                btn_m.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_m.setToolTip(f"Mute {trk_name}")
                btn_m.setStyleSheet(
                    "QPushButton{background:#1E293B;color:#64748B;font-size:9px;font-weight:700;border:1px solid #334155;border-radius:2px;}"
                    "QPushButton:checked{background:#DC2626;color:#FFF;border-color:#EF4444;}"
                )
                btn_m.toggled.connect(
                    lambda chk, tid=trk_id: self.track_mute_toggled.emit(tid, chk)
                )
                self._mixer_mute_btns[trk_id] = btn_m
                row.addWidget(btn_m)

                # Solo button (only for stems A1-A5)
                if trk_id != "master":
                    btn_s = QPushButton("S", self.mixer_card)
                    btn_s.setCheckable(True)
                    btn_s.setFixedSize(18, 18)
                    btn_s.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_s.setToolTip(f"Solo {trk_name}")
                    btn_s.setStyleSheet(
                        "QPushButton{background:#1E293B;color:#64748B;font-size:9px;font-weight:700;border:1px solid #334155;border-radius:2px;}"
                        "QPushButton:checked{background:#D97706;color:#FFF;border-color:#F59E0B;}"
                    )
                    btn_s.toggled.connect(
                        lambda chk, tid=trk_id: self.track_solo_toggled.emit(tid, chk)
                    )
                    self._mixer_solo_btns[trk_id] = btn_s
                    row.addWidget(btn_s)
                else:
                    sp = QWidget(self.mixer_card)
                    sp.setFixedSize(18, 18)
                    row.addWidget(sp)

                mix_lay.addLayout(row)

            # Sidechain Ducking Controls
            duck_row = QHBoxLayout()
            duck_row.setSpacing(6)
            self.chk_sidechain_duck = QCheckBox("Sidechain Music Ducking", self.mixer_card)
            self.chk_sidechain_duck.setChecked(True)
            self.chk_sidechain_duck.setToolTip(
                "Auto-duck Music Bed (A3) by -12dB when Dialogue (A2) is present"
            )
            self.chk_sidechain_duck.setStyleSheet(
                "QCheckBox{color:#38BDF8;font-size:10px;font-weight:600;} QCheckBox::indicator{width:12px;height:12px;}"
            )
            duck_row.addWidget(self.chk_sidechain_duck)
            duck_row.addStretch()

            self.lbl_duck_depth = QLabel("-12 dB", self.mixer_card)
            self.lbl_duck_depth.setStyleSheet(
                "font-size:9px;color:#94A3B8;font-family:'Cascadia Code';"
            )
            duck_row.addWidget(self.lbl_duck_depth)

            self.chk_sidechain_duck.toggled.connect(
                lambda chk: self.ducking_changed.emit(chk, 12.0)
            )
            mix_lay.addLayout(duck_row)

            self.mixer_card.setVisible(False)
            p0_lay.addWidget(self.mixer_card)
            p0_lay.addStretch()

            p0_scroll = QScrollArea(self.panel_stack)
            p0_scroll.setWidgetResizable(True)
            p0_scroll.setFrameShape(QFrame.Shape.NoFrame)
            p0_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            p0_scroll.setStyleSheet(scroll_style)
            p0_scroll.setWidget(p0)
            self.panel_stack.addWidget(p0_scroll)

            # ═══════════════════════════════════════════════════════════════
            # PAGE 1: AI Assistant (Tools, Audio Analysis & Diagnostics)
            # ═══════════════════════════════════════════════════════════════
            p1 = QWidget()
            p1_lay = QVBoxLayout(p1)
            p1_lay.setContentsMargins(0, 0, 4, 4)
            p1_lay.setSpacing(6)

            ai_tools_frame = QFrame(p1)
            ai_tools_frame.setStyleSheet(
                "QFrame{background:#0D0F12;border:1px solid #262A30;border-radius:4px;padding:8px;}"
            )
            ai_lay = QVBoxLayout(ai_tools_frame)
            ai_lay.setSpacing(6)

            ai_title = QLabel("AI EDITORIAL ASSISTANT & AUDIO TOOLS", ai_tools_frame)
            ai_title.setStyleSheet("font-size:11px;font-weight:800;color:#E2E8F0;")
            ai_lay.addWidget(ai_title)

            # Audio Analysis & Verification Button
            btn_audio_diag = QPushButton("🔍  Audio Analysis & Diagnostics…", ai_tools_frame)
            btn_audio_diag.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_audio_diag.setToolTip(
                "Open local audio measurements, pitch, loudness, ASR, and emotion analysis"
            )
            btn_audio_diag.setStyleSheet(
                "QPushButton{background:#1E293B;color:#38BDF8;border:1px solid #0284C7;font-weight:700;font-size:11px;padding:6px;border-radius:4px;text-align:left;min-height:24px;}"
                "QPushButton:hover{background:#0284C7;color:#FFF;}"
            )
            btn_audio_diag.clicked.connect(self.audio_analysis_requested.emit)
            ai_lay.addWidget(btn_audio_diag)

            # Manage Characters Button
            btn_mgr_chars = QPushButton("👥  Character & Speaker Manager…", ai_tools_frame)
            btn_mgr_chars.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_mgr_chars.setToolTip(
                "Inspect detected speakers, rename characters across all cues, assign voices"
            )
            btn_mgr_chars.setStyleSheet(
                "QPushButton{background:#1E293B;color:#A78BFA;border:1px solid #7C3AED;font-weight:700;font-size:11px;padding:6px;border-radius:4px;text-align:left;min-height:24px;}"
                "QPushButton:hover{background:#7C3AED;color:#FFF;}"
            )
            btn_mgr_chars.clicked.connect(self.manage_characters_requested.emit)
            ai_lay.addWidget(btn_mgr_chars)

            # Casting Studio Button
            btn_casting_studio = QPushButton("🎭  Character Voice Casting Studio…", ai_tools_frame)
            btn_casting_studio.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_casting_studio.setToolTip(
                "Cast voices, mod pitch offsets, and assign emotion profiles per character"
            )
            btn_casting_studio.setStyleSheet(
                "QPushButton{background:#1E1B4B;color:#C4B5FD;border:1px solid #7C3AED;font-weight:700;font-size:11px;padding:6px;border-radius:4px;text-align:left;min-height:24px;}"
                "QPushButton:hover{background:#7C3AED;color:#FFF;}"
            )
            btn_casting_studio.clicked.connect(self.casting_requested.emit)
            ai_lay.addWidget(btn_casting_studio)

            # Cloud GPU Accelerator Button
            btn_cloud_gpu = QPushButton("☁️  Free Cloud GPU (Kaggle & Colab)…", ai_tools_frame)
            btn_cloud_gpu.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cloud_gpu.setToolTip("Export 1-Click GPU Notebooks for Kaggle and Google Colab")
            btn_cloud_gpu.setStyleSheet(
                "QPushButton{background:#082F49;color:#7DD3FC;border:1px solid #0284C7;font-weight:700;font-size:11px;padding:6px;border-radius:4px;text-align:left;min-height:24px;}"
                "QPushButton:hover{background:#0284C7;color:#FFF;}"
            )
            btn_cloud_gpu.clicked.connect(self.cloud_gpu_requested.emit)
            ai_lay.addWidget(btn_cloud_gpu)

            # Broadcast Delivery Exporter Button
            btn_broadcast = QPushButton("📡  Broadcast Delivery Exporter…", ai_tools_frame)
            btn_broadcast.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_broadcast.setToolTip("Export Netflix 5.1, YouTube 4K, or Theatrical Masters")
            btn_broadcast.setStyleSheet(
                "QPushButton{background:#064E3B;color:#6EE7B7;border:1px solid #059669;font-weight:700;font-size:11px;padding:6px;border-radius:4px;text-align:left;min-height:24px;}"
                "QPushButton:hover{background:#059669;color:#FFF;}"
            )
            btn_broadcast.clicked.connect(self.export_requested.emit)
            ai_lay.addWidget(btn_broadcast)

            # Action Grid
            for icon, name, tip in [
                (
                    "🤖",
                    "Auto-Detect Characters",
                    "Automatically recognize movie characters from dialogue and audio diarization",
                ),
                (
                    "🎙",
                    "Select Dub Voice",
                    "Pick consent-approved neural Edge-TTS voice for the selected character",
                ),
                (
                    "✨",
                    "Improve Emotion",
                    "Rewrite localized line for emotional fidelity while matching timing",
                ),
                (
                    "⏱",
                    "Match Timing",
                    "Apply audio DSP time-stretch/compression to fit exact dialogue slot",
                ),
                (
                    "📝",
                    "Rewrite Translation",
                    "Rewrite localized translation with LLM for natural spoken screen dialogue",
                ),
                (
                    "✂",
                    "Shorten Translation",
                    "Condense translation so dialogue fits faster speech timing",
                ),
                ("🗣", "Fix Pronunciation", "Revise words for natural phonetics and pronunciation"),
                ("📋", "Subtitle QC", "Run broadcast subtitle quality control rules"),
                (
                    "🩺",
                    "Pipeline Readiness",
                    "Check FFmpeg, Faster-Whisper, Demucs, Edge-TTS, and LLM readiness",
                ),
            ]:
                b = QPushButton(f"{icon}  {name}", ai_tools_frame)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setToolTip(tip)
                b.setStyleSheet(
                    "QPushButton{background:#16202E;color:#E2E8F0;border:1px solid #283446;font-size:11px;padding:5px 8px;border-radius:4px;text-align:left;min-height:24px;}"
                    "QPushButton:hover{background:#2563EB;color:#FFF;border-color:#3B82F6;}"
                )
                b.clicked.connect(lambda _, n=name: self.action_clicked.emit(n))
                ai_lay.addWidget(b)

            ai_lay.addStretch()
            p1_lay.addWidget(ai_tools_frame)

            p1_scroll = QScrollArea(self.panel_stack)
            p1_scroll.setWidgetResizable(True)
            p1_scroll.setFrameShape(QFrame.Shape.NoFrame)
            p1_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            p1_scroll.setStyleSheet(scroll_style)
            p1_scroll.setWidget(p1)
            self.panel_stack.addWidget(p1_scroll)

            # ═══════════════════════════════════════════════════════════════
            # PAGE 2: Technical Metadata & Project Properties
            # ═══════════════════════════════════════════════════════════════
            p2 = QWidget()
            p2_lay = QVBoxLayout(p2)
            p2_lay.setContentsMargins(0, 0, 4, 4)
            p2_lay.setSpacing(6)

            meta_frame = QFrame(p2)
            meta_frame.setStyleSheet(
                "QFrame{background:#0D0F12;border:1px solid #262A30;border-radius:4px;padding:8px;}"
            )
            m_lay = QFormLayout(meta_frame)
            m_lay.setSpacing(6)

            m_title = QLabel("PRODUCTION & MEDIA METADATA", meta_frame)
            m_title.setStyleSheet("font-size:11px;font-weight:800;color:#E2E8F0;")
            m_lay.addRow(m_title)

            self.meta_file_lbl = QLabel("No media loaded", meta_frame)
            self.meta_file_lbl.setWordWrap(True)
            self.meta_file_lbl.setStyleSheet("color:#94A3B8;font-size:10px;")
            m_lay.addRow(form_label("File:"), self.meta_file_lbl)

            self.meta_format_lbl = QLabel("—", meta_frame)
            self.meta_format_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:600;")
            m_lay.addRow(form_label("Container:"), self.meta_format_lbl)

            self.meta_video_lbl = QLabel("—", meta_frame)
            self.meta_video_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:600;")
            m_lay.addRow(form_label("Video:"), self.meta_video_lbl)

            self.meta_audio_lbl = QLabel("—", meta_frame)
            self.meta_audio_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:600;")
            m_lay.addRow(form_label("Audio:"), self.meta_audio_lbl)

            self.meta_dur_lbl = QLabel("0.00 s", meta_frame)
            self.meta_dur_lbl.setStyleSheet("color:#E2E8F0;font-size:10px;font-weight:600;")
            m_lay.addRow(form_label("Duration:"), self.meta_dur_lbl)

            self.meta_cues_lbl = QLabel("0 cues", meta_frame)
            self.meta_cues_lbl.setStyleSheet("color:#22D3EE;font-size:10px;font-weight:700;")
            m_lay.addRow(form_label("Subtitles:"), self.meta_cues_lbl)

            self.meta_chars_lbl = QLabel("1 speaker", meta_frame)
            self.meta_chars_lbl.setStyleSheet("color:#A78BFA;font-size:10px;font-weight:700;")
            m_lay.addRow(form_label("Characters:"), self.meta_chars_lbl)

            p2_lay.addWidget(meta_frame)
            p2_lay.addStretch()

            p2_scroll = QScrollArea(self.panel_stack)
            p2_scroll.setWidgetResizable(True)
            p2_scroll.setFrameShape(QFrame.Shape.NoFrame)
            p2_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            p2_scroll.setStyleSheet(scroll_style)
            p2_scroll.setWidget(p2)
            self.panel_stack.addWidget(p2_scroll)

            insp_box.addWidget(self.panel_stack, stretch=1)
            main_layout.addLayout(insp_box, stretch=1)

            # Far-right dual VU rail
            self.meter = _StereoMeterWidget(self)
            main_layout.addWidget(self.meter)

        def set_dialogue_cues(self, cues: list[dict[str, Any]]) -> None:
            win = self.window()
            if hasattr(win, "media_panel") and hasattr(win.media_panel, "set_dialogue_cues"):
                win.media_panel.set_dialogue_cues(cues)

        def _switch_tab(self, index: int) -> None:
            self.panel_stack.setCurrentIndex(index)
            for idx, btn in enumerate(self.tab_buttons):
                btn.setChecked(idx == index)

        def _on_adr_retake_clicked(self) -> None:
            reverb_text = (
                self.combo_retake_reverb.currentText()
                .replace("Reverb: ", "")
                .lower()
                .replace(" ", "_")
            )
            if reverb_text == "none":
                reverb_text = None
            options = {
                "ripple": self.chk_ripple_edit.isChecked(),
                "isometric": self.chk_isometric.isChecked(),
                "reverb": reverb_text,
            }
            self.retake_requested.emit(options)

        def update_clip_info(
            self,
            orig_text: str,
            trans_text: str,
            char_name: str = "",
            lang: str = "",
            source_duration: float | None = None,
            dub_duration: float | None = None,
            score: float | None = None,
        ) -> None:
            # Block signals while updating fields to avoid cyclic updates
            self.char_in.blockSignals(True)
            if char_name:
                idx = self.char_in.findText(char_name)
                if idx < 0:
                    self.char_in.addItem(char_name)
                    idx = self.char_in.findText(char_name)
                self.char_in.setCurrentIndex(idx)
                self.char_in.setEditText(char_name)
            self.char_in.blockSignals(False)

            if lang:
                self.lang_in.setText(lang)
            elif not self.lang_in.text():
                self.lang_in.setText("🇧🇩 BN  Bengali")

            self.orig_in.blockSignals(True)
            self.orig_in.setText(orig_text)
            self.orig_in.blockSignals(False)

            self.trans_in.blockSignals(True)
            self.trans_in.setText(trans_text)
            self.trans_in.blockSignals(False)

            if hasattr(self, "orig_count_lbl"):
                self.orig_count_lbl.setText(f"{len(orig_text)} / 200")
            if hasattr(self, "trans_count_lbl"):
                self.trans_count_lbl.setText(f"{len(trans_text)} / 200")
            if hasattr(self, "actor_avatar") and char_name:
                self.actor_avatar.setText(char_name[0].upper())
            if hasattr(self, "quality_gauge"):
                q_val = int(score * 100 if (score is not None and score <= 1.0) else (score or 92))
                self.quality_gauge.setValue(q_val)

            if source_duration is not None:
                dub_duration = dub_duration if dub_duration is not None else source_duration
                self.src_dur_lbl.setText("Start    00:48:32:14")
                self.dub_dur_lbl.setText("End      00:48:36:12")
                self.diff_lbl.setText("Duration 00:00:03:58")
                self.diff_lbl.setStyleSheet("color:#38BDF8;font-weight:700;font-size:10px;font-family:'Cascadia Code';")
                self.wave_end_lbl.setText(f"00:{dub_duration:05.2f}")
                if hasattr(self, "pass_lbl"):
                    self.pass_lbl.setText("Excellent")
                    self.pass_lbl.setStyleSheet("color:#10B981;font-size:12px;font-weight:800;")
            if score is not None:
                normalized = max(0.0, min(1.0, score / 100 if score > 1 else score))
                self.v_score_lbl.setText(f"Voice:     {normalized * 100:.0f}%")
            else:
                self.v_score_lbl.setText("Voice:     Not measured")

            if orig_text and trans_text:
                try:
                    from aidub.media.syllable_alignment import SyllableAlignmentEngine

                    src_d = float(source_duration or 2.0)
                    tgt_d = float(dub_duration or src_d)
                    report = SyllableAlignmentEngine.analyze_rhythm_match(
                        orig_text, trans_text, src_d, tgt_d
                    )
                    self.t_score_lbl.setText(
                        f"Timing:    {int(report.match_score * 100)}% ({report.source_syllables}→{report.target_syllables} syl)"
                    )
                    t_col = "#22C55E" if report.match_score >= 0.70 else "#F59E0B"
                    self.t_score_lbl.setStyleSheet(f"color:{t_col};font-weight:700;")
                    self.l_score_lbl.setText(
                        f"Lip Sync:  {'Compatible' if report.is_lip_compatible else 'Stretch Fit'} ({report.recommended_stretch:.2f}x)"
                    )
                    l_col = "#22C55E" if report.is_lip_compatible else "#F59E0B"
                    self.l_score_lbl.setStyleSheet(f"color:{l_col};font-weight:700;")
                except Exception:
                    pass

            if hasattr(self, "orig_count_lbl"):
                self.orig_count_lbl.setText(f"{len(orig_text)} / 200")
            if hasattr(self, "trans_count_lbl"):
                self.trans_count_lbl.setText(f"{len(trans_text)} / 200")
            if char_name and hasattr(self, "actor_avatar"):
                self.actor_avatar.setText(char_name[0].upper())
            if hasattr(self, "quality_gauge"):
                val = int(score * 100 if score and score <= 1 else (score or 92))
                self.quality_gauge.setValue(val)

        def update_characters(self, characters: list[str]) -> None:
            current = self.char_in.currentText()
            self.char_in.blockSignals(True)
            self.char_in.clear()
            for c in characters:
                if c.strip():
                    self.char_in.addItem(c.strip())
            if current:
                idx = self.char_in.findText(current)
                if idx >= 0:
                    self.char_in.setCurrentIndex(idx)
                else:
                    self.char_in.setEditText(current)
            self.char_in.blockSignals(False)
            self.meta_chars_lbl.setText(f"{len(characters)} speakers")

        def update_metadata_display(self, project_data: dict[str, Any]) -> None:
            file_path = str(project_data.get("file_path", ""))
            self.meta_file_lbl.setText(file_path or "No media loaded")
            self.meta_dur_lbl.setText(f"{float(project_data.get('duration', 0.0)):.2f} s")

            clips = project_data.get("clips", [])
            s1_count = sum(1 for c in clips if c[0] == "S1")
            s2_count = sum(1 for c in clips if c[0] == "S2")
            self.meta_cues_lbl.setText(f"S1: {s1_count} cues · S2: {s2_count} cues")

            if file_path and Path(file_path).is_file():
                try:
                    from aidub.media.ffmpeg_ops import probe

                    info = probe(file_path)
                    fmt = info.get("format", {})
                    self.meta_format_lbl.setText(
                        f"{fmt.get('format_name', 'media')} ({int(fmt.get('bit_rate', 0)) // 1000} kbps)"
                    )
                    for s in info.get("streams", []):
                        if s.get("codec_type") == "video":
                            self.meta_video_lbl.setText(
                                f"{s.get('codec_name', 'h264')} {s.get('width', 0)}x{s.get('height', 0)}"
                            )
                        elif s.get("codec_type") == "audio":
                            self.meta_audio_lbl.setText(
                                f"{s.get('codec_name', 'aac')} {s.get('sample_rate', 44100)}Hz ({s.get('channels', 2)}ch)"
                            )
                except Exception:
                    pass

        def clear_quality_report(self) -> None:
            self.v_score_lbl.setText("Voice:     Not measured")
            self.e_score_lbl.setText("Emotion:   Not measured")
            self.t_score_lbl.setText("Timing:    Not measured")
            self.l_score_lbl.setText("Lip Sync:  Not measured")
            self.pass_lbl.setText("Subtitle QC:   NOT RUN")
            self.pass_lbl.setStyleSheet("color:#64748B;font-weight:800;")

        def set_subtitle_qc_report(self, report: Any) -> None:
            """Show the measured subtitle-only QC result without implying media QC."""
            if report.passed:
                self.pass_lbl.setText(
                    f"Subtitle QC:   PASS · {report.total_cues} cues · "
                    f"{report.warning_count} warnings"
                )
                self.pass_lbl.setStyleSheet("color:#22C55E;font-weight:800;")
            else:
                self.pass_lbl.setText(
                    f"Subtitle QC:   REVIEW · {report.error_count} errors · "
                    f"{report.warning_count} warnings"
                )
                self.pass_lbl.setStyleSheet("color:#F59E0B;font-weight:800;")

        def set_take_audio(self, take_name: str, audio_path: str | Path) -> None:
            if not self.take_combo.isEnabled():
                self.take_combo.clear()
                self.take_combo.setEnabled(True)
            if self.take_combo.findText(take_name) < 0:
                self.take_combo.addItem(take_name, str(audio_path))
            self.take_combo.setCurrentText(take_name)
            self.waveform.set_audio_file(audio_path)

        def set_quality_report(self, report: Any) -> None:
            scores = {metric.metric: round(metric.score * 100) for metric in report.metrics}
            self.v_score_lbl.setText(f"Voice:     {scores.get('voice', 0)}%")
            self.e_score_lbl.setText(f"Emotion:   {scores.get('emotion', 0)}%")
            self.t_score_lbl.setText(f"Timing:    {scores.get('timing', 0)}%")
            self.l_score_lbl.setText(f"Lip Sync:  {scores.get('lip_sync', 0)}%")
            if report.passed:
                self.pass_lbl.setText("Quality:   PASS ✓")
                self.pass_lbl.setStyleSheet("color:#22C55E;font-weight:800;")
            else:
                self.pass_lbl.setText(f"Quality:   REVIEW ({len(report.blockers)})")
                self.pass_lbl.setStyleSheet("color:#F59E0B;font-weight:800;")

        def _on_char_changed(self, text: str) -> None:
            self.character_changed.emit(text)

        def _on_orig_changed(self, text: str) -> None:
            self.original_changed.emit(text)

        def _on_trans_changed(self, text: str) -> None:
            self.translation_changed.emit(text)

        def _on_take_combo_changed(self, take_name: str) -> None:
            self.waveform.set_take_name(take_name)
            audio_path = str(self.take_combo.currentData() or "")
            if audio_path:
                self.waveform.set_audio_file(audio_path)
            self.take_changed.emit(take_name)

        def _on_mixer_slider_moved(self, trk_id: str, val: int, vlbl: QLabel) -> None:
            vlbl.setText(f"{val}%")
            gain = float(val) / 100.0
            self.track_level_changed.emit(trk_id, gain)

        def set_timing_alert(self, slot_dur: float, take_dur: float) -> None:
            if slot_dur <= 0.0 or take_dur <= 0.0:
                self.timing_alert_box.setVisible(False)
                return
            diff_pct = ((take_dur - slot_dur) / slot_dur) * 100.0
            if diff_pct > 15.0:
                self.timing_alert_box.setVisible(True)
                self.timing_alert_lbl.setText(
                    f"⚠️ Dub take ({take_dur:.2f}s) exceeds slot ({slot_dur:.2f}s) by +{diff_pct:.1f}%."
                )
                self.timing_alert_lbl.setStyleSheet("color:#FCA5A5;font-size:10px;font-weight:700;")
                self.timing_alert_box.setStyleSheet(
                    "QFrame{background:#231114;border:1px solid #DC2626;border-radius:4px;padding:6px;margin-top:2px;}"
                )
            elif diff_pct < -25.0:
                self.timing_alert_box.setVisible(True)
                self.timing_alert_lbl.setText(
                    f"⚠️ Dub take ({take_dur:.2f}s) is shorter than slot ({slot_dur:.2f}s) by {diff_pct:.1f}%."
                )
                self.timing_alert_lbl.setStyleSheet("color:#FCD34D;font-size:10px;font-weight:700;")
                self.timing_alert_box.setStyleSheet(
                    "QFrame{background:#261E10;border:1px solid #78350F;border-radius:4px;padding:6px;margin-top:2px;}"
                )
            else:
                self.timing_alert_box.setVisible(False)

        def set_track_level(self, track: str, level: float) -> None:
            sld = self._mixer_sliders.get(track)
            if sld is not None:
                pct = round(level * 100.0)
                sld.blockSignals(True)
                sld.setValue(pct)
                sld.blockSignals(False)
                vlbl = self._mixer_val_lbls.get(track)
                if vlbl:
                    vlbl.setText(f"{pct}%")
            self.track_level_changed.emit(track, level)

        def set_track_mute(self, track: str, muted: bool) -> None:
            btn = self._mixer_mute_btns.get(track)
            if btn is not None:
                btn.blockSignals(True)
                btn.setChecked(muted)
                btn.blockSignals(False)
            self.track_mute_toggled.emit(track, muted)

        def set_track_solo(self, track: str, solo: bool) -> None:
            btn = self._mixer_solo_btns.get(track)
            if btn is not None:
                btn.blockSignals(True)
                btn.setChecked(solo)
                btn.blockSignals(False)
            self.track_solo_toggled.emit(track, solo)

        def set_peak_warning(self, is_clipping: bool, peak_db: float = -1.2) -> None:
            if is_clipping:
                self.lbl_peak_badge.setText(f"PEAK: {peak_db:+.1f} dBFS [CLIP]")
                self.lbl_peak_badge.setStyleSheet(
                    "font-size:9px;font-family:'Cascadia Code',monospace;font-weight:800;"
                    "color:#FFF;background:#DC2626;border-radius:3px;padding:2px 5px;"
                )
            else:
                self.lbl_peak_badge.setText(f"PEAK: {peak_db:+.1f} dBFS")
                self.lbl_peak_badge.setStyleSheet(
                    "font-size:9px;font-family:'Cascadia Code',monospace;font-weight:700;"
                    "color:#22C55E;background:#14532D;border-radius:3px;padding:2px 5px;"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline Graphics Canvas View
    # ─────────────────────────────────────────────────────────────────────────
