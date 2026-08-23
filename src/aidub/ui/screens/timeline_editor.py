"""
Full NLE Timeline Editor Screen — Real Dynamic Project Data Engine.

Matches reference design pixel-for-pixel with zero hardcoded static locks:
  • Top Workspace Tabs Bar (Learning, Assembly, Editing, Dubbing [active], Color, Audio, Graphics, Libraries)
  • 3-Column Upper Panel:
      - Left Column: Project Media Browser with dynamic file tree (01_Source, 02_Generated, 03_Assets, 04_Proxies, 05_Stems)
      - Center Column: Program Video Monitor with live playhead, transport controls, cyan timecode overlay, resolution dropdowns
      - Right Column: Dialogue Inspector with Character, Original/Translation text, Timing & Scores cards, Take Selector, Waveform & dual vertical VU meter (-6 to -54 dB)
  • Lower Multi-track Timeline Panel (10 tracks V1-V3, A1-A5, S1-S2) with dynamic clip blocks, Bengali subtitle blocks, scrubbing playhead
  • Floating AI Actions Right Panel on Timeline (11 AI workflow commands)
  • Bottom Editing Status Dock & Tool Palette (Pointer, Razor, Text, Hand, Zoom, Slip/Slide)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidub.application.agentic_studio import (
    AgenticStudioState,
    AutomationStage,
    StageStatus,
    StudioSessionStore,
    create_automation_plan,
)

try:
    from PySide6.QtCore import (
        QLineF,
        QPointF,
        QRectF,
        QStandardPaths,
        Qt,
        QTimer,
        QUrl,
        Signal,
    )
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QPainter,
        QPen,
        QPixmap,
        QWheelEvent,
    )
    from PySide6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QSplitter,
        QStackedWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    _QT = True
except ImportError:
    _QT = False

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as _W

# ────────────────────────────────────────────────────────────────────────────
# Timeline Constants & Presets
# ────────────────────────────────────────────────────────────────────────────
TRACK_HEIGHT = 34
TRACK_HEADER_WIDTH = 250
RULER_HEIGHT = 30
MIN_CLIP_WIDTH = 6
PX_PER_SEC_DEFAULT = 120.0

_TRACK_DEFS = [
    ("V3", "Video",        "#3B82F6", "video"),
    ("V2", "Lip Sync",     "#8B5CF6", "video"),
    ("V1", "Source Video", "#3B82F6", "video"),
    ("A1", "Source Audio", "#10B981", "audio"),
    ("A2", "Dubbed Voice", "#8B5CF6", "audio"),
    ("A3", "Music",        "#06B6D4", "audio"),
    ("A4", "SFX",          "#F97316", "audio"),
    ("A5", "Ambience",     "#EAB308", "audio"),
    ("S1", "Source Subs",  "#2563EB", "subtitle"),
    ("S2", "Target Subs",  "#1E3A8A", "subtitle"),
]


def _format_tc(sec: float) -> str:
    """Convert floating seconds to an absolute zero-based studio timecode."""
    total_sec = max(0.0, sec)
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    s = int(total_sec % 60)
    ms = int((total_sec - int(total_sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}:{ms:03d}"


if _QT:
    class _ProductionStageBar(QFrame):
        """Live production graph summary for the single Studio workspace."""

        _GROUPS = (
            ("MEDIA", (AutomationStage.INGEST, AutomationStage.AUDIO_SEPARATION)),
            (
                "ANALYSIS",
                (AutomationStage.SPEAKER_ANALYSIS, AutomationStage.TRANSCRIPTION),
            ),
            ("TRANSLATION", (AutomationStage.TRANSLATION,)),
            (
                "VOICE",
                (AutomationStage.VOICE_CASTING, AutomationStage.SYNTHESIS),
            ),
            ("TIMING", (AutomationStage.TIMING,)),
            ("LIP SYNC", (AutomationStage.LIP_SYNC,)),
            ("MIX", (AutomationStage.MIX,)),
            (
                "DELIVERY",
                (AutomationStage.QUALITY_CONTROL, AutomationStage.MASTER_EXPORT),
            ),
        )

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setFixedHeight(39)
            self.setStyleSheet(
                "QFrame{background:#0D1118;border-bottom:1px solid #1E2838;}"
            )
            layout = QHBoxLayout(self)
            layout.setContentsMargins(300, 0, 300, 0)
            layout.setSpacing(12)
            self._labels: dict[str, QLabel] = {}
            for label, _stages in self._GROUPS:
                widget = QLabel(label, self)
                widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(widget, stretch=1)
                self._labels[label] = widget

        def set_state(self, state: AgenticStudioState) -> None:
            for label, stages in self._GROUPS:
                statuses = {state.stage(stage).status for stage in stages}
                if StageStatus.FAILED in statuses:
                    color, border = "#EF4444", "#EF4444"
                elif StageStatus.RUNNING in statuses:
                    color, border = "#22D3EE", "#22D3EE"
                elif statuses <= {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                    color, border = "#22C55E", "transparent"
                else:
                    color, border = "#8C9BAE", "transparent"
                self._labels[label].setStyleSheet(
                    f"color:{color};font-size:10px;font-weight:700;"
                    f"border-bottom:2px solid {border};padding:7px 4px 5px 4px;"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Left Column: Project Media Browser
    # ─────────────────────────────────────────────────────────────────────────
    class _MediaBrowserPanel(QFrame):
        media_selected = Signal(str)

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self._source_path = ""
            self.setStyleSheet("background:#111722;border-right:1px solid #1E2838;")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)

            hdr_layout = QHBoxLayout()
            self.proj_tab = QLabel("NO PROJECT", self)
            self.proj_tab.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #F7F9FC; background: #1C2636;"
                "padding: 4px 8px; border-radius: 4px;"
            )
            hdr_layout.addWidget(self.proj_tab)

            mb_tab = QLabel("Media", self)
            mb_tab.setStyleSheet("font-size: 11px; color: #64748B; padding: 4px 8px;")
            hdr_layout.addWidget(mb_tab)
            hdr_layout.addStretch()
            layout.addLayout(hdr_layout)

            self.proj_file_lbl = QLabel("Import a movie to begin", self)
            self.proj_file_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8C9BAE;")
            layout.addWidget(self.proj_file_lbl)

            # Search & Count bar
            search_row = QHBoxLayout()
            search_row.setSpacing(6)

            self.search_in = QLineEdit(self)
            self.search_in.setPlaceholderText("🔍 Search media…")
            self.search_in.setStyleSheet(
                "QLineEdit{background:#0D131F;color:#F7F9FC;border:1px solid #1E2838;padding:4px 8px;border-radius:4px;font-size:11px;}"
            )
            self.search_in.textChanged.connect(self._on_search_text_changed)
            search_row.addWidget(self.search_in, stretch=1)

            self.count_lbl = QLabel("0", self)
            self.count_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #64748B; background: #16202E; padding: 3px 6px; border-radius: 3px;"
            )
            search_row.addWidget(self.count_lbl)

            gear_btn = QPushButton("⚙", self)
            gear_btn.setFixedSize(24, 24)
            gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            gear_btn.setStyleSheet(
                "QPushButton{background:#16202E;color:#8C9BAE;border:none;border-radius:3px;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            gear_btn.clicked.connect(self._on_gear_clicked)
            search_row.addWidget(gear_btn)
            layout.addLayout(search_row)

            # Folder Tree
            self.tree = QTreeWidget(self)
            self.tree.setHeaderLabels(["Name", "Type"])
            self.tree.header().setStyleSheet(
                "QHeaderView::section{background:#0D131F;color:#64748B;font-size:10px;font-weight:700;border:none;padding:3px;}"
            )
            self.tree.setStyleSheet(
                "QTreeWidget{background:#0D131F;border:1px solid #1E2838;border-radius:6px;color:#F7F9FC;font-size:11px;}"
                "QTreeWidget::item{padding:3px;}"
                "QTreeWidget::item:selected{background:#1E3A5F;color:#F7F9FC;}"
            )
            self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

            self.populate_tree()
            layout.addWidget(self.tree, stretch=1)

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
                empty_item = self._item(
                    self.tree,
                    "＋  Import source movie…",
                    "Action",
                    "studio://import",
                )
                empty_item.setToolTip(0, "Choose a local movie file")
                self.count_lbl.setText("0")
                return

            source_bin = self._item(self.tree, "📁  01_Source")
            self._item(source_bin, f"🎬  {movie_name}", "Video", source_path)

            if source.parent.is_dir():
                sidecars = sorted(
                    item
                    for item in source.parent.iterdir()
                    if item.is_file()
                    and item.suffix.lower()
                    in {".srt", ".vtt", ".ass", ".wav", ".flac", ".mp3"}
                )[:12]
                for sidecar in sidecars:
                    is_subtitle = sidecar.suffix.lower() in {".srt", ".vtt", ".ass"}
                    media_type = "Subtitle" if is_subtitle else "Audio"
                    icon = "📄" if is_subtitle else "🎵"
                    self._item(
                        source_bin,
                        f"{icon}  {sidecar.name}",
                        media_type,
                        str(sidecar),
                    )
            generated_bin = self._item(self.tree, "📁  02_Generated")
            if generated_paths:
                for generated in generated_paths:
                    generated_path = Path(generated)
                    if generated_path.name:
                        media_type = (
                            "Video"
                            if generated_path.suffix.lower() in {".mp4", ".mkv", ".mov"}
                            else "Artifact"
                        )
                        self._item(
                            generated_bin,
                            f"⚡  {generated_path.name}",
                            media_type,
                            str(generated_path),
                        )
            self.tree.expandAll()
            root = self.tree.invisibleRootItem()
            count = sum(1 + root.child(index).childCount() for index in range(root.childCount()))
            self.count_lbl.setText(str(count))

        def set_project_name(
            self,
            name: str,
            movie_name: str = "",
            source_path: str = "",
            generated_paths: tuple[str, ...] = (),
        ) -> None:
            self.proj_tab.setText(name.upper())
            self.proj_file_lbl.setText(source_path or "No source media loaded")
            self.populate_tree(movie_name, source_path, generated_paths)

        def _on_search_text_changed(self, text: str) -> None:
            text = text.lower()
            if not text:
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    item.setHidden(False)
                    for j in range(item.childCount()):
                        item.child(j).setHidden(False)
                return

            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                match_parent = text in item.text(0).lower()
                any_child_match = False
                for j in range(item.childCount()):
                    child = item.child(j)
                    match_child = text in child.text(0).lower()
                    child.setHidden(not (match_child or match_parent))
                    if match_child:
                        any_child_match = True
                item.setHidden(not (match_parent or any_child_match))

        def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int) -> None:
            del col
            path = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if path == "studio://import":
                self._import_media()
                return
            name = (
                item.text(0)
                .replace("📁 ", "")
                .replace("🎬 ", "")
                .replace("📄 ", "")
                .replace("🎵 ", "")
                .replace("⚡ ", "")
                .strip()
            )
            self.media_selected.emit(path or name)

        def _on_gear_clicked(self) -> None:
            menu = QMenu(self)
            import_action = menu.addAction("Import Media Files…")
            import_action.triggered.connect(self._import_media)
            menu.exec(self.mapToGlobal(QPointF(0, 24).toPoint()))

        def _import_media(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Media",
                str(Path(self._source_path).parent) if self._source_path else "",
                (
                    "Production Media (*.mkv *.mp4 *.mov *.avi *.wav *.flac *.mp3 "
                    "*.srt *.vtt *.ass);;All Files (*)"
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
        duration_resolved = Signal(float)
        first_frame_decoded = Signal(object)

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet("background:#080B10;border-right:1px solid #1E2838;")

            self._playhead_sec = 0.0
            self._is_playing = False
            self._mark_in_sec = 0.0
            self._mark_out_sec = 0.0
            self._loop_enabled = False
            self._max_duration_sec = 0.0
            self._media_path = ""
            self._player: Any | None = None
            self._audio_output: Any | None = None
            self._video_widget: QWidget | None = None
            self._video_sink: Any | None = None
            self._last_video_image: Any | None = None
            self._priming_video = False
            self._prime_restore_muted = False
            self._prime_target_ms = 0

            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)

            # Header Tabs matching Image 1
            hdr = QHBoxLayout()
            self.prog_title_lbl = QLabel("Program Monitor", self)
            self.prog_title_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #F7F9FC; background: #1C2636; padding: 4px 8px; border-radius: 4px;"
            )
            hdr.addWidget(self.prog_title_lbl)

            self.source_lbl = QLabel("Source: none", self)
            self.source_lbl.setStyleSheet("font-size: 11px; color: #64748B; padding: 4px 8px;")
            hdr.addWidget(self.source_lbl)

            hdr.addStretch()
            layout.addLayout(hdr)

            # Video Canvas Frame
            video_frame = QFrame(self)
            video_frame.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #151D2A, stop:1 #090E17);"
                "border: 1px solid #1E2838; border-radius: 6px;"
            )
            vf_lay = QVBoxLayout(video_frame)
            vf_lay.setContentsMargins(12, 12, 12, 12)

            # Top overlay inside video
            v_top = QHBoxLayout()
            self.tc_overlay = QLabel("00:00:00:000", video_frame)
            self.tc_overlay.setStyleSheet(
                "font-family:'Cascadia Code'; font-size:13px; font-weight:700; color:#22D3EE;"
                "background:rgba(8,11,16,0.85); padding:3px 8px; border-radius:4px;"
            )
            v_top.addWidget(self.tc_overlay)

            v_top.addStretch()

            fit_combo = QComboBox(video_frame)
            fit_combo.addItems(["Fit", "50%", "100%", "200%"])
            fit_combo.setStyleSheet(
                "QComboBox{background:rgba(8,11,16,0.85);color:#F7F9FC;border:none;padding:2px 6px;border-radius:4px;font-size:11px;}"
            )
            v_top.addWidget(fit_combo)

            self.dur_overlay = QLabel("00:00:00:000", video_frame)
            self.dur_overlay.setStyleSheet(
                "font-family:'Cascadia Code'; font-size:12px; color:#8C9BAE;"
                "background:rgba(8,11,16,0.85); padding:3px 8px; border-radius:4px;"
            )
            v_top.addWidget(self.dur_overlay)
            vf_lay.addLayout(v_top)

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

            self.stark_quote = QLabel("Import a movie to activate playback and the timeline.", placeholder)
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

            try:
                from PySide6.QtMultimedia import (  # noqa: PLC0415
                    QAudioOutput,
                    QMediaPlayer,
                    QVideoSink,
                )

                self._video_widget = QLabel(self.media_stack)
                self._video_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._video_widget.setStyleSheet("background:#000;border:none;")
                self.media_stack.addWidget(self._video_widget)
                self._audio_output = QAudioOutput(self)
                self._audio_output.setVolume(0.82)
                self._player = QMediaPlayer(self)
                self._player.setAudioOutput(self._audio_output)
                self._video_sink = QVideoSink(self)
                self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)
                self._player.setVideoSink(self._video_sink)
                self._player.positionChanged.connect(self._on_player_position_changed)
                self._player.durationChanged.connect(self._on_player_duration_changed)
                self._player.mediaStatusChanged.connect(self._on_media_status_changed)
                self._player.errorOccurred.connect(self._on_player_error)
            except (ImportError, RuntimeError):
                self._player = None
                self._video_widget = None

            vf_lay.addWidget(self.media_stack, stretch=1)

            layout.addWidget(video_frame, stretch=1)

            # Transport controls operate directly on QMediaPlayer.
            t_bar = QHBoxLayout()
            t_bar.setSpacing(4)
            t_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)

            ctrl_btns = [
                ("{", "Mark In", self._on_mark_in),
                ("}", "Mark Out", self._on_mark_out),
                ("|←", "Go to In", self._on_go_to_in),
                ("←", "Step Back", self._on_step_back),
                ("▶", "Play / Pause", self._toggle_play),
                ("→", "Step Forward", self._on_step_forward),
                ("→|", "Go to Out", self._on_go_to_out),
                ("📷", "Export Snapshot", self._on_export_snapshot),
                ("🔁", "Loop", self._toggle_loop),
                ("🔊", "Mute / Unmute", self._toggle_mute),
            ]

            self.play_btn = None
            for sym, tip, slot in ctrl_btns:
                b = QPushButton(sym, self)
                b.setFixedSize(28, 28)
                b.setToolTip(tip)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                is_play = (sym == "▶")
                if is_play:
                    self.play_btn = b
                b.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {'#2563EB' if is_play else '#141C2B'};"
                    f"  color: {'#FFF' if is_play else '#A9B2C3'};"
                    f"  border: 1px solid {'#3B82F6' if is_play else '#222D3E'};"
                    f"  border-radius: 4px; font-size: 11px; font-weight: 700;"
                    f"}}"
                    f"QPushButton:hover {{ background: #3B82F6; color: #FFF; }}"
                )
                b.clicked.connect(slot)
                t_bar.addWidget(b)

            layout.addLayout(t_bar)

        def set_project_info(
            self,
            name: str,
            movie_name: str,
            char_name: str,
            quote: str,
            dur_sec: float,
            media_path: str = "",
        ) -> None:
            self.prog_title_lbl.setText(f"Program: {name}")
            self.source_lbl.setText(f"Source: {movie_name}")
            del char_name, quote
            self._max_duration_sec = dur_sec
            self._mark_out_sec = dur_sec
            self.dur_overlay.setText(_format_tc(dur_sec))
            if media_path:
                self.load_media(media_path)

        def load_media(self, media_path: str) -> None:
            """Load a local video into Qt Multimedia without blocking the UI thread."""

            path = Path(media_path)
            if self._player is None or self._video_widget is None or not path.is_file():
                self._media_path = ""
                self.media_stack.setCurrentWidget(self._placeholder_widget)
                return
            self._media_path = str(path)
            self._last_video_image = None
            self._priming_video = False
            if isinstance(self._video_widget, QLabel):
                self._video_widget.clear()
            self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            self.media_stack.setCurrentWidget(self._video_widget)

        def _on_media_status_changed(self, status: object) -> None:
            if self._player is None or not self._media_path or self._last_video_image is not None:
                return
            from PySide6.QtMultimedia import QMediaPlayer  # noqa: PLC0415

            ready_statuses = {
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            }
            if status in ready_statuses and not self._priming_video:
                self._priming_video = True
                self._prime_target_ms = min(
                    5_000,
                    max(0, self._player.duration() - 1),
                )
                if self._audio_output is not None:
                    self._prime_restore_muted = self._audio_output.isMuted()
                    self._audio_output.setMuted(True)
                self._player.setPosition(self._prime_target_ms)
                self._player.play()

        def _on_player_error(self, _error: object, error_string: str) -> None:
            self._finish_video_prime()
            self.media_stack.setCurrentWidget(self._placeholder_widget)
            self.actor_lbl.setText("PLAYBACK ERROR")
            self.stark_quote.setText(
                error_string or "The media backend could not decode this file."
            )
            self.action_triggered.emit(self.stark_quote.text())

        def _on_player_position_changed(self, position_ms: int) -> None:
            self._playhead_sec = max(0.0, position_ms / 1_000.0)
            self.tc_overlay.setText(_format_tc(self._playhead_sec))
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

        def _update_video_surface(self) -> None:
            if self._video_widget is None or self._last_video_image is None:
                return
            pixmap = QPixmap.fromImage(self._last_video_image)
            self._video_widget.setPixmap(
                pixmap.scaled(
                    self._video_widget.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        def resizeEvent(self, event: Any) -> None:  # noqa: N802
            super().resizeEvent(event)
            self._update_video_surface()

        def _on_player_duration_changed(self, duration_ms: int) -> None:
            if duration_ms <= 0:
                return
            self._max_duration_sec = duration_ms / 1_000.0
            self._mark_out_sec = self._max_duration_sec
            self.dur_overlay.setText(_format_tc(self._max_duration_sec))
            if self._player is not None and self._player.position() == 0:
                self._player.setPosition(1)
            self.duration_resolved.emit(self._max_duration_sec)

        def set_playhead(self, sec: float) -> None:
            self._playhead_sec = max(0.0, min(self._max_duration_sec, sec))
            self.tc_overlay.setText(_format_tc(self._playhead_sec))
            if self._player is not None and self._media_path:
                target_ms = round(self._playhead_sec * 1_000)
                if abs(self._player.position() - target_ms) > 80:
                    self._player.setPosition(target_ms)

        def _toggle_play(self) -> None:
            if self._player is not None and self._media_path:
                from PySide6.QtMultimedia import QMediaPlayer  # noqa: PLC0415

                playing = (
                    self._player.playbackState()
                    is QMediaPlayer.PlaybackState.PlayingState
                )
                if playing:
                    self._player.pause()
                    self._is_playing = False
                    if self.play_btn:
                        self.play_btn.setText("▶")
                else:
                    self._player.play()
                    self._is_playing = True
                    if self.play_btn:
                        self.play_btn.setText("❚❚")
                return
            self.action_triggered.emit("Import a movie before using playback controls")

        def _on_mark_in(self) -> None:
            self._mark_in_sec = self._playhead_sec

        def _on_mark_out(self) -> None:
            self._mark_out_sec = self._playhead_sec

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
            self._loop_enabled = not self._loop_enabled
            if self._player is not None:
                self._player.setLoops(-1 if self._loop_enabled else 1)

        def _toggle_mute(self) -> None:
            if self._audio_output is None or not self._media_path:
                self.action_triggered.emit("No source audio is loaded")
                return
            self._audio_output.setMuted(not self._audio_output.isMuted())
            self.action_triggered.emit(
                "Program audio muted"
                if self._audio_output.isMuted()
                else "Program audio enabled"
            )

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
            if (
                target
                and self._last_video_image is not None
                and self._last_video_image.save(target, "PNG")
            ):
                self.action_triggered.emit(f"Snapshot exported: {target}")

    # ─────────────────────────────────────────────────────────────────────────
    # Right Column: Inspector & AI Assistant + Dual Channel Audio VU Meter
    # ─────────────────────────────────────────────────────────────────────────
    class _WaveformWidget(QWidget):
        """Waveform view populated only from decoded, real audio samples."""

        def __init__(self, parent: _W | None = None) -> None:
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
                import numpy as np  # noqa: PLC0415
                import soundfile as sf  # type: ignore[import-not-found]  # noqa: PLC0415

                samples, _sample_rate = sf.read(str(audio_path), always_2d=True)
                mono = np.mean(samples, axis=1)
                if mono.size == 0:
                    raise ValueError("decoded audio contains no samples")
                peak_count = max(32, min(512, self.width() // 2 or 128))
                chunk_size = max(1, int(np.ceil(mono.size / peak_count)))
                self._peaks = [
                    float(np.max(np.abs(mono[index:index + chunk_size])))
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

    class _DialogueInspectorPanel(QFrame):
        translation_changed = Signal(str)
        take_changed = Signal(str)
        regenerate_requested = Signal()
        ai_fix_requested = Signal()
        compare_takes_requested = Signal()

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet("background:#111722;")

            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(8, 8, 8, 8)
            main_layout.setSpacing(8)

            insp_box = QVBoxLayout()
            insp_box.setSpacing(8)

            # Tabs
            tab_row = QHBoxLayout()
            t1 = QLabel("Inspector", self)
            t1.setStyleSheet("font-size: 11px; font-weight: 700; color: #F7F9FC; background: #1C2636; padding: 4px 8px; border-radius: 4px;")
            tab_row.addWidget(t1)

            t2 = QLabel("AI Assistant", self)
            t2.setStyleSheet("font-size: 11px; color: #64748B; padding: 4px 8px;")
            tab_row.addWidget(t2)

            t3 = QLabel("Metadata", self)
            t3.setStyleSheet("font-size: 11px; color: #64748B; padding: 4px 8px;")
            tab_row.addWidget(t3)
            tab_row.addStretch()
            insp_box.addLayout(tab_row)

            # Dialogue Fields Frame
            d_frame = QFrame(self)
            d_frame.setStyleSheet("background:#0D131F;border:1px solid #1E2838;border-radius:6px;padding:8px;")
            d_lay = QFormLayout(d_frame)
            d_lay.setSpacing(6)

            self.char_in = QLineEdit(d_frame)
            self.char_in.setPlaceholderText("Select an analyzed speaker")
            self.char_in.setStyleSheet("QLineEdit{background:#16202E;color:#F7F9FC;border:1px solid #283446;padding:3px 6px;border-radius:4px;font-size:11px;}")
            d_lay.addRow("Character:", self.char_in)

            self.lang_in = QLineEdit(d_frame)
            self.lang_in.setPlaceholderText("Target language code")
            self.lang_in.setStyleSheet("QLineEdit{background:#16202E;color:#F7F9FC;border:1px solid #283446;padding:3px 6px;border-radius:4px;font-size:11px;}")
            d_lay.addRow("Language:", self.lang_in)

            self.orig_in = QLineEdit(d_frame)
            self.orig_in.setPlaceholderText("Select or import source dialogue")
            self.orig_in.setStyleSheet("QLineEdit{background:#16202E;color:#F7F9FC;border:1px solid #283446;padding:3px 6px;border-radius:4px;font-size:11px;}")
            d_lay.addRow("Original:", self.orig_in)

            self.trans_in = QLineEdit(d_frame)
            self.trans_in.setPlaceholderText("Translation appears after processing")
            self.trans_in.setStyleSheet("QLineEdit{background:#16202E;color:#22D3EE;font-weight:700;border:1px solid #283446;padding:3px 6px;border-radius:4px;font-size:11px;}")
            self.trans_in.textChanged.connect(self._on_trans_changed)
            d_lay.addRow("Translation:", self.trans_in)

            insp_box.addWidget(d_frame)

            # Dual Cards: Timing & Scores
            cards_row = QHBoxLayout()
            cards_row.setSpacing(6)

            # Timing Card
            t_card = QFrame(self)
            t_card.setStyleSheet("background:#0D131F;border:1px solid #1E2838;border-radius:6px;padding:6px;")
            tc_lay = QVBoxLayout(t_card)
            tc_lay.setSpacing(3)
            tc_title = QLabel("Timing", t_card)
            tc_title.setStyleSheet("font-size:10px;font-weight:800;color:#8C9BAE;")
            tc_lay.addWidget(tc_title)
            self.src_dur_lbl = QLabel("Source Duration:  —", t_card)
            tc_lay.addWidget(self.src_dur_lbl)
            self.dub_dur_lbl = QLabel("Dub Duration:     —", t_card)
            tc_lay.addWidget(self.dub_dur_lbl)
            self.diff_lbl = QLabel("Difference:       —", t_card)
            self.diff_lbl.setStyleSheet("color:#F59E0B;font-weight:700;")
            tc_lay.addWidget(self.diff_lbl)
            cards_row.addWidget(t_card, stretch=1)

            # Scores Card
            s_card = QFrame(self)
            s_card.setStyleSheet("background:#0D131F;border:1px solid #1E2838;border-radius:6px;padding:6px;")
            sc_lay = QVBoxLayout(s_card)
            sc_lay.setSpacing(2)
            sc_title = QLabel("Scores", s_card)
            sc_title.setStyleSheet("font-size:10px;font-weight:800;color:#8C9BAE;")
            sc_lay.addWidget(sc_title)
            self.v_score_lbl = QLabel("Voice:     Not measured", s_card)
            sc_lay.addWidget(self.v_score_lbl)
            self.e_score_lbl = QLabel("Emotion:   Not measured", s_card)
            sc_lay.addWidget(self.e_score_lbl)
            self.t_score_lbl = QLabel("Timing:    Not measured", s_card)
            sc_lay.addWidget(self.t_score_lbl)
            self.l_score_lbl = QLabel("Lip Sync:  Not measured", s_card)
            sc_lay.addWidget(self.l_score_lbl)
            self.pass_lbl = QLabel("Quality:   NOT RUN", s_card)
            self.pass_lbl.setStyleSheet("color:#64748B;font-weight:800;")
            sc_lay.addWidget(self.pass_lbl)
            cards_row.addWidget(s_card, stretch=1)

            insp_box.addLayout(cards_row)

            # Take Selector & Waveform
            take_card = QFrame(self)
            take_card.setStyleSheet("background:#0D131F;border:1px solid #1E2838;border-radius:6px;padding:6px;")
            tk_lay = QVBoxLayout(take_card)
            tk_lay.setSpacing(6)

            tk_top = QHBoxLayout()
            tk_top.addWidget(QLabel("Take:", take_card))
            self.take_combo = QComboBox(take_card)
            self.take_combo.addItem("No generated takes")
            self.take_combo.setEnabled(False)
            self.take_combo.setStyleSheet("QComboBox{background:#16202E;color:#F7F9FC;border:none;padding:2px 6px;border-radius:4px;font-size:11px;}")
            self.take_combo.currentTextChanged.connect(self._on_take_combo_changed)
            tk_top.addWidget(self.take_combo, stretch=1)
            tk_lay.addLayout(tk_top)

            # Real painted waveform instead of a text approximation.
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

            # Action Buttons Row
            act_row = QHBoxLayout()
            act_row.setSpacing(4)
            r_btn = QPushButton("Regenerate", take_card)
            r_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            r_btn.setStyleSheet("QPushButton{background:#8B5CF6;color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:4px;}"
                                "QPushButton:hover{background:#7C3AED;}")
            r_btn.clicked.connect(lambda: self.regenerate_requested.emit())
            act_row.addWidget(r_btn)

            f_btn = QPushButton("AI Fix", take_card)
            f_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            f_btn.setStyleSheet("QPushButton{background:#2563EB;color:#FFF;font-size:10px;font-weight:700;border:none;border-radius:4px;padding:4px;}"
                                "QPushButton:hover{background:#1D4ED8;}")
            f_btn.clicked.connect(lambda: self.ai_fix_requested.emit())
            act_row.addWidget(f_btn)

            c_btn = QPushButton("Compare Takes", take_card)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet("QPushButton{background:#16202E;color:#A9B2C3;font-size:10px;font-weight:600;border:1px solid #283446;border-radius:4px;padding:4px;}"
                                "QPushButton:hover{background:#2563EB;color:#FFF;}")
            c_btn.clicked.connect(lambda: self.compare_takes_requested.emit())
            act_row.addWidget(c_btn)

            tk_lay.addLayout(act_row)
            insp_box.addWidget(take_card)

            main_layout.addLayout(insp_box, stretch=1)

            # Far Right Dual VU Level Meter Panel
            vu_frame = QFrame(self)
            vu_frame.setFixedWidth(32)
            vu_frame.setStyleSheet("background:#080B10;border:1px solid #1E2838;border-radius:4px;")
            vu_lay = QVBoxLayout(vu_frame)
            vu_lay.setContentsMargins(2, 4, 2, 4)
            vu_lay.setSpacing(2)

            vu_lbl = QLabel("METER OFF", vu_frame)
            vu_lbl.setStyleSheet("font-size:9px;color:#64748B;font-weight:700;")
            vu_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vu_lay.addWidget(vu_lbl)

            db_ticks = ["-6", "-12", "-18", "-24", "-30", "-36", "-42", "-48", "-54"]
            for db_val in db_ticks:
                bar = QFrame(vu_frame)
                bar.setFixedHeight(12)
                bar.setStyleSheet("background:#1E2838;border-radius:1px;")
                bar_lay = QHBoxLayout(bar)
                bar_lay.setContentsMargins(1, 0, 1, 0)
                t_lbl = QLabel(db_val, bar)
                t_lbl.setStyleSheet("font-size:7px;color:#080B10;font-weight:700;")
                bar_lay.addWidget(t_lbl)
                vu_lay.addWidget(bar)

            main_layout.addWidget(vu_frame)

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
            self.char_in.setText(char_name)
            self.lang_in.setText(lang)
            self.orig_in.setText(orig_text)
            self.trans_in.setText(trans_text)
            if source_duration is not None:
                dub_duration = dub_duration if dub_duration is not None else source_duration
                difference = (
                    ((dub_duration - source_duration) / source_duration) * 100
                    if source_duration > 0
                    else 0.0
                )
                self.src_dur_lbl.setText(f"Source Duration:  {source_duration:.2f} s")
                self.dub_dur_lbl.setText(f"Dub Duration:     {dub_duration:.2f} s")
                self.diff_lbl.setText(f"Difference:       {difference:+.1f}%")
                color = "#22C55E" if abs(difference) <= 8 else "#F59E0B"
                self.diff_lbl.setStyleSheet(f"color:{color};font-weight:700;")
                self.wave_end_lbl.setText(f"00:{dub_duration:05.2f}")
            if score is not None:
                normalized = max(0.0, min(1.0, score / 100 if score > 1 else score))
                self.v_score_lbl.setText(f"Voice:     {normalized * 100:.0f}%")

        def clear_quality_report(self) -> None:
            self.v_score_lbl.setText("Voice:     Not measured")
            self.e_score_lbl.setText("Emotion:   Not measured")
            self.t_score_lbl.setText("Timing:    Not measured")
            self.l_score_lbl.setText("Lip Sync:  Not measured")
            self.pass_lbl.setText("Quality:   NOT RUN")
            self.pass_lbl.setStyleSheet("color:#64748B;font-weight:800;")

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

        def _on_trans_changed(self, text: str) -> None:
            self.translation_changed.emit(text)

        def _on_take_combo_changed(self, take_name: str) -> None:
            self.waveform.set_take_name(take_name)
            audio_path = str(self.take_combo.currentData() or "")
            if audio_path:
                self.waveform.set_audio_file(audio_path)
            self.take_changed.emit(take_name)

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline Graphics Canvas View
    # ─────────────────────────────────────────────────────────────────────────
    class _TimelineCanvasView(QGraphicsView):
        timecode_changed = Signal(float)
        clip_clicked = Signal(dict)

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setScene(QGraphicsScene(self))
            self._duration_sec = 1.0
            self._px_per_sec = PX_PER_SEC_DEFAULT
            self._playhead_sec = 0.0
            self._clip_items: list[tuple[dict, QGraphicsRectItem, QGraphicsTextItem]] = []
            self._clips_data: list[tuple] = []
            self._selected_rect: QGraphicsRectItem | None = None
            self._video_thumbnail: QPixmap | None = None
            self.setStyleSheet("QGraphicsView{background:#0D1118;border:none;}")
            self.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.set_clips([], 1.0)

        def set_clips(self, clips_list: list[tuple], duration_sec: float = 10.0) -> None:
            self._clips_data = list(clips_list)
            self._duration_sec = max(1.0, duration_sec)
            self._px_per_sec = max(
                0.25,
                min(PX_PER_SEC_DEFAULT, 1_400.0 / self._duration_sec),
            )
            self._build_scene()

        def set_playhead(self, sec: float) -> None:
            self._playhead_sec = max(0.0, min(self._duration_sec, sec))
            if hasattr(self, "_playhead_bar") and self._playhead_bar:
                ph_x = self._playhead_sec * self._px_per_sec
                h = RULER_HEIGHT + len(_TRACK_DEFS) * TRACK_HEIGHT + 20
                self._playhead_bar.setRect(QRectF(ph_x, 0, 2, h))
                if hasattr(self, "_playhead_handle") and self._playhead_handle:
                    polygon = [QPointF(ph_x - 6, 0), QPointF(ph_x + 8, 0), QPointF(ph_x + 1, 10)]
                    self._playhead_handle.setPolygon(polygon)

        def set_video_thumbnail(self, image: Any) -> None:
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return
            self._video_thumbnail = pixmap
            self._build_scene()

        def clear_video_thumbnail(self) -> None:
            self._video_thumbnail = None

        def update_subtitle_text(self, text: str) -> None:
            for c_info, rect, txt_item in self._clip_items:
                if c_info.get("tid") == "S2":
                    c_info["label"] = text
                    txt_item.setPlainText(text)
                    break

        def _build_scene(self) -> None:
            sc = self.scene()
            sc.clear()
            self._clip_items.clear()
            self._selected_rect = None

            w = self._duration_sec * self._px_per_sec + 200
            h = RULER_HEIGHT + len(_TRACK_DEFS) * TRACK_HEIGHT + 20
            sc.setSceneRect(0, 0, w, h)

            # Ruler
            sc.addRect(QRectF(0, 0, w, RULER_HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#080B10")))
            sc.addLine(QLineF(0, RULER_HEIGHT, w, RULER_HEIGHT), QPen(QColor("#1E2838"), 1))

            # Ruler Timecodes
            tick_interval = next(
                (
                    interval
                    for interval in (1, 2, 5, 10, 30, 60, 120, 300, 600, 1_800)
                    if interval * self._px_per_sec >= 72
                ),
                3_600,
            )
            tick_seconds = range(0, int(self._duration_sec) + 1, tick_interval)
            for second in tick_seconds:
                x = second * self._px_per_sec
                sc.addLine(QLineF(x, RULER_HEIGHT - 8, x, RULER_HEIGHT), QPen(QColor("#EAB308"), 1))
                tc_txt = sc.addText(_format_tc(float(second)), QFont("Cascadia Code", 8))
                tc_txt.setDefaultTextColor(QColor("#8C9BAE"))
                tc_txt.setPos(x + 2, 2)

            # Tracks Backgrounds & Separators
            for i, (tid, label, col, ttype) in enumerate(_TRACK_DEFS):
                y = RULER_HEIGHT + i * TRACK_HEIGHT
                bg_col = QColor("#0D1118") if i % 2 == 0 else QColor("#090E17")
                sc.addRect(QRectF(0, y, w, TRACK_HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(bg_col))
                sc.addLine(QLineF(0, y + TRACK_HEIGHT - 1, w, y + TRACK_HEIGHT - 1), QPen(QColor("#161F2E"), 1))

            # Render Clips
            track_y_map = {t[0]: RULER_HEIGHT + idx * TRACK_HEIGHT + 2 for idx, t in enumerate(_TRACK_DEFS)}
            color_map = {t[0]: t[2] for t in _TRACK_DEFS}

            for clip_item in self._clips_data:
                tid = clip_item[0]
                start = clip_item[1]
                dur = clip_item[2]
                label = clip_item[3]
                score = clip_item[4] if len(clip_item) > 4 else None

                x = start * self._px_per_sec
                cw = max(MIN_CLIP_WIDTH, dur * self._px_per_sec)
                cy = track_y_map.get(tid, RULER_HEIGHT)
                ch = TRACK_HEIGHT - 4

                c_color = color_map.get(tid, "#3B82F6")
                clip_rect = sc.addRect(QRectF(x, cy, cw, ch), QPen(QColor(c_color), 1), QBrush(QColor(c_color).darker(180)))
                clip_rect.setData(0, tid)
                clip_rect.setToolTip(
                    f"{tid} · {label}\n{_format_tc(start)} → {_format_tc(start + dur)}"
                )

                if tid == "V1" and self._video_thumbnail is not None:
                    thumbnail = self._video_thumbnail.scaledToHeight(
                        max(1, round(ch - 6)),
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    thumb_x = x + 3
                    while thumb_x < x + cw - 3:
                        thumb_item = sc.addPixmap(thumbnail)
                        thumb_item.setPos(thumb_x, cy + 3)
                        thumb_item.setOpacity(0.72)
                        thumb_x += max(1, thumbnail.width() + 2)

                txt = sc.addText(label, QFont("Segoe UI Variable", 8, QFont.Weight.Bold))
                txt.setDefaultTextColor(QColor("#F7F9FC"))
                txt.setPos(x + 4, cy + 4)

                c_dict = {"tid": tid, "start": start, "dur": dur, "label": label, "score": score}
                self._clip_items.append((c_dict, clip_rect, txt))

            if not self._clips_data:
                empty = sc.addText(
                    "IMPORT A MOVIE TO BUILD THE TIMELINE",
                    QFont("Segoe UI Variable", 11, QFont.Weight.DemiBold),
                )
                empty.setDefaultTextColor(QColor("#64748B"))
                empty.setPos(24, RULER_HEIGHT + 18)

            # Playhead Bar
            ph_x = self._playhead_sec * self._px_per_sec
            self._playhead_bar = sc.addRect(QRectF(ph_x, 0, 2, h), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#3B82F6")))
            polygon = [QPointF(ph_x - 6, 0), QPointF(ph_x + 8, 0), QPointF(ph_x + 1, 10)]
            self._playhead_handle = sc.addPolygon(polygon, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#3B82F6")))

        def mousePressEvent(self, event: Any) -> None:
            pt = self.mapToScene(event.pos())
            if pt.y() <= RULER_HEIGHT:
                sec = pt.x() / self._px_per_sec
                self.set_playhead(sec)
                self.timecode_changed.emit(self._playhead_sec)
            else:
                for c_info, rect, txt_item in self._clip_items:
                    if rect.contains(pt):
                        if self._selected_rect is not None:
                            old_color = next(
                                (row[2] for row in _TRACK_DEFS if row[0] == self._selected_rect.data(0)),
                                "#3B82F6",
                            )
                            self._selected_rect.setPen(QPen(QColor(old_color), 1))
                        rect.setPen(QPen(QColor("#E2E8F0"), 2))
                        self._selected_rect = rect
                        self.clip_clicked.emit(c_info)
                        break
            super().mousePressEvent(event)

        def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
                current = self.transform().m11()
                if 0.55 <= current * factor <= 3.5:
                    self.scale(factor, 1.0)
                event.accept()
                return
            super().wheelEvent(event)

    # ─────────────────────────────────────────────────────────────────────────
    # Floating AI Actions Overlay Panel
    # ─────────────────────────────────────────────────────────────────────────
    class _FloatingAIActionsPanel(QFrame):
        action_clicked = Signal(str)
        run_requested = Signal()
        cancel_requested = Signal()

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("AiActionsPanel")
            self.setFixedWidth(190)
            self._busy = False
            self.setStyleSheet(
                "QFrame#AiActionsPanel {"
                "  background: #0B0F17;"
                "  border-left: 1px solid #1E2838;"
                "}"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)

            header = QHBoxLayout()
            hdr = QLabel("AGENTIC DIRECTOR", self)
            hdr.setStyleSheet("font-size:10px;font-weight:800;color:#4F8CFF;")
            header.addWidget(hdr)
            header.addStretch()
            self.status_badge = QLabel("● IDLE", self)
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#64748B;")
            header.addWidget(self.status_badge)
            layout.addLayout(header)

            agent_card = QFrame(self)
            agent_card.setStyleSheet(
                "background:#101827;border:1px solid #253149;border-radius:7px;"
            )
            agent_layout = QVBoxLayout(agent_card)
            agent_layout.setContentsMargins(7, 7, 7, 7)
            agent_layout.setSpacing(5)
            self.stage_lbl = QLabel("Ready · 12-stage production graph", agent_card)
            self.stage_lbl.setWordWrap(True)
            self.stage_lbl.setStyleSheet("font-size:9px;color:#A9B2C3;")
            agent_layout.addWidget(self.stage_lbl)
            self.progress_bar = QProgressBar(agent_card)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(5)
            self.progress_bar.setStyleSheet(
                "QProgressBar{background:#243044;border:none;border-radius:2px;}"
                "QProgressBar::chunk{background:#4F8CFF;border-radius:2px;}"
            )
            agent_layout.addWidget(self.progress_bar)
            self.quality_lbl = QLabel("QUALITY GATE · NOT RUN", agent_card)
            self.quality_lbl.setStyleSheet("font-size:8px;font-weight:800;color:#64748B;")
            agent_layout.addWidget(self.quality_lbl)
            self.run_btn = QPushButton("✦  AUTO DUB MASTER", agent_card)
            self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.run_btn.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFF;border:1px solid #3B82F6;"
                "border-radius:5px;padding:5px;font-size:10px;font-weight:800;}"
                "QPushButton:hover{background:#3B82F6;}"
            )
            self.run_btn.clicked.connect(self._on_run_clicked)
            agent_layout.addWidget(self.run_btn)
            layout.addWidget(agent_card)

            action_heading = QLabel("AI ACTIONS", self)
            action_heading.setStyleSheet(
                "font-size:9px;font-weight:800;color:#64748B;border-bottom:1px solid #1E2838;"
                "padding:3px 0;"
            )
            layout.addWidget(action_heading)

            actions = [
                ("🪄", "Regenerate Voice"),
                ("⏱️", "Match Timing"),
                ("✍️", "Rewrite Translation"),
                ("✂️", "Shorten Translation"),
                ("⚙️", "Properties"),
            ]

            for icon, name in actions:
                btn = QPushButton(f"{icon}  {name}", self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background: transparent; color: #CBD5E1; font-size: 11px; text-align: left;"
                    "  border: none; padding: 4px 6px; border-radius: 4px;"
                    "}"
                    "QPushButton:hover { background: #1D293D; color: #FFF; }"
                )
                btn.clicked.connect(lambda _, n=name: self.action_clicked.emit(n))
                layout.addWidget(btn)

            layout.addStretch()

        def _on_run_clicked(self) -> None:
            if self._busy:
                self.cancel_requested.emit()
            else:
                self.run_requested.emit()

        def set_progress(self, message: str, percent: int) -> None:
            self._busy = percent < 100
            self.status_badge.setText("● RUNNING")
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#22D3EE;")
            self.progress_bar.setValue(max(0, min(100, percent)))
            self.stage_lbl.setText(message)
            self.run_btn.setText("■  CANCEL SAFELY" if self._busy else "✦  AUTO DUB MASTER")
            self.run_btn.setStyleSheet(
                "QPushButton{background:#7F1D1D;color:#FFF;border:1px solid #EF4444;"
                "border-radius:5px;padding:5px;font-size:10px;font-weight:800;}"
                "QPushButton:hover{background:#991B1B;}"
                if self._busy
                else "QPushButton{background:#2563EB;color:#FFF;border:1px solid #3B82F6;"
                "border-radius:5px;padding:5px;font-size:10px;font-weight:800;}"
                "QPushButton:hover{background:#3B82F6;}"
            )

        def set_complete(
            self,
            message: str = "Master ready for review",
            *,
            quality_passed: bool | None = None,
        ) -> None:
            self._busy = False
            self.status_badge.setText("● REVIEW")
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#F59E0B;")
            self.progress_bar.setValue(100)
            self.stage_lbl.setText(message)
            self.run_btn.setText("↻  RUN NEW REVISION")
            if quality_passed is not None:
                self.quality_lbl.setText(
                    f"QUALITY GATE · {'PASS' if quality_passed else 'REVIEW'}"
                )
                color = "#22C55E" if quality_passed else "#F59E0B"
                self.quality_lbl.setStyleSheet(
                    f"font-size:8px;font-weight:800;color:{color};"
                )

        def set_failed(self, message: str) -> None:
            self._busy = False
            self.status_badge.setText("● STOPPED")
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#EF4444;")
            self.stage_lbl.setText(message)
            self.run_btn.setText("↻  RETRY AUTOMATION")
            self.quality_lbl.setText("QUALITY GATE · ACTION REQUIRED")
            self.quality_lbl.setStyleSheet("font-size:8px;font-weight:800;color:#F59E0B;")

        def set_state(self, state: AgenticStudioState) -> None:
            self.progress_bar.setValue(state.progress)
            running = next(
                (item for item in state.stages if item.status is StageStatus.RUNNING),
                None,
            )
            if running is not None:
                self.stage_lbl.setText(running.detail or running.label)
            elif state.is_complete:
                self.stage_lbl.setText("Production graph complete")
            else:
                ready = state.ready_stages()
                self.stage_lbl.setText(
                    f"Ready · {len(ready)} stage{'s' if len(ready) != 1 else ''} available"
                )
            report = state.quality_report
            if report is not None:
                self.quality_lbl.setText(
                    f"QUALITY GATE · {'PASS' if report.passed else 'REVIEW'} · "
                    f"{report.overall_score * 100:.1f}"
                )
                color = "#22C55E" if report.passed else "#F59E0B"
                self.quality_lbl.setStyleSheet(
                    f"font-size:8px;font-weight:800;color:{color};"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline Header Track Panel
    # ─────────────────────────────────────────────────────────────────────────
    class _TimelineHeaderPanel(QFrame):
        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self.setFixedWidth(TRACK_HEADER_WIDTH)
            self.setStyleSheet("background:#111722;border-right:1px solid #1E2838;")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # Ruler Header Cell
            self.r_cell = QLabel("Timeline", self)
            self.r_cell.setFixedHeight(RULER_HEIGHT)
            self.r_cell.setStyleSheet(
                "font-size:11px; font-weight:700; color:#F7F9FC; background:#080B10;"
                "border-bottom:1px solid #1E2838; padding-left:8px;"
            )
            layout.addWidget(self.r_cell)

            # Track Cells
            for tid, label, col, ttype in _TRACK_DEFS:
                cell = QFrame(self)
                cell.setFixedHeight(TRACK_HEIGHT)
                cell.setStyleSheet("border-bottom:1px solid #161F2E;background:#111722;")
                c_lay = QHBoxLayout(cell)
                c_lay.setContentsMargins(6, 0, 6, 0)
                c_lay.setSpacing(6)

                lock_lbl = QLabel("🔒", cell)
                lock_lbl.setStyleSheet("font-size:10px;color:#64748B;")
                c_lay.addWidget(lock_lbl)

                eye_lbl = QLabel("👁️" if ttype == "video" else "🎙" if ttype == "audio" else "💬", cell)
                eye_lbl.setStyleSheet("font-size:10px;color:#8C9BAE;")
                c_lay.addWidget(eye_lbl)

                t_lbl = QLabel(f"{tid}  {label}", cell)
                t_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{col};")
                c_lay.addWidget(t_lbl, stretch=1)

                layout.addWidget(cell)

            layout.addStretch()

        def set_header_title(self, title: str) -> None:
            self.r_cell.setText(title)

    # ─────────────────────────────────────────────────────────────────────────
    # Main Timeline Editor Screen Class
    # ─────────────────────────────────────────────────────────────────────────
    class TimelineScreen(QWidget):
        clip_selected = Signal(object)
        project_loaded = Signal(str)

        def __init__(self, parent: _W | None = None) -> None:
            super().__init__(parent)
            self._current_project_data: dict[str, Any] = {
                "name": "Untitled Studio",
                "movie_name": "",
                "file_path": "",
                "character": "",
                "duration": 1.0,
                "original_text": "",
                "translation_text": "",
                "clips": [],
                "generated_paths": (),
            }
            self._active_clip_info: dict[str, Any] | None = None
            app_data = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            session_root = Path(app_data) / "sessions"
            self._session_store = StudioSessionStore(session_root)
            self._automation_state = create_automation_plan(
                "Untitled Studio",
                target_language="bn",
            )
            self._dubbing_worker: Any | None = None
            self._assistant_worker: Any | None = None
            self._tts_worker: Any | None = None
            self._build_ui()
            self._wire_signals()
            self.ai_overlay.set_state(self._automation_state)
            self.stage_bar.set_state(self._automation_state)
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setInterval(15_000)
            self._autosave_timer.timeout.connect(self._autosave_session)
            self._autosave_timer.start()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            self.stage_bar = _ProductionStageBar(self)
            root.addWidget(self.stage_bar)

            self.workspace_splitter = QSplitter(Qt.Orientation.Vertical, self)
            self.workspace_splitter.setHandleWidth(1)
            self.workspace_splitter.setStyleSheet(
                "QSplitter::handle{background:#1E2838;}"
            )

            # Main 3-column Studio workspace.
            upper_splitter = QSplitter(Qt.Orientation.Horizontal, self.workspace_splitter)
            upper_splitter.setHandleWidth(1)
            upper_splitter.setFixedHeight(440)
            upper_splitter.setStyleSheet("QSplitter::handle{background:#1E2838;}")

            # Left Column (Media Browser)
            self.media_panel = _MediaBrowserPanel(upper_splitter)
            self.media_panel.setFixedWidth(375)
            upper_splitter.addWidget(self.media_panel)

            # Center Column (Program Video Monitor)
            self.monitor_panel = _ProgramMonitorPanel(upper_splitter)
            upper_splitter.addWidget(self.monitor_panel)

            # Right Column (Dialogue Inspector & Dual VU Level Meter)
            self.inspector_panel = _DialogueInspectorPanel(upper_splitter)
            self.inspector_panel.setFixedWidth(490)
            upper_splitter.addWidget(self.inspector_panel)

            upper_splitter.setStretchFactor(0, 0)
            upper_splitter.setStretchFactor(1, 1)
            upper_splitter.setStretchFactor(2, 0)
            upper_splitter.setSizes([375, 670, 490])
            self.workspace_splitter.addWidget(upper_splitter)

            # Lower multitrack timeline and agentic actions.
            tl_container = QWidget(self.workspace_splitter)
            tl_lay = QHBoxLayout(tl_container)
            tl_lay.setContentsMargins(0, 0, 0, 0)
            tl_lay.setSpacing(0)

            # Timeline Track Headers
            self.header_p = _TimelineHeaderPanel(tl_container)
            tl_lay.addWidget(self.header_p)

            # Timeline Canvas View
            self.canvas_view = _TimelineCanvasView(tl_container)
            tl_lay.addWidget(self.canvas_view, stretch=1)

            # AI Actions Dock Panel
            self.ai_overlay = _FloatingAIActionsPanel(tl_container)
            tl_lay.addWidget(self.ai_overlay)

            self.workspace_splitter.addWidget(tl_container)
            self.workspace_splitter.setStretchFactor(0, 0)
            self.workspace_splitter.setStretchFactor(1, 1)
            self.workspace_splitter.setSizes([440, 475])
            root.addWidget(self.workspace_splitter, stretch=1)

            # Bottom status bar reports only real operations.
            dock_bar = QFrame(self)
            dock_bar.setFixedHeight(32)
            dock_bar.setStyleSheet("background:#080B10;border-top:1px solid #1E2838;")
            d_lay = QHBoxLayout(dock_bar)
            d_lay.setContentsMargins(12, 0, 12, 0)

            self.status_msg_lbl = QLabel("Ready · import a movie to begin", dock_bar)
            self.status_msg_lbl.setStyleSheet("font-size:11px;color:#64748B;")
            d_lay.addWidget(self.status_msg_lbl)

            d_lay.addStretch()

            root.addWidget(dock_bar)

        def _wire_signals(self) -> None:
            # Monitor playhead sync
            self.monitor_panel.playhead_changed.connect(self.canvas_view.set_playhead)
            self.canvas_view.timecode_changed.connect(self.monitor_panel.set_playhead)
            self.monitor_panel.action_triggered.connect(self._show_status)
            self.monitor_panel.import_requested.connect(self.import_media_dialog)
            self.monitor_panel.duration_resolved.connect(self._on_media_duration_resolved)
            self.monitor_panel.first_frame_decoded.connect(
                self.canvas_view.set_video_thumbnail
            )

            # Media selection sync
            self.media_panel.media_selected.connect(self._on_media_selected)

            # Timeline clip selection -> Inspector sync
            self.canvas_view.clip_clicked.connect(self._on_timeline_clip_clicked)

            # Inspector live text sync -> Timeline canvas
            self.inspector_panel.translation_changed.connect(self.canvas_view.update_subtitle_text)
            self.inspector_panel.translation_changed.connect(self._on_translation_changed)
            self.inspector_panel.lang_in.editingFinished.connect(
                self._on_target_language_changed
            )

            # Inspector Action buttons
            self.inspector_panel.regenerate_requested.connect(self._on_ai_regenerate_voice)
            self.inspector_panel.ai_fix_requested.connect(self._on_ai_fix_all)
            self.inspector_panel.compare_takes_requested.connect(self._compare_takes)

            # Floating AI Actions
            self.ai_overlay.action_clicked.connect(self._on_ai_action_clicked)
            self.ai_overlay.run_requested.connect(self._run_agentic_dub)
            self.ai_overlay.cancel_requested.connect(self._cancel_agentic_dub)

        def load_project_data(self, project_info: dict[str, Any]) -> None:
            """Load a real movie and derive all initial UI state from that file."""
            file_path = str(project_info.get("file_path") or project_info.get("movie_path", ""))
            source = Path(file_path) if file_path else None
            target_language = str(
                project_info.get("target_language")
                or next(iter(project_info.get("target_languages", [])), "bn")
            )
            if source is None or not source.is_file():
                self._show_status("The selected source movie does not exist")
                return
            if source.suffix.lower() in {".srt", ".vtt", ".ass"}:
                self.import_subtitle_file(str(source))
                return

            proj_name = str(project_info.get("name") or source.stem)
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe  # noqa: PLC0415

                media_info = probe(source)
                duration = max(0.001, float(media_info["format"]["duration"]))
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_status(
                    f"Metadata probe unavailable; waiting for the media backend: {exc}"
                )

            sidecar = next(
                (
                    candidate
                    for suffix in (".srt", ".vtt")
                    if (candidate := source.with_suffix(suffix)).is_file()
                ),
                None,
            )
            source_cues = (
                self._parse_subtitle_file_cues(str(sidecar), track_id="S1")
                if sidecar
                else []
            )
            clips: list[tuple] = [
                ("V1", 0.0, duration, source.name, None),
                ("A1", 0.0, duration, source.name, None),
            ]
            clips.extend(source_cues)
            data: dict[str, Any] = {
                "name": proj_name,
                "movie_name": source.name,
                "file_path": str(source.resolve()),
                "character": str(project_info.get("character", "")),
                "duration": duration,
                "original_text": source_cues[0][3] if source_cues else "",
                "translation_text": "",
                "quote": "",
                "clips": clips,
                "generated_paths": tuple(project_info.get("generated_paths", ())),
            }

            self._current_project_data = data
            self.canvas_view.clear_video_thumbnail()
            self.media_panel.set_project_name(
                data["name"],
                data["movie_name"],
                data.get("file_path", ""),
                tuple(data.get("generated_paths", ())),
            )
            self.monitor_panel.set_project_info(
                data["name"],
                data["movie_name"],
                data["character"],
                data["quote"],
                data["duration"],
                data.get("file_path", ""),
            )
            self.inspector_panel.update_clip_info(
                data["original_text"],
                data["translation_text"],
                data["character"],
                target_language,
            )
            self.header_p.set_header_title(data["name"])
            self.canvas_view.set_clips(data["clips"], data["duration"])
            self.inspector_panel.clear_quality_report()
            try:
                saved_state = self._session_store.load(proj_name)
            except (OSError, ValueError):
                saved_state = None
            if saved_state is None or (
                file_path and saved_state.source_path and saved_state.source_path != file_path
            ):
                saved_state = create_automation_plan(
                    proj_name,
                    source_path=file_path,
                    target_language=target_language,
                    quality_profile=str(project_info.get("quality_profile", "theatrical")),
                )
            self._automation_state = saved_state
            self._persist_automation_state()
            self.ai_overlay.set_state(self._automation_state)
            self.project_loaded.emit(str(data["name"]))
            self._show_status(f"Loaded source movie: {source.name}")

        def import_subtitle_file(self, srt_path: str, *, track_id: str = "S1") -> None:
            """Import a real .srt or .vtt subtitle file and update timeline clips dynamically."""
            if track_id not in {"S1", "S2"}:
                raise ValueError("subtitle track must be S1 or S2")
            try:
                cues = self._parse_subtitle_file_cues(srt_path, track_id=track_id)
            except (OSError, UnicodeError, ValueError) as exc:
                self._show_status(f"Subtitle import failed: {exc}")
                return
            if cues:
                current_duration = float(self._current_project_data.get("duration", 1.0))
                dur = max([c[1] + c[2] for c in cues] + [current_duration])
                current_clips = [
                    c
                    for c in self._current_project_data.get("clips", [])
                    if c[0] != track_id
                ]
                current_clips.extend(cues)
                self._current_project_data["clips"] = current_clips
                self._current_project_data["duration"] = dur
                self.canvas_view.set_clips(current_clips, dur)

                first = cues[0][3]
                if track_id == "S1":
                    self._current_project_data["original_text"] = first
                else:
                    self._current_project_data["translation_text"] = first
                self.inspector_panel.update_clip_info(
                    str(self._current_project_data.get("original_text", "")),
                    str(self._current_project_data.get("translation_text", "")),
                    str(self._current_project_data.get("character", "")),
                    self._automation_state.target_language,
                )
                self._show_status(
                    f"Imported {len(cues)} subtitle cues to {track_id}: {Path(srt_path).name}"
                )

        @staticmethod
        def _parse_subtitle_file_cues(
            path: str,
            *,
            track_id: str = "S1",
        ) -> list[tuple]:
            """Parse SRT or WebVTT file into track tuple items."""
            results: list[tuple] = []
            from aidub.subtitles.codec import parse_srt, parse_webvtt  # noqa: PLC0415

            content = Path(path).read_text(encoding="utf-8-sig")
            doc = parse_webvtt(content) if path.lower().endswith(".vtt") else parse_srt(content)
            for cue in doc.cues:
                start_s = cue.time_range.start.ticks / 1000.0
                end_s = cue.time_range.end_exclusive.ticks / 1000.0
                dur_s = max(0.001, end_s - start_s)
                txt = cue.text.replace("\n", " ")
                results.append((track_id, start_s, dur_s, txt, None))
            return results

        def _on_media_selected(self, media_ref: str) -> None:
            path = Path(media_ref)
            suffix = path.suffix.lower()
            if path.is_file() and suffix in {".mkv", ".mp4", ".mov", ".avi", ".m2ts"}:
                self.load_project_data(
                    {
                        "name": path.stem,
                        "file_path": str(path),
                        "target_language": self._automation_state.target_language,
                    }
                )
                self._show_status(f"Program Monitor loaded: {path.name}")
            elif path.is_file() and suffix in {".srt", ".vtt"}:
                self.import_subtitle_file(str(path))
            elif path.is_file() and suffix in {".wav", ".flac", ".mp3", ".aac"}:
                self._import_audio_asset(path)
            else:
                self._show_status(f"Unsupported or missing media: {media_ref}")

        def import_media_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Source Movie",
                str(Path(str(self._current_project_data.get("file_path", ""))).parent)
                if self._current_project_data.get("file_path")
                else "",
                "Movies (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
            )
            if path:
                self.load_project_data({"name": Path(path).stem, "file_path": path})

        def open_media_path(self, path: str | Path) -> None:
            self._on_media_selected(str(path))

        def import_subtitle_dialog(self, *, target: bool = False) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Target Subtitles" if target else "Import Source Subtitles",
                "",
                "Subtitles (*.srt *.vtt);;All Files (*)",
            )
            if path:
                self.import_subtitle_file(path, track_id="S2" if target else "S1")

        def import_audio_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Audio Asset",
                "",
                "Audio (*.wav *.flac *.mp3 *.aac);;All Files (*)",
            )
            if path:
                self._import_audio_asset(Path(path))

        def _import_audio_asset(self, path: Path) -> None:
            labels = ["Dubbed Voice (A2)", "Music (A3)", "SFX (A4)", "Ambience (A5)"]
            selection, accepted = QInputDialog.getItem(
                self,
                "Place Audio Asset",
                f"Choose a timeline track for {path.name}:",
                labels,
                0,
                False,
            )
            if not accepted:
                return
            track_id = {"Dubbed Voice (A2)": "A2", "Music (A3)": "A3", "SFX (A4)": "A4", "Ambience (A5)": "A5"}[selection]
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe  # noqa: PLC0415

                media_info = probe(path)
                duration = max(0.001, float(media_info["format"]["duration"]))
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_status(f"Audio metadata unavailable: {exc}")
            clips = list(self._current_project_data.get("clips", []))
            clips.append((track_id, 0.0, duration, path.name, None))
            self._current_project_data["clips"] = clips
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (str(path),)
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_clips(
                clips,
                max(float(self._current_project_data.get("duration", 1.0)), duration),
            )
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            if track_id == "A2":
                self.inspector_panel.set_take_audio(path.stem, path)
            self._show_status(f"Placed {path.name} on {track_id}")

        def _on_media_duration_resolved(self, duration: float) -> None:
            if not self._current_project_data.get("file_path"):
                return
            clips = [
                (item[0], item[1], duration, item[3], item[4])
                if item[0] in {"V1", "A1"} and float(item[1]) == 0.0
                else item
                for item in self._current_project_data.get("clips", [])
            ]
            self._current_project_data["duration"] = duration
            self._current_project_data["clips"] = clips
            self.canvas_view.set_clips(clips, duration)

        def _on_timeline_clip_clicked(self, clip_info: dict) -> None:
            lbl = clip_info.get("label", "")
            tid = clip_info.get("tid", "")
            self._active_clip_info = clip_info
            self.clip_selected.emit(clip_info)
            char_name = self._current_project_data.get("character", "")
            start = float(clip_info.get("start", 0.0))
            duration = float(clip_info.get("dur", 0.0))
            score = clip_info.get("score")
            self.monitor_panel.set_playhead(start)
            self.canvas_view.set_playhead(start)
            if tid.startswith("S"):
                if tid == "S1":
                    orig = lbl
                    trans = self._current_project_data.get("translation_text", "")
                else:
                    orig = self._current_project_data.get("original_text", "")
                    trans = lbl
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    duration,
                    duration,
                    score,
                )
                self._show_status(f"Selected Subtitle Clip [{tid}]: '{lbl}'")
            elif tid == "A2":
                orig = self._current_project_data.get("original_text", "")
                trans = self._current_project_data.get("translation_text", "")
                source_duration = self._nearest_source_duration(start, duration)
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    source_duration,
                    duration,
                    score,
                )
                self.inspector_panel.take_combo.setCurrentText(lbl.replace(" ★", ""))
                self._show_status(f"Selected Dub Audio Clip [{tid}]: '{lbl}'")

        def _nearest_source_duration(self, start: float, fallback: float) -> float:
            source_clips = [
                clip
                for clip in self._current_project_data.get("clips", [])
                if clip[0] in {"S1", "A1"}
            ]
            if not source_clips:
                return fallback
            nearest = min(source_clips, key=lambda clip: abs(float(clip[1]) - start))
            return float(nearest[2])

        def _on_translation_changed(self, text: str) -> None:
            self._current_project_data["translation_text"] = text

        def _on_ai_action_clicked(self, action_name: str) -> None:
            if action_name == "Regenerate Voice":
                self._on_ai_regenerate_voice()
            elif action_name == "Match Timing":
                self._apply_timing_fix()
            elif action_name in {"Rewrite Translation", "Shorten Translation"}:
                self._run_translation_assistant(shorten=action_name.startswith("Shorten"))
            elif action_name == "Properties":
                proj_name = self._current_project_data.get("name", "Current Project")
                m_name = self._current_project_data.get("movie_name", "Video")
                report = self._automation_state.quality_report
                quality = (
                    f"{report.overall_score * 100:.1f}% ({'PASS' if report.passed else 'REVIEW'})"
                    if report is not None
                    else "Not evaluated"
                )
                QMessageBox.information(
                    self,
                    "Production Properties",
                    (
                        f"Project: {proj_name}\n"
                        f"Source Media: {m_name}\n"
                        f"Target: {self._automation_state.target_language}\n"
                        f"Automation: {self._automation_state.progress}%\n"
                        f"Quality Gate: {quality}\n"
                        f"Session: {self._session_store.path_for(str(proj_name))}"
                    ),
                )
            else:
                self._show_status(f"AI Action queued: {action_name}")

        def _on_ai_regenerate_voice(self) -> None:
            if self._tts_worker is not None and self._tts_worker.isRunning():
                self._show_status("Voice synthesis is already running")
                return
            text = self.inspector_panel.trans_in.text().strip()
            if not text:
                self._show_status("Enter a translated dialogue line before synthesis")
                return
            from aidub.ui.workers import TTSPreviewWorker  # noqa: PLC0415

            preview_dir = self._session_store.workspace / "previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            output = preview_dir / f"take_{len(self._current_project_data.get('clips', [])) + 1:04d}.mp3"
            self._tts_worker = TTSPreviewWorker(text, output_file=output, parent=self)
            self._tts_worker.synthesis_completed.connect(self._on_voice_take_ready)
            self._tts_worker.synthesis_failed.connect(
                lambda error: self._show_status(f"Voice synthesis failed: {error}")
            )
            self._tts_worker.finished.connect(lambda: setattr(self, "_tts_worker", None))
            self._show_status("Neural voice synthesis started in a background worker…")
            self._tts_worker.start()

        def _on_voice_take_ready(self, output_path: str) -> None:
            clip = self._active_clip_info or {}
            start = float(clip.get("start", 0.0))
            duration = float(clip.get("dur", 1.0))
            clips = list(self._current_project_data.get("clips", []))
            take_number = 1 + sum(1 for item in clips if item[0] == "A2")
            take_name = f"Take {take_number}"
            clips.append(("A2", start, duration, take_name, None))
            self._current_project_data["clips"] = clips
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (
                output_path,
            )
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_clips(
                clips,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self.inspector_panel.set_take_audio(take_name, output_path)
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            self._show_status(f"Voice take synthesized: {output_path}")

        def _run_translation_assistant(self, *, shorten: bool) -> None:
            if self._assistant_worker is not None and self._assistant_worker.isRunning():
                self._show_status("Translation agent is already processing a request")
                return
            source = self.inspector_panel.orig_in.text().strip()
            current = self.inspector_panel.trans_in.text().strip()
            if not source:
                self._show_status("Select a dialogue segment before rewriting")
                return
            from aidub.ui.workers import AIAssistantWorker  # noqa: PLC0415

            instruction = (
                "Shorten this localized dialogue by about 15% while preserving meaning and character tone."
                if shorten
                else "Rewrite this localized dialogue naturally for screen performance and lip timing."
            )
            prompt = (
                f"{instruction}\nSource: {source}\nCurrent translation: {current}\n"
                f"Target language: {self._automation_state.target_language}\n"
                "Return only the revised spoken dialogue, without quotes or explanation."
            )
            self._assistant_worker = AIAssistantWorker(
                prompt,
                "You are a senior film localization dialogue director.",
                self,
            )
            self._assistant_worker.response_received.connect(self._on_translation_rewritten)
            self._assistant_worker.request_failed.connect(
                lambda error: self._show_status(f"Translation agent unavailable: {error}")
            )
            self._assistant_worker.finished.connect(
                lambda: setattr(self, "_assistant_worker", None)
            )
            self._show_status("Translation agent is rewriting the selected line…")
            self._assistant_worker.start()

        def _on_translation_rewritten(self, text: str) -> None:
            cleaned = text.strip()
            try:
                payload = json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                payload = None
            if isinstance(payload, dict):
                cleaned = str(
                    payload.get("translated_text")
                    or payload.get("translated")
                    or payload.get("text")
                    or ""
                ).strip()
            else:
                cleaned = cleaned.strip('"')
            if cleaned:
                self.inspector_panel.trans_in.setText(cleaned)
                self._show_status("Translation revision applied; voice and timing are now stale")

        def _apply_timing_fix(self) -> None:
            if self._active_clip_info is None:
                self._show_status("Select a dub take before matching timing")
                return
            source_duration = self._nearest_source_duration(
                float(self._active_clip_info.get("start", 0.0)),
                float(self._active_clip_info.get("dur", 0.0)),
            )
            self._active_clip_info["dur"] = source_duration
            self.inspector_panel.update_clip_info(
                self.inspector_panel.orig_in.text(),
                self.inspector_panel.trans_in.text(),
                self.inspector_panel.char_in.text(),
                self.inspector_panel.lang_in.text(),
                source_duration,
                source_duration,
                self._active_clip_info.get("score"),
            )
            self._show_status("Timing conformed to the source editorial slot")

        def _run_agentic_dub(self) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                return
            input_path = Path(str(self._current_project_data.get("file_path", "")))
            if not input_path.is_file():
                selected, _selected_filter = QFileDialog.getOpenFileName(
                    self,
                    "Select Source Movie for Automated Dubbing",
                    "",
                    "Movie Files (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
                )
                if not selected:
                    return
                input_path = Path(selected)
                self.load_project_data(
                    {
                        "name": self._current_project_data.get("name", input_path.stem),
                        "file_path": str(input_path),
                        "target_language": self._automation_state.target_language,
                        "quality_profile": self._automation_state.quality_profile,
                    }
                )

            from aidub.ui.workers import DubbingEngineWorker  # noqa: PLC0415

            self._automation_state = create_automation_plan(
                str(self._current_project_data.get("name", input_path.stem)),
                source_path=str(input_path.resolve()),
                target_language=self._automation_state.target_language,
                quality_profile=self._automation_state.quality_profile,
            )
            self.inspector_panel.clear_quality_report()
            self.ai_overlay.set_state(self._automation_state)
            self._persist_automation_state()
            self._dubbing_worker = DubbingEngineWorker(
                input_path,
                self._automation_state.target_language,
                self._automation_state.quality_profile,
                self,
            )
            self._dubbing_worker.progress_updated.connect(self._on_dubbing_progress)
            self._dubbing_worker.dubbing_completed.connect(self._on_dubbing_completed)
            self._dubbing_worker.dubbing_failed.connect(self._on_dubbing_failed)
            self._dubbing_worker.dubbing_cancelled.connect(self._on_dubbing_cancelled)
            self._dubbing_worker.finished.connect(lambda: setattr(self, "_dubbing_worker", None))
            self.ai_overlay.set_progress("Preparing autonomous production graph…", 1)
            self._show_status("Agentic dubbing job started · background execution enabled")
            self._dubbing_worker.start()

        def _cancel_agentic_dub(self) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                self._dubbing_worker.cancel()
                self._show_status("Cancellation requested · waiting for a safe stage boundary")

        @staticmethod
        def _automation_stage_for_percent(percent: int) -> AutomationStage:
            if percent < 13:
                return AutomationStage.INGEST
            if percent < 24:
                return AutomationStage.AUDIO_SEPARATION
            if percent < 33:
                return AutomationStage.SPEAKER_ANALYSIS
            if percent < 46:
                return AutomationStage.TRANSCRIPTION
            if percent < 59:
                return AutomationStage.TRANSLATION
            if percent < 75:
                return AutomationStage.SYNTHESIS
            if percent < 85:
                return AutomationStage.TIMING
            if percent < 93:
                return AutomationStage.MIX
            return AutomationStage.MASTER_EXPORT

        def _on_dubbing_progress(self, message: str, percent: int) -> None:
            current_stage = self._automation_stage_for_percent(percent)
            # Only advance stages that the automated engine actually executes.
            # Lip-sync and QC remain explicit gates instead of being marked complete
            # merely because the worker reached the mux phase.
            executed_stages = [
                AutomationStage.INGEST,
                AutomationStage.AUDIO_SEPARATION,
                AutomationStage.SPEAKER_ANALYSIS,
                AutomationStage.TRANSCRIPTION,
                AutomationStage.TRANSLATION,
                AutomationStage.VOICE_CASTING,
                AutomationStage.SYNTHESIS,
                AutomationStage.TIMING,
                AutomationStage.MIX,
                AutomationStage.MASTER_EXPORT,
            ]
            current_index = executed_stages.index(current_stage)
            state = self._automation_state
            for stage in executed_stages[:current_index]:
                stage_state = state.stage(stage)
                if stage_state.status not in {
                    StageStatus.SUCCEEDED,
                    StageStatus.SKIPPED,
                }:
                    state = state.update_stage(
                        stage,
                        status=StageStatus.SUCCEEDED,
                        progress=100,
                        detail="Completed by automation worker",
                    )
            if state.stage(current_stage).status is not StageStatus.SUCCEEDED:
                state = state.update_stage(
                    current_stage,
                    status=StageStatus.RUNNING,
                    progress=percent,
                    detail=message,
                )
            self._automation_state = state
            self._persist_automation_state()
            self.ai_overlay.set_progress(message, percent)
            self._show_status(f"Agent · {percent}% · {message}")

        def _on_dubbing_completed(self, result: dict[str, Any]) -> None:
            generated = tuple(
                value
                for key in ("output_file", "audio_file", "target_srt_file", "srt_file")
                if (value := str(result.get(key, "")))
            )
            self._current_project_data["generated_paths"] = generated
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Project")),
                str(self._current_project_data.get("movie_name", "source")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            target_srt = str(result.get("target_srt_file") or result.get("srt_file") or "")
            if target_srt and Path(target_srt).is_file():
                self.import_subtitle_file(target_srt, track_id="S2")

            state = self._automation_state
            for item in state.stages:
                if item.stage is AutomationStage.LIP_SYNC:
                    state = state.update_stage(
                        item.stage,
                        status=StageStatus.SKIPPED,
                        progress=100,
                        detail="Selective lip sync requires shot approval",
                    )
                elif item.stage is AutomationStage.QUALITY_CONTROL:
                    state = state.update_stage(
                        item.stage,
                        status=StageStatus.FAILED,
                        progress=100,
                        detail="No measured QC report is available; review required",
                    )
                elif item.status is not StageStatus.SUCCEEDED:
                    state = state.update_stage(
                        item.stage,
                        status=StageStatus.SUCCEEDED,
                        progress=100,
                        detail="Completed",
                    )
            self._automation_state = state
            self.inspector_panel.clear_quality_report()
            self._persist_automation_state()
            self.ai_overlay.set_state(state)
            self.ai_overlay.set_complete(
                "Localized master rendered · operator review ready",
                quality_passed=False,
            )
            self._show_status(f"Master created: {result.get('output_file', '')}")

        def _on_dubbing_failed(self, error: str) -> None:
            current = next(
                (
                    item
                    for item in self._automation_state.stages
                    if item.status is StageStatus.RUNNING
                ),
                None,
            )
            if current is not None:
                self._automation_state = self._automation_state.update_stage(
                    current.stage,
                    status=StageStatus.FAILED,
                    progress=current.progress,
                    detail=error,
                )
                self._persist_automation_state()
            self.ai_overlay.set_failed(f"Automation stopped · {error}")
            self._show_status(f"Dubbing job failed: {error}")

        def _on_dubbing_cancelled(self) -> None:
            self.ai_overlay.set_failed("Automation cancelled safely · revision preserved")
            self._show_status("Dubbing job cancelled; completed stage artifacts remain resumable")

        def _persist_automation_state(self) -> None:
            self.stage_bar.set_state(self._automation_state)
            if not self._current_project_data.get("file_path"):
                return
            try:
                self._session_store.save(self._automation_state)
            except OSError as exc:
                self._show_status(f"Session autosave warning: {exc}")

        def _autosave_session(self) -> None:
            self._persist_automation_state()
            if (
                self._current_project_data.get("file_path")
                and (self._dubbing_worker is None or not self._dubbing_worker.isRunning())
            ):
                self.status_msg_lbl.setText("● Session auto-saved · automation state is resumable")

        def _on_ai_fix_all(self) -> None:
            if self._active_clip_info is None:
                self._show_status("Select a dialogue or dubbed voice clip before Auto Fix")
                return
            self._apply_timing_fix()
            if self.inspector_panel.orig_in.text().strip():
                self._run_translation_assistant(shorten=False)

        def _compare_takes(self) -> None:
            takes = [
                (
                    self.inspector_panel.take_combo.itemText(index),
                    str(self.inspector_panel.take_combo.itemData(index) or ""),
                )
                for index in range(self.inspector_panel.take_combo.count())
                if self.inspector_panel.take_combo.itemData(index)
            ]
            if len(takes) < 2:
                self._show_status("Generate or import at least two voice takes to compare")
                return
            details = "\n".join(f"{name}: {path}" for name, path in takes)
            QMessageBox.information(self, "Generated Voice Takes", details)

        def _on_target_language_changed(self) -> None:
            language = self.inspector_panel.lang_in.text().strip()
            if not language or language == self._automation_state.target_language:
                return
            self._automation_state = create_automation_plan(
                str(self._current_project_data.get("name", "Untitled Studio")),
                source_path=str(self._current_project_data.get("file_path", "")),
                target_language=language,
                quality_profile=self._automation_state.quality_profile,
            )
            self.ai_overlay.set_state(self._automation_state)
            self._persist_automation_state()
            self._show_status(f"Target language changed to {language}; automation reset")

        def configure_target_language(self) -> None:
            language, accepted = QInputDialog.getText(
                self,
                "Target Language",
                "ISO language code or locale:",
                text=self._automation_state.target_language,
            )
            if accepted and language.strip():
                self.inspector_panel.lang_in.setText(language.strip())
                self._on_target_language_changed()

        def play_pause(self) -> None:
            self.monitor_panel._toggle_play()

        def step_backward(self) -> None:
            self.monitor_panel._on_step_back()

        def step_forward(self) -> None:
            self.monitor_panel._on_step_forward()

        def export_snapshot(self) -> None:
            self.monitor_panel._on_export_snapshot()

        def run_auto_dub(self) -> None:
            self._run_agentic_dub()

        def cancel_active_job(self) -> None:
            self._cancel_agentic_dub()

        def regenerate_selected_voice(self) -> None:
            self._on_ai_regenerate_voice()

        def match_selected_timing(self) -> None:
            self._apply_timing_fix()

        def rewrite_selected_translation(self, *, shorten: bool = False) -> None:
            self._run_translation_assistant(shorten=shorten)

        @property
        def current_project_name(self) -> str:
            return str(self._current_project_data.get("name", "Untitled Studio"))

        def _show_status(self, msg: str) -> None:
            self.status_msg_lbl.setText(msg)

        def has_active_job(self) -> bool:
            return self._dubbing_worker is not None and self._dubbing_worker.isRunning()


__all__ = ["TimelineScreen"]
