"""
Full NLE Timeline Editor Screen — Real Dynamic Project Data Engine.

Matches reference design pixel-for-pixel with zero hardcoded static locks:
  • Top Workspace Tabs Bar (Learning, Assembly, Editing, Dubbing [active], Color, Audio, Graphics, Libraries)
  • 3-Column Upper Panel:
      - Left Column: Project Media Browser with dynamic file tree (01_Source, 02_Generated, 03_Assets, 04_Proxies, 05_Stems)
      - Center Column: Program Video Monitor with live playhead, transport controls, cyan timecode overlay, resolution dropdowns
      - Right Column: Dialogue Inspector with Character, Original/Translation text, Timing & Scores cards, Take Selector, Waveform & dual vertical VU meter (-6 to -54 dB)
  • Lower Multi-track Timeline Panel (10 tracks V1-V3, A1-A5, S1-S2) with dynamic clip blocks, Bengali subtitle blocks, scrubbing playhead
  - Floating AI Actions panel with executable production commands
  - Editing status dock and a single timeline tool palette
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from aidub.application.agentic_studio import (
    AgenticStudioState,
    AutomationStage,
    StageStatus,
    StudioSessionStore,
    create_automation_plan,
)

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import (
        QLineF,
        QPointF,
        QRect,
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
        QImage,
        QMouseEvent,
        QPainter,
        QPen,
        QPixmap,
        QPolygonF,
        QWheelEvent,
    )
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSlider,
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

# ────────────────────────────────────────────────────────────────────────────
# Timeline Constants & Presets
# ────────────────────────────────────────────────────────────────────────────
TRACK_HEIGHT = 32
TRACK_HEADER_WIDTH = 218
RULER_HEIGHT = 30
MIN_CLIP_WIDTH = 6
PX_PER_SEC_DEFAULT = 78.0
NAV_RAIL_WIDTH = 168
TOOL_PALETTE_WIDTH = 82

type ClipTuple = tuple[str, float, float, str, float | None]

_TRACK_DEFS = [
    ("V3", "Video", "#3B82F6", "video"),
    ("V2", "Lip Sync", "#8B5CF6", "video"),
    ("V1", "Source Video", "#3B82F6", "video"),
    ("A1", "Source Audio", "#10B981", "audio"),
    ("A2", "Dubbed Voice", "#8B5CF6", "audio"),
    ("A3", "Music", "#06B6D4", "audio"),
    ("A4", "SFX", "#F97316", "audio"),
    ("A5", "Ambience", "#EAB308", "audio"),
    ("S1", "Source Subs", "#2563EB", "subtitle"),
    ("S2", "Target Subs", "#1E3A8A", "subtitle"),
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
    # Left Column: Filmora-Style 2-Column Media Browser Panel (Image 2)
    # ─────────────────────────────────────────────────────────────────────────
    class _MediaBrowserPanel(QFrame):
        media_selected = Signal(str)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._source_path = ""
            self._project_name = "Untitled"
            self.setStyleSheet("background:#0F1318;border-right:1px solid #1C222D;")

            root_layout = QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # =================================================================
            # Column 1: Filmora Categories Sidebar (Left, ~140px)
            # =================================================================
            cat_col = QFrame(self)
            cat_col.setFixedWidth(146)
            cat_col.setStyleSheet("background:#131720;border-right:1px solid #1E2532;")
            c_lay = QVBoxLayout(cat_col)
            c_lay.setContentsMargins(6, 10, 6, 10)
            c_lay.setSpacing(4)

            self._cat_buttons: list[QPushButton] = []
            categories = [
                ("Project Media", "1", True),
                ("Folder", "1", False),
                ("Shared Media", "0", False),
                ("Sample Colors", "25", False),
                ("Sample Video", "20", False),
                ("Sample Green Screen", "10", False),
            ]
            for cat_title, count_str, active in categories:
                c_btn = QPushButton(f"▾ 📁 {cat_title} ({count_str})", cat_col)
                c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                c_btn.setFixedHeight(28)
                if active:
                    c_btn.setStyleSheet(
                        "QPushButton{background:#232C3A;color:#2DD4BF;font-size:10px;font-weight:700;"
                        "text-align:left;padding-left:8px;border:none;border-radius:4px;}"
                    )
                else:
                    c_btn.setStyleSheet(
                        "QPushButton{background:transparent;color:#94A3B8;font-size:10px;font-weight:500;"
                        "text-align:left;padding-left:8px;border:none;border-radius:4px;}"
                        "QPushButton:hover{background:#1B212D;color:#E2E8F0;}"
                    )
                c_lay.addWidget(c_btn)
                self._cat_buttons.append(c_btn)

            c_lay.addStretch()

            # Bottom Folder Action Icons (Image 2)
            c_bottom = QHBoxLayout()
            c_bottom.setSpacing(4)
            add_folder_btn = QPushButton("📁+", cat_col)
            add_folder_btn.setFixedSize(26, 24)
            add_folder_btn.setToolTip("New Folder")
            add_folder_btn.setStyleSheet(
                "QPushButton{background:#1B212D;color:#94A3B8;border:1px solid #283344;border-radius:3px;font-size:10px;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            c_bottom.addWidget(add_folder_btn)

            del_folder_btn = QPushButton("🗑", cat_col)
            del_folder_btn.setFixedSize(26, 24)
            del_folder_btn.setToolTip("Delete Folder")
            del_folder_btn.setStyleSheet(
                "QPushButton{background:#1B212D;color:#94A3B8;border:1px solid #283344;border-radius:3px;font-size:10px;}"
                "QPushButton:hover{background:#EF4444;color:#FFF;}"
            )
            c_bottom.addWidget(del_folder_btn)
            c_bottom.addStretch()
            c_lay.addLayout(c_bottom)

            root_layout.addWidget(cat_col)

            # =================================================================
            # Column 2: Filmora Media Gallery (Right, Flexible)
            # =================================================================
            gallery_col = QFrame(self)
            gallery_col.setStyleSheet("background:#0E1116;")
            g_lay = QVBoxLayout(gallery_col)
            g_lay.setContentsMargins(10, 8, 10, 8)
            g_lay.setSpacing(8)

            # Top Action Row: Import ⌄ | Record ⌄ | Search | Filter
            act_row = QHBoxLayout()
            act_row.setSpacing(6)

            self.import_dropdown = QPushButton("Import ⌄", gallery_col)
            self.import_dropdown.setCursor(Qt.CursorShape.PointingHandCursor)
            self.import_dropdown.setFixedHeight(26)
            self.import_dropdown.setStyleSheet(
                "QPushButton{background:#1A202C;color:#F1F5F9;border:1px solid #2D3748;border-radius:4px;"
                "padding:2px 10px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#2B3545;border-color:#38BDF8;}"
            )
            self.import_dropdown.clicked.connect(self._on_import_menu_requested)
            act_row.addWidget(self.import_dropdown)

            self.record_dropdown = QPushButton("Record ⌄", gallery_col)
            self.record_dropdown.setCursor(Qt.CursorShape.PointingHandCursor)
            self.record_dropdown.setFixedHeight(26)
            self.record_dropdown.setStyleSheet(
                "QPushButton{background:#1A202C;color:#94A3B8;border:1px solid #2D3748;border-radius:4px;"
                "padding:2px 10px;font-size:11px;font-weight:600;}"
                "QPushButton:hover{background:#2B3545;color:#FFF;}"
            )
            act_row.addWidget(self.record_dropdown)

            act_row.addStretch()

            self.search_in = QLineEdit(gallery_col)
            self.search_in.setPlaceholderText("🔍 Search")
            self.search_in.setFixedWidth(130)
            self.search_in.setFixedHeight(24)
            self.search_in.setStyleSheet(
                "QLineEdit{background:#0B0E14;color:#F1F5F9;border:1px solid #232C3E;border-radius:3px;"
                "padding:2px 8px;font-size:10px;}QLineEdit:focus{border-color:#2DD4BF;}"
            )
            self.search_in.textChanged.connect(self._on_search_text_changed)
            act_row.addWidget(self.search_in)

            gear_btn = QPushButton("⚙", gallery_col)
            gear_btn.setFixedSize(24, 24)
            gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            gear_btn.setStyleSheet(
                "QPushButton{background:#161C26;color:#94A3B8;border:1px solid #232C3E;border-radius:3px;font-size:11px;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            gear_btn.clicked.connect(self._on_gear_clicked)
            act_row.addWidget(gear_btn)

            g_lay.addLayout(act_row)

            # Media Gallery Grid Container (Scrollable)
            gallery_scroll = QScrollArea(gallery_col)
            gallery_scroll.setWidgetResizable(True)
            gallery_scroll.setStyleSheet(
                "QScrollArea{background:#0B0E14;border:1px solid #1C222D;border-radius:6px;}"
                "QWidget#GalleryContent{background:#0B0E14;}"
            )

            self.gallery_widget = QWidget()
            self.gallery_widget.setObjectName("GalleryContent")
            self.grid_layout = QHBoxLayout(self.gallery_widget)
            self.grid_layout.setContentsMargins(12, 12, 12, 12)
            self.grid_layout.setSpacing(12)

            # Card 1: Filmora Dashed "+ Import Media" Card (Image 2)
            self.import_card = QFrame(self.gallery_widget)
            self.import_card.setFixedSize(130, 92)
            self.import_card.setCursor(Qt.CursorShape.PointingHandCursor)
            self.import_card.setStyleSheet(
                "QFrame{background:#11141A;border:1px dashed #2DD4BF;border-radius:6px;}"
                "QFrame:hover{background:#161D24;border-color:#5EEAD4;}"
            )
            ic_lay = QVBoxLayout(self.import_card)
            ic_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic_lay.setSpacing(4)
            ic_plus = QLabel("+", self.import_card)
            ic_plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic_plus.setStyleSheet("font-size:24px;font-weight:300;color:#2DD4BF;")
            ic_lbl = QLabel("Import Media", self.import_card)
            ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic_lbl.setStyleSheet("font-size:10px;font-weight:600;color:#E2E8F0;")
            ic_lay.addWidget(ic_plus)
            ic_lay.addWidget(ic_lbl)

            def _on_import_card_click(event: QMouseEvent) -> None:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._import_media()

            self.import_card.mousePressEvent = _on_import_card_click  # type: ignore[assignment]
            self.grid_layout.addWidget(self.import_card)

            # Card 2: Filmora Media Thumbnail Card (Image 2)
            self.media_thumb_card = QFrame(self.gallery_widget)
            self.media_thumb_card.setFixedSize(140, 92)
            self.media_thumb_card.setCursor(Qt.CursorShape.PointingHandCursor)
            self.media_thumb_card.setStyleSheet(
                "QFrame{background:#141923;border:2px solid #2DD4BF;border-radius:6px;}"
                "QFrame:hover{background:#1A212E;}"
            )
            mc_lay = QVBoxLayout(self.media_thumb_card)
            mc_lay.setContentsMargins(6, 6, 6, 6)
            mc_lay.setSpacing(3)

            mc_top = QHBoxLayout()
            mc_icon = QLabel("🎬", self.media_thumb_card)
            mc_icon.setStyleSheet("font-size:14px;")
            mc_top.addWidget(mc_icon)
            mc_top.addStretch()
            mc_badge = QLabel("🎞️", self.media_thumb_card)
            mc_badge.setStyleSheet("font-size:11px;color:#94A3B8;")
            mc_top.addWidget(mc_badge)
            mc_lay.addLayout(mc_top)

            self.media_title_lbl = QLabel("clip_2min.mp4", self.media_thumb_card)
            self.media_title_lbl.setStyleSheet("font-size:10px;font-weight:700;color:#F8FAFC;")
            self.media_title_lbl.setWordWrap(True)
            mc_lay.addWidget(self.media_title_lbl)

            self.media_dur_lbl = QLabel("02:00 • 1080p", self.media_thumb_card)
            self.media_dur_lbl.setStyleSheet("font-size:9px;color:#2DD4BF;font-weight:600;")
            mc_lay.addWidget(self.media_dur_lbl)

            def _on_thumb_click(event: QMouseEvent) -> None:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self._source_path:
                        self.media_selected.emit(self._source_path)

            self.media_thumb_card.mousePressEvent = _on_thumb_click  # type: ignore[assignment]
            self.grid_layout.addWidget(self.media_thumb_card)

            self.grid_layout.addStretch()
            gallery_scroll.setWidget(self.gallery_widget)
            g_lay.addWidget(gallery_scroll, 1)

            # Hidden compatibility QTreeWidget so existing tree APIs continue working 100%
            self.tree = QTreeWidget(self)
            self.tree.setHeaderLabels(["Name", "Type"])
            self.tree.setVisible(False)
            self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
            self.tree.itemClicked.connect(self._on_item_clicked)
            g_lay.addWidget(self.tree)

            # Backward-compatibility labels
            self.proj_tab = QLabel("Project: Untitled", self)
            self.proj_tab.setVisible(False)
            self.proj_file_lbl = QLabel("", self)
            self.proj_file_lbl.setVisible(False)
            self.count_lbl = QLabel("1", self)
            self.count_lbl.setVisible(False)

            root_layout.addWidget(gallery_col, 1)

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

            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 7, 8, 5)
            layout.setSpacing(5)

            # Header Tabs matching Image 1
            hdr = QHBoxLayout()
            self.prog_title_lbl = QLabel("Program: No Scene", self)
            self.prog_title_lbl.setStyleSheet(
                "font-size:11px;font-weight:600;color:#F2F3F5;padding:4px 0;"
                "border-bottom:2px solid #268DE4;"
            )
            hdr.addWidget(self.prog_title_lbl)

            self.source_lbl = QLabel("Source: none", self)
            self.source_lbl.setStyleSheet("font-size:11px;color:#868B94;padding:4px 8px;")
            hdr.addWidget(self.source_lbl)

            hdr.addStretch()
            layout.addLayout(hdr)

            # Video Canvas Frame
            video_frame = QFrame(self)
            video_frame.setStyleSheet("background:#050607;border:none;border-radius:0;")
            video_frame.setMinimumHeight(220)
            vf_lay = QVBoxLayout(video_frame)
            vf_lay.setContentsMargins(0, 0, 0, 0)

            # Top overlay inside video
            v_top = QHBoxLayout()
            self.tc_overlay = QLabel("00:00:00:000", video_frame)
            self.tc_overlay.setStyleSheet(
                "font-family:'Cascadia Mono';font-size:13px;font-weight:700;color:#269BEF;"
                "background:transparent;padding:3px 4px;"
            )
            v_top.addWidget(self.tc_overlay)

            v_top.addStretch()

            fit_combo = QComboBox(video_frame)
            fit_combo.addItems(["Fit", "50%", "100%", "200%"])
            fit_combo.setFixedWidth(74)
            fit_combo.setStyleSheet(
                "QComboBox{background:#111317;color:#E7E9ED;border:1px solid #22262C;"
                "padding:2px 6px;border-radius:2px;font-size:11px;min-height:20px;}"
            )
            self._fit_combo = fit_combo
            fit_combo.currentTextChanged.connect(lambda _value: self._update_video_surface())
            v_top.addWidget(fit_combo)

            split_btn = QPushButton("⚖️ Split View", video_frame)
            split_btn.setCheckable(True)
            split_btn.setFixedHeight(22)
            split_btn.setToolTip("Toggle Before/After Split-Screen Lip-Sync Comparison")
            split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            split_btn.setStyleSheet(
                "QPushButton{background:#111622;color:#94A3B8;border:1px solid #1E293B;"
                "border-radius:2px;font-size:11px;padding:2px 8px;min-height:0;}"
                "QPushButton:hover{background:#1E293B;color:#F8FAFC;}"
                "QPushButton:checked{background:#0369A1;color:#F0F9FF;border-color:#38BDF8;font-weight:700;}"
            )
            split_btn.toggled.connect(self._toggle_split_view)
            self._split_btn = split_btn
            v_top.addWidget(split_btn)

            self.dur_overlay = QLabel("00:00:00:000", video_frame)
            self.dur_overlay.setStyleSheet(
                "font-family:'Cascadia Mono';font-size:12px;color:#AEB3BC;"
                "background:transparent;padding:3px 4px;"
            )
            v_top.addWidget(self.dur_overlay)

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

            vf_lay.addWidget(self.media_stack, stretch=1)

            layout.addWidget(video_frame, stretch=1)
            layout.addLayout(v_top)

            scrub_row = QHBoxLayout()
            scrub_row.setContentsMargins(2, 0, 2, 0)
            self.scrubber = QSlider(Qt.Orientation.Horizontal, self)
            self.scrubber.setRange(0, 0)
            self.scrubber.setTracking(True)
            self.scrubber.setFixedHeight(18)
            self.scrubber.setStyleSheet(
                "QSlider::groove:horizontal{height:3px;background:#272B31;}"
                "QSlider::sub-page:horizontal{background:#555B64;}"
                "QSlider::handle:horizontal{background:#9FA5AE;border:1px solid #090A0C;"
                "width:9px;height:9px;margin:-4px 0;border-radius:5px;}"
            )
            self.scrubber.sliderMoved.connect(self._on_scrubber_moved)
            scrub_row.addWidget(self.scrubber)
            layout.addLayout(scrub_row)

            # Transport controls operate directly on QMediaPlayer.
            t_bar = QHBoxLayout()
            t_bar.setSpacing(12)
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
                is_play = sym == "▶"
                if is_play:
                    self.play_btn = b
                b.setStyleSheet(
                    "QPushButton{background:transparent;color:#AEB3BB;border:none;"
                    "border-radius:2px;font-size:13px;font-weight:700;padding:0;min-height:0;}"
                    "QPushButton:hover{background:#25292F;color:#FFF;}"
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
            if self._video_widget is None or self._last_video_image is None:
                return
            widget_size = self._video_widget.size()
            if widget_size.width() <= 1 or widget_size.height() <= 1:
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
                pixmap = QPixmap.fromImage(self._last_video_image)

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
        fit_to_slot_requested = Signal()
        nudge_timing_requested = Signal(float)

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
            p0_lay.setContentsMargins(0, 0, 4, 4)
            p0_lay.setSpacing(8)

            d_frame = QFrame(p0)
            d_frame.setObjectName("InspectorCard")
            d_frame.setMinimumHeight(170)
            d_frame.setStyleSheet(
                "QFrame#InspectorCard{background:#0D0F12;border:1px solid #262A30;"
                "border-radius:4px;padding:6px;}"
            )
            d_lay = QFormLayout(d_frame)
            d_lay.setContentsMargins(8, 8, 8, 8)
            d_lay.setVerticalSpacing(8)
            d_lay.setHorizontalSpacing(8)

            def form_label(text: str) -> QLabel:
                label = QLabel(text, d_frame)
                label.setStyleSheet("color:#B8BDC6;font-size:11px;background:transparent;")
                return label

            # Character Row: editable QComboBox + Manage button
            char_row = QHBoxLayout()
            char_row.setSpacing(4)
            self.char_in = QComboBox(d_frame)
            self.char_in.setEditable(True)
            self.char_in.setPlaceholderText("Select or type speaker / character")
            self.char_in.addItems(["SPEAKER_00", "SPEAKER_01", "Narrator"])
            self.char_in.setStyleSheet(
                input_style
                + "QComboBox QAbstractItemView{background:#111722;color:#F7F9FC;selection-background-color:#2563EB;}"
            )
            self.char_in.currentTextChanged.connect(self._on_char_changed)
            char_row.addWidget(self.char_in, stretch=1)

            self.btn_manage_chars = QPushButton("👥", d_frame)
            self.btn_manage_chars.setToolTip("Manage Characters & Speaker Voices…")
            self.btn_manage_chars.setFixedSize(26, 26)
            self.btn_manage_chars.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_manage_chars.setStyleSheet(
                "QPushButton{background:#1E293B;color:#93C5FD;border:1px solid #3B82F6;border-radius:4px;font-size:11px;padding:0;min-height:0;}"
                "QPushButton:hover{background:#2563EB;color:#FFF;}"
            )
            self.btn_manage_chars.clicked.connect(self.manage_characters_requested.emit)
            char_row.addWidget(self.btn_manage_chars)
            d_lay.addRow(form_label("Character"), char_row)

            # Language Row
            self.lang_in = QLineEdit(d_frame)
            self.lang_in.setPlaceholderText("Target language code")
            self.lang_in.setStyleSheet(input_style)
            d_lay.addRow(form_label("Language"), self.lang_in)

            # Original Dialogue Row: QLineEdit + Import Source SRT button
            orig_row = QHBoxLayout()
            orig_row.setSpacing(4)
            self.orig_in = QLineEdit(d_frame)
            self.orig_in.setPlaceholderText("Select or import source dialogue")
            self.orig_in.setStyleSheet(input_style)
            self.orig_in.textChanged.connect(self._on_orig_changed)
            orig_row.addWidget(self.orig_in, stretch=1)

            self.btn_import_orig_srt = QPushButton("📂", d_frame)
            self.btn_import_orig_srt.setToolTip("Import Source Subtitles (SRT/VTT) into S1…")
            self.btn_import_orig_srt.setFixedSize(26, 26)
            self.btn_import_orig_srt.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_import_orig_srt.setStyleSheet(btn_action_style)
            self.btn_import_orig_srt.clicked.connect(self.import_source_srt_requested.emit)
            orig_row.addWidget(self.btn_import_orig_srt)
            d_lay.addRow(form_label("Original"), orig_row)

            # Translation Dialogue Row: QLineEdit + Import Target SRT button
            trans_row = QHBoxLayout()
            trans_row.setSpacing(4)
            self.trans_in = QLineEdit(d_frame)
            self.trans_in.setPlaceholderText("Translation appears after processing")
            self.trans_in.setStyleSheet(trans_style)
            self.trans_in.textChanged.connect(self._on_trans_changed)
            trans_row.addWidget(self.trans_in, stretch=1)

            self.btn_import_trans_srt = QPushButton("📂", d_frame)
            self.btn_import_trans_srt.setToolTip("Import Target Subtitles (SRT/VTT) into S2…")
            self.btn_import_trans_srt.setFixedSize(26, 26)
            self.btn_import_trans_srt.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_import_trans_srt.setStyleSheet(
                "QPushButton{background:#1E293B;color:#22D3EE;border:1px solid #0891B2;border-radius:4px;font-size:11px;padding:0;min-height:0;}"
                "QPushButton:hover{background:#0891B2;color:#FFF;}"
            )
            self.btn_import_trans_srt.clicked.connect(self.import_target_srt_requested.emit)
            trans_row.addWidget(self.btn_import_trans_srt)
            d_lay.addRow(form_label("Translation"), trans_row)

            p0_lay.addWidget(d_frame)

            # Dual Cards: Timing & Scores
            cards_row = QHBoxLayout()
            cards_row.setSpacing(6)

            # Timing Card
            t_card = QFrame(p0)
            t_card.setObjectName("InspectorTimingCard")
            t_card.setStyleSheet(
                "QFrame#InspectorTimingCard{background:#0D0F12;border:1px solid #262A30;"
                "border-radius:4px;padding:6px;}"
            )
            tc_lay = QVBoxLayout(t_card)
            tc_lay.setContentsMargins(6, 6, 6, 6)
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
            s_card = QFrame(p0)
            s_card.setObjectName("InspectorScoresCard")
            s_card.setStyleSheet(
                "QFrame#InspectorScoresCard{background:#0D0F12;border:1px solid #262A30;"
                "border-radius:4px;padding:6px;}"
            )
            sc_lay = QVBoxLayout(s_card)
            sc_lay.setContentsMargins(6, 6, 6, 6)
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

            p0_lay.addLayout(cards_row)

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

            self.lang_in.setText(lang)

            self.orig_in.blockSignals(True)
            self.orig_in.setText(orig_text)
            self.orig_in.blockSignals(False)

            self.trans_in.blockSignals(True)
            self.trans_in.setText(trans_text)
            self.trans_in.blockSignals(False)

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
    class _TimelineCanvasView(QGraphicsView):
        timecode_changed = Signal(float)
        clip_clicked = Signal(dict)
        clips_edited = Signal(object)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setScene(QGraphicsScene(self))
            self._duration_sec = 1.0
            self._px_per_sec = PX_PER_SEC_DEFAULT
            self._playhead_sec = 0.0
            self._clip_items: list[tuple[dict[str, Any], QGraphicsRectItem, QGraphicsTextItem]] = []
            self._clips_data: list[ClipTuple] = []
            self._selected_rect: QGraphicsRectItem | None = None
            self._selected_rects: list[QGraphicsRectItem] = []
            self._markers: list[float] = []
            self._snapping_enabled = True
            self._linked_selection_enabled = True
            self._locked_tracks: set[str] = set()
            self._hidden_tracks: set[str] = set()
            self._video_thumbnail: QPixmap | None = None
            self._active_tool = "Select"
            self._drag_mode: str | None = None
            self._active_drag_clip: dict[str, Any] | None = None
            self._drag_start_pt: Any | None = None
            self._drag_orig_start: float = 0.0
            self._drag_orig_dur: float = 0.0
            self._drag_has_modified: bool = False
            self.setMouseTracking(True)
            self.setStyleSheet("QGraphicsView{background:#0D1118;border:none;}")
            self.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.set_clips([], 1.0)

        def set_tool(self, tool_name: str) -> None:
            if tool_name in {"Zoom In", "Zoom Out"}:
                factor = 1.15 if tool_name == "Zoom In" else 1 / 1.15
                target = max(0.55, min(3.5, self.transform().m11() * factor))
                self.resetTransform()
                self.scale(target, 1.0)
                return
            self._active_tool = tool_name
            if tool_name == "Hand":
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                cursor = (
                    Qt.CursorShape.CrossCursor
                    if tool_name in {"Razor", "Pen", "Text"}
                    else Qt.CursorShape.ArrowCursor
                )
                self.setCursor(cursor)

        def set_snapping_enabled(self, enabled: bool) -> None:
            self._snapping_enabled = enabled

        def set_linked_selection_enabled(self, enabled: bool) -> None:
            self._linked_selection_enabled = enabled

        def set_track_locked(self, tid: str, locked: bool) -> None:
            if locked:
                self._locked_tracks.add(tid)
            else:
                self._locked_tracks.discard(tid)

        def set_track_visible(self, tid: str, visible: bool) -> None:
            if visible:
                self._hidden_tracks.discard(tid)
            else:
                self._hidden_tracks.add(tid)
            for c_info, rect, txt_item in self._clip_items:
                if c_info.get("tid") == tid:
                    rect.setOpacity(1.0 if visible else 0.25)
                    txt_item.setOpacity(1.0 if visible else 0.25)

        def add_marker(self, seconds: float) -> bool:
            marker = max(0.0, min(self._duration_sec, float(seconds)))
            if any(abs(existing - marker) < 0.05 for existing in self._markers):
                return False
            self._markers.append(marker)
            self._markers.sort()
            self._build_scene()
            return True

        def clear_markers(self) -> None:
            self._markers.clear()
            self._build_scene()

        def _snap_time(self, seconds: float) -> float:
            value = max(0.0, min(self._duration_sec, seconds))
            if not self._snapping_enabled:
                return value
            zoom = max(0.1, self.transform().m11())
            tolerance = 8.0 / (self._px_per_sec * zoom)
            snap_points = [*self._markers]
            for clip in self._clips_data:
                snap_points.extend((float(clip[1]), float(clip[1]) + float(clip[2])))
            nearest = min(snap_points, key=lambda point: abs(point - value), default=value)
            return nearest if abs(nearest - value) <= tolerance else value

        def set_clips(self, clips_list: list[ClipTuple], duration_sec: float = 10.0) -> None:
            self._clips_data = list(clips_list)
            self._duration_sec = max(1.0, duration_sec)
            if self._duration_sec <= 60.0:
                self._px_per_sec = PX_PER_SEC_DEFAULT
            else:
                self._px_per_sec = max(0.5, min(PX_PER_SEC_DEFAULT, 3600.0 / self._duration_sec))
            self._build_scene()

        def set_playhead(self, sec: float) -> None:
            self._playhead_sec = max(0.0, min(self._duration_sec, sec))
            if hasattr(self, "_playhead_bar") and self._playhead_bar:
                ph_x = self._playhead_sec * self._px_per_sec
                h = RULER_HEIGHT + len(_TRACK_DEFS) * TRACK_HEIGHT + 20
                self._playhead_bar.setRect(QRectF(ph_x, 0, 2, h))
                if hasattr(self, "_playhead_handle") and self._playhead_handle:
                    polygon = QPolygonF(
                        [QPointF(ph_x - 6, 0), QPointF(ph_x + 8, 0), QPointF(ph_x + 1, 10)]
                    )
                    self._playhead_handle.setPolygon(polygon)

        def set_video_thumbnail(self, image: Any) -> None:
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return
            self._video_thumbnail = pixmap
            self._build_scene()

        def clear_video_thumbnail(self) -> None:
            self._video_thumbnail = None

        def update_subtitle_text(self, text: str, start_sec: float | None = None) -> None:
            for c_info, rect, txt_item in self._clip_items:
                if c_info.get("tid") == "S2" and (
                    start_sec is None or abs(float(c_info["start"]) - start_sec) < 0.001
                ):
                    txt_item.setPlainText(text)

        def _build_scene(self) -> None:
            sc = self.scene()
            sc.clear()
            self._clip_items.clear()
            self._selected_rect = None
            self._selected_rects.clear()

            w = self._duration_sec * self._px_per_sec + 200
            h = RULER_HEIGHT + len(_TRACK_DEFS) * TRACK_HEIGHT + 20
            sc.setSceneRect(0, 0, w, h)

            # Ruler
            sc.addRect(
                QRectF(0, 0, w, RULER_HEIGHT), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#080B10"))
            )
            sc.addLine(QLineF(0, RULER_HEIGHT, w, RULER_HEIGHT), QPen(QColor("#1E2838"), 1))

            # Ruler Timecodes: Ensure tick spacing is at least 80 pixels
            min_pixel_spacing = 80.0
            candidate_intervals = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1_800, 3_600, 7_200)
            tick_interval = next(
                (
                    interval
                    for interval in candidate_intervals
                    if interval * self._px_per_sec >= min_pixel_spacing
                ),
                3_600,
            )
            if tick_interval * self._px_per_sec < min_pixel_spacing:
                tick_interval = max(60, int(min_pixel_spacing / max(0.01, self._px_per_sec)))
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
                sc.addLine(
                    QLineF(0, y + TRACK_HEIGHT - 1, w, y + TRACK_HEIGHT - 1),
                    QPen(QColor("#161F2E"), 1),
                )

            # Render Clips
            track_y_map = {
                t[0]: RULER_HEIGHT + idx * TRACK_HEIGHT + 2 for idx, t in enumerate(_TRACK_DEFS)
            }
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
                is_audio = tid in {"A1", "A2", "A3", "A4", "A5"}
                is_sub = tid in {"S1", "S2"}

                # Modern rounded clip container (Reference Images 2, 3, 4)
                from PySide6.QtGui import QPainterPath

                clip_path = QPainterPath()
                clip_path.addRoundedRect(QRectF(x, cy, cw, ch), 5.0, 5.0)

                fill_col = QColor(c_color).darker(220)
                fill_col.setAlpha(220)
                clip_rect = sc.addPath(
                    clip_path,
                    QPen(QColor(c_color), 1.2),
                    QBrush(fill_col),
                )
                clip_rect.setData(0, tid)
                clip_rect.setToolTip(
                    f"{tid} · {label}\n{_format_tc(start)} → {_format_tc(start + dur)}"
                )

                # Render dynamic speech/audio waveform peaks inside audio clips (single path per clip)
                if is_audio and cw > 14:
                    import math

                    mid_y = cy + ch / 2.0
                    step_w = 4.0
                    n_bars = int(min(300.0, cw - 6) // step_w)
                    pen_wave = QPen(QColor(c_color).lighter(140), 1.5)
                    wave_path = QPainterPath()
                    for b_idx in range(n_bars):
                        bx = x + 3 + b_idx * step_w
                        norm = b_idx / max(1, n_bars)
                        env = math.sin(norm * math.pi) ** 0.6
                        burst = (
                            0.35
                            + 0.65 * math.sin(b_idx * 1.85 + start * 7.3) ** 2
                            + 0.15 * math.cos(b_idx * 3.1)
                        )
                        half_h = max(2.0, min((ch * 0.44), (ch * 0.42) * env * burst))
                        wave_path.moveTo(bx, mid_y - half_h)
                        wave_path.lineTo(bx, mid_y + half_h)
                    sc.addPath(wave_path, pen_wave)

                if tid == "V1" and self._video_thumbnail is not None:
                    thumbnail = self._video_thumbnail.scaledToHeight(
                        max(1, round(ch - 6)),
                        Qt.TransformationMode.FastTransformation,
                    )
                    thumb_x = x + 3
                    max_thumbs = 15
                    thumb_count = 0
                    thumbnail_limit = min(x + cw - 3, x + max(1_800, self.viewport().width() * 2))
                    step = max(
                        thumbnail.width() + 2,
                        int((thumbnail_limit - thumb_x) / max_thumbs)
                        if (thumbnail_limit - thumb_x) > max_thumbs * thumbnail.width()
                        else thumbnail.width() + 2,
                    )
                    step = max(1, step)
                    while thumb_x < thumbnail_limit and thumb_count < max_thumbs:
                        thumb_item = sc.addPixmap(thumbnail)
                        thumb_item.setPos(thumb_x, cy + 3)
                        thumb_item.setOpacity(0.72)
                        thumb_x += step
                        thumb_count += 1

                clip_title = f"💬 {label}" if is_sub else label
                txt = sc.addText(clip_title, QFont("Segoe UI Variable", 8, QFont.Weight.Bold))
                txt.setDefaultTextColor(QColor("#FFFFFF" if is_sub else "#F7F9FC"))
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

            # Timeline markers
            for index, marker in enumerate(self._markers, start=1):
                x = marker * self._px_per_sec
                marker_line = sc.addLine(QLineF(x, RULER_HEIGHT, x, h), QPen(QColor("#EAB308"), 1))
                marker_line.setToolTip(f"Marker {index} · {_format_tc(marker)}")
                marker_label = sc.addText(f"M{index}", QFont("Cascadia Code", 7))
                marker_label.setDefaultTextColor(QColor("#FACC15"))
                marker_label.setPos(x + 2, RULER_HEIGHT + 1)

            # Playhead Bar
            ph_x = self._playhead_sec * self._px_per_sec
            self._playhead_bar = sc.addRect(
                QRectF(ph_x, 0, 2, h), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#FF6433"))
            )
            polygon = QPolygonF([QPointF(ph_x - 6, 0), QPointF(ph_x + 8, 0), QPointF(ph_x + 1, 10)])
            self._playhead_handle = sc.addPolygon(
                polygon, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#FF6433"))
            )

        def _get_clip_edge_at(self, pt: Any) -> tuple[dict[str, Any] | None, str | None]:
            edge_margin_px = 8.0
            for c_info, rect, _txt_item in self._clip_items:
                if c_info.get("tid") in self._locked_tracks:
                    continue
                r = rect.boundingRect()
                if r.contains(pt):
                    if abs(pt.x() - r.left()) <= edge_margin_px:
                        return c_info, "left"
                    if abs(pt.x() - r.right()) <= edge_margin_px:
                        return c_info, "right"
                    return c_info, "body"
            return None, None

        def _update_clip_timing(
            self, clip_info: dict[str, Any], new_start: float, new_dur: float
        ) -> None:
            old_start = float(clip_info["start"])
            tid = clip_info["tid"]
            label = clip_info["label"]

            updated: list[ClipTuple] = []
            matched = False
            for c in self._clips_data:
                if (
                    not matched
                    and c[0] == tid
                    and abs(float(c[1]) - old_start) < 0.001
                    and c[3] == label
                ):
                    score = c[4] if len(c) > 4 else None
                    updated.append((tid, round(new_start, 3), round(new_dur, 3), label, score))
                    matched = True
                else:
                    updated.append(c)
            self._clips_data = updated
            clip_info["start"] = round(new_start, 3)
            clip_info["dur"] = round(new_dur, 3)
            self._build_scene()

        def split_at_playhead(self) -> bool:
            """Split the clip under the playhead at the current playhead position."""
            ph = self._playhead_sec
            for c_info, _rect, _txt in self._clip_items:
                if c_info.get("tid") in self._locked_tracks:
                    continue
                start = float(c_info["start"])
                dur = float(c_info["dur"])
                if start + 0.05 < ph < (start + dur - 0.05):
                    return self._split_clip(c_info, ph)
            return False

        def delete_selected_clips(self) -> bool:
            """Delete currently selected clip(s) from the timeline."""
            if not self._selected_rects and not self._selected_rect:
                return False
            selected_infos: list[dict[str, Any]] = []
            for c_info, rect, _txt in self._clip_items:
                if rect in self._selected_rects or rect == self._selected_rect:
                    if c_info.get("tid") not in self._locked_tracks:
                        selected_infos.append(c_info)

            if not selected_infos:
                return False

            updated = [
                c
                for c in self._clips_data
                if not any(
                    c[0] == s["tid"]
                    and abs(float(c[1]) - float(s["start"])) < 0.001
                    and c[3] == s["label"]
                    for s in selected_infos
                )
            ]
            self._clips_data = updated
            self._selected_rect = None
            self._selected_rects.clear()
            self._build_scene()
            self.clips_edited.emit(list(self._clips_data))
            return True

        def keyPressEvent(self, event: Any) -> None:  # noqa: N802
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if self.delete_selected_clips():
                    event.accept()
                    return
            if (
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_B
            ):
                if self.split_at_playhead():
                    event.accept()
                    return
            super().keyPressEvent(event)

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            if self._active_tool == "Hand":
                super().mousePressEvent(event)
                return
            pt = self.mapToScene(
                event.position().toPoint() if hasattr(event, "position") else event.pos()
            )
            if pt.y() <= RULER_HEIGHT or (
                hasattr(self, "_playhead_bar")
                and abs(pt.x() - (self._playhead_sec * self._px_per_sec)) < 16
            ):
                self._is_dragging_playhead = True
                sec = max(0.0, min(self._duration_sec, self._snap_time(pt.x() / self._px_per_sec)))
                self.set_playhead(sec)
                self.timecode_changed.emit(self._playhead_sec)
                event.accept()
                return
            for c_info, rect, txt_item in self._clip_items:
                if rect.contains(pt):
                    if c_info.get("tid") in self._locked_tracks:
                        break
                    if self._active_tool == "Razor":
                        split_sec = max(
                            float(c_info["start"]),
                            min(
                                float(c_info["start"]) + float(c_info["dur"]),
                                self._snap_time(pt.x() / self._px_per_sec),
                            ),
                        )
                        if self._split_clip(c_info, split_sec):
                            event.accept()
                            return
                    elif self._active_tool == "Select":
                        _c, edge = self._get_clip_edge_at(pt)
                        if edge == "left":
                            self._drag_mode = "trim_left"
                            self._active_drag_clip = c_info
                            self._drag_start_pt = pt
                            self._drag_orig_start = float(c_info["start"])
                            self._drag_orig_dur = float(c_info["dur"])
                            self._drag_has_modified = False
                        elif edge == "right":
                            self._drag_mode = "trim_right"
                            self._active_drag_clip = c_info
                            self._drag_start_pt = pt
                            self._drag_orig_start = float(c_info["start"])
                            self._drag_orig_dur = float(c_info["dur"])
                            self._drag_has_modified = False
                        else:
                            self._drag_mode = "move"
                            self._active_drag_clip = c_info
                            self._drag_start_pt = pt
                            self._drag_orig_start = float(c_info["start"])
                            self._drag_orig_dur = float(c_info["dur"])
                            self._drag_has_modified = False

                    for selected in self._selected_rects:
                        old_color = next(
                            (row[2] for row in _TRACK_DEFS if row[0] == selected.data(0)),
                            "#3B82F6",
                        )
                        selected.setPen(QPen(QColor(old_color), 1))
                    related_tracks = {
                        "S1": {"S2", "A2"},
                        "S2": {"S1", "A2"},
                        "A2": {"S1", "S2"},
                    }
                    selected_items = [(c_info, rect)]
                    if self._linked_selection_enabled:
                        linked = related_tracks.get(str(c_info["tid"]), set())
                        selected_items.extend(
                            (other_info, other_rect)
                            for other_info, other_rect, _other_text in self._clip_items
                            if other_info["tid"] in linked
                            and abs(float(other_info["start"]) - float(c_info["start"])) < 0.05
                        )
                    self._selected_rects = [item_rect for _info, item_rect in selected_items]
                    for selected in self._selected_rects:
                        selected.setPen(QPen(QColor("#E2E8F0"), 2))
                    self._selected_rect = rect
                    self.clip_clicked.emit(c_info)
                    break
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
            pt = self.mapToScene(
                event.position().toPoint() if hasattr(event, "position") else event.pos()
            )
            if getattr(self, "_is_dragging_playhead", False):
                sec = max(0.0, min(self._duration_sec, self._snap_time(pt.x() / self._px_per_sec)))
                self.set_playhead(sec)
                self.timecode_changed.emit(self._playhead_sec)
                event.accept()
                return

            if self._drag_mode and self._active_drag_clip and self._drag_start_pt:
                delta_sec = (pt.x() - self._drag_start_pt.x()) / self._px_per_sec
                c_info = self._active_drag_clip
                tid = c_info["tid"]
                orig_start = self._drag_orig_start
                orig_dur = self._drag_orig_dur

                if self._drag_mode == "trim_left":
                    cand_start = self._snap_time(orig_start + delta_sec)
                    cand_start = min(cand_start, orig_start + orig_dur - 0.1)
                    cand_start = max(0.0, cand_start)
                    prev_end = max(
                        (
                            float(c[1]) + float(c[2])
                            for c in self._clips_data
                            if c[0] == tid and float(c[1]) < orig_start
                        ),
                        default=0.0,
                    )
                    cand_start = max(cand_start, prev_end)
                    new_dur = (orig_start + orig_dur) - cand_start
                    if (
                        abs(cand_start - float(c_info["start"])) > 0.001
                        or abs(new_dur - float(c_info["dur"])) > 0.001
                    ):
                        self._update_clip_timing(c_info, cand_start, new_dur)
                        self._drag_has_modified = True

                elif self._drag_mode == "trim_right":
                    cand_end = self._snap_time(orig_start + orig_dur + delta_sec)
                    cand_end = max(orig_start + 0.1, cand_end)
                    cand_end = min(self._duration_sec, cand_end)
                    next_start = min(
                        (
                            float(c[1])
                            for c in self._clips_data
                            if c[0] == tid and float(c[1]) > orig_start
                        ),
                        default=self._duration_sec,
                    )
                    cand_end = min(cand_end, next_start)
                    new_dur = cand_end - orig_start
                    if abs(new_dur - float(c_info["dur"])) > 0.001:
                        self._update_clip_timing(c_info, orig_start, new_dur)
                        self._drag_has_modified = True

                elif self._drag_mode == "move":
                    cand_start = self._snap_time(orig_start + delta_sec)
                    cand_start = max(0.0, min(self._duration_sec - orig_dur, cand_start))
                    cand_end = cand_start + orig_dur
                    overlap = any(
                        c[0] == tid
                        and (
                            float(c[1]) != orig_start
                            or float(c[2]) != orig_dur
                            or c[3] != c_info["label"]
                        )
                        and max(cand_start, float(c[1])) < min(cand_end, float(c[1]) + float(c[2]))
                        for c in self._clips_data
                    )
                    if not overlap and abs(cand_start - float(c_info["start"])) > 0.001:
                        self._update_clip_timing(c_info, cand_start, orig_dur)
                        self._drag_has_modified = True

                event.accept()
                return

            if self._active_tool == "Select":
                _clip, edge = self._get_clip_edge_at(pt)
                if edge in {"left", "right"}:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif edge == "body":
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)

            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
            self._is_dragging_playhead = False
            if self._drag_mode:
                if self._drag_has_modified:
                    self._build_scene()
                    self.clips_edited.emit(list(self._clips_data))
                self._drag_mode = None
                self._active_drag_clip = None
                self._drag_start_pt = None
                self._drag_has_modified = False
            super().mouseReleaseEvent(event)

        def _split_clip(self, clip_info: dict[str, Any], split_sec: float) -> bool:
            start = float(clip_info["start"])
            duration = float(clip_info["dur"])
            end = start + duration
            if split_sec <= start + 0.05 or split_sec >= end - 0.05:
                return False
            updated: list[ClipTuple] = []
            replaced = False
            for clip in self._clips_data:
                if (
                    not replaced
                    and clip[0] == clip_info["tid"]
                    and float(clip[1]) == start
                    and float(clip[2]) == duration
                    and clip[3] == clip_info["label"]
                ):
                    score = clip[4] if len(clip) > 4 else None
                    updated.append((clip[0], start, split_sec - start, clip[3], score))
                    updated.append((clip[0], split_sec, end - split_sec, clip[3], score))
                    replaced = True
                else:
                    updated.append(clip)
            if not replaced:
                return False
            self._clips_data = updated
            self._build_scene()
            self.clips_edited.emit(list(updated))
            return True

        def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
                current = self.transform().m11()
                if 0.55 <= current * factor <= 3.5:
                    self.scale(factor, 1.0)
                event.accept()
                return
            super().wheelEvent(event)

    class _StudioNavigationRail(QFrame):
        """Dense workflow rail occupying the lower-left reference column."""

        route_requested = Signal(str)

        _ROUTES = (("S", "Subtitles"),)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedWidth(NAV_RAIL_WIDTH)
            self.setStyleSheet("background:#111315;border-right:1px solid #08090B;")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(7, 19, 7, 7)
            layout.setSpacing(1)
            self._buttons: dict[str, QPushButton] = {}
            for icon, route in self._ROUTES:
                button = QPushButton(f"{icon}   {route}", self)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setFixedHeight(28)
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#B5BAC3;border:none;"
                    "border-radius:3px;text-align:left;padding:0 10px;font-size:11px;"
                    "font-weight:500;min-height:0;}"
                    "QPushButton:hover{background:#22262C;color:#FFF;}"
                    "QPushButton:checked{background:#155BA6;color:#FFF;font-weight:600;}"
                )
                button.clicked.connect(
                    lambda _checked=False, name=route: self.route_requested.emit(name)
                )
                layout.addWidget(button)
                self._buttons[route] = button
            layout.addStretch()
            models_button = QPushButton("◈   Pipeline Readiness", self)
            models_button.setFixedHeight(30)
            models_button.setCursor(Qt.CursorShape.PointingHandCursor)
            models_button.setStyleSheet(
                "QPushButton{background:#15181C;color:#B5BAC3;border:1px solid #23272D;"
                "border-radius:2px;text-align:left;padding:0 10px;font-size:10px;"
                "min-height:0;}QPushButton:hover{background:#22262C;color:#FFF;}"
            )
            models_button.clicked.connect(lambda: self.route_requested.emit("Pipeline Readiness"))
            layout.addWidget(models_button)

    class _TimelineToolPalette(QFrame):
        tool_selected = Signal(str)

        _TOOLS = (
            ("↖", "Select"),
            ("⌁", "Razor"),
            ("✋", "Hand"),
            ("＋", "Zoom In"),
            ("−", "Zoom Out"),
        )

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedWidth(TOOL_PALETTE_WIDTH)
            self.setStyleSheet("background:#101214;border-right:1px solid #08090B;")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 19, 8, 8)
            grid = QGridLayout()
            grid.setSpacing(4)
            self._buttons: dict[str, QPushButton] = {}
            for index, (icon, tool_name) in enumerate(self._TOOLS):
                button = QPushButton(icon, self)
                button.setCheckable(tool_name not in {"Zoom In", "Zoom Out"})
                button.setChecked(tool_name == "Select")
                button.setToolTip(tool_name)
                button.setFixedSize(29, 29)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setStyleSheet(
                    "QPushButton{background:transparent;color:#B5BAC3;border:none;"
                    "border-radius:2px;padding:0;font-size:14px;min-height:0;}"
                    "QPushButton:hover{background:#282C32;color:#FFF;}"
                    "QPushButton:checked{background:#1E6BB5;color:#FFF;}"
                )
                button.clicked.connect(lambda _checked=False, name=tool_name: self._activate(name))
                grid.addWidget(button, index // 2, index % 2)
                self._buttons[tool_name] = button
            layout.addLayout(grid)
            layout.addStretch()

        def _activate(self, tool_name: str) -> None:
            if tool_name not in {"Zoom In", "Zoom Out"}:
                for name, button in self._buttons.items():
                    if button.isCheckable():
                        button.setChecked(name == tool_name)
            self.tool_selected.emit(tool_name)

    class _TimelineEditorBar(QFrame):
        action_requested = Signal(str)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedHeight(40)
            self.setStyleSheet("QFrame{background:#11141A;border-bottom:1px solid #1E232F;}")
            layout = QHBoxLayout(self)
            layout.setContentsMargins(10, 0, 10, 0)
            layout.setSpacing(6)

            self.title_label = QLabel("Scene 001 - Untitled  ×", self)
            self.title_label.setStyleSheet(
                "font-size:11px;font-weight:600;color:#E2E8F0;"
                "border-bottom:2px solid #2DD4BF;padding:4px 4px;"
            )
            layout.addWidget(self.title_label)

            layout.addStretch()

            self.timecode_label = QLabel("00:00:00:00", self)
            self.timecode_label.setStyleSheet(
                "font:700 13px 'Cascadia Mono';color:#2DD4BF;background:#0B0E14;border:1px solid #1E2532;"
                "border-radius:4px;padding:2px 10px;"
            )
            layout.addWidget(self.timecode_label)

            for symbol, name in (
                ("🏷", "Add Marker"),
                ("⚙", "Timeline Settings"),
            ):
                button = QPushButton(symbol, self)
                button.setFixedSize(28, 28)
                button.setToolTip(name)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setStyleSheet(
                    "QPushButton{background:#181D26;color:#C4CAD4;border:1px solid #283141;border-radius:4px;font-size:13px;padding:0;}"
                    "QPushButton:hover{background:#232C3A;color:#2DD4BF;border-color:#2DD4BF;}"
                )
                button.clicked.connect(
                    lambda _checked=False, action=name: self.action_requested.emit(action)
                )
                layout.addWidget(button)

        def set_title(self, title: str) -> None:
            self.title_label.setText(f"Scene 001 - {title}  ×")

        def set_timecode(self, seconds: float) -> None:
            self.timecode_label.setText(_format_tc(seconds))

    # ─────────────────────────────────────────────────────────────────────────
    # Floating AI Actions Overlay Panel
    # ─────────────────────────────────────────────────────────────────────────
    class _FloatingAIActionsPanel(QFrame):
        action_clicked = Signal(str)
        run_requested = Signal()
        cancel_requested = Signal()

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("AiActionsPanel")
            self.setFixedWidth(190)
            self._busy = False
            self.setStyleSheet(
                "QFrame#AiActionsPanel {  background: #111315;  border-left: 1px solid #08090B;}"
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 0, 8, 8)
            layout.setSpacing(2)

            header = QHBoxLayout()
            hdr = QLabel("AI Actions", self)
            hdr.setFixedHeight(34)
            hdr.setStyleSheet("font-size:11px;font-weight:600;color:#E8EAEE;")
            header.addWidget(hdr)
            header.addStretch()
            self.status_badge = QLabel("", self)
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#64748B;")
            header.addWidget(self.status_badge)
            layout.addLayout(header)

            actions = [
                ("1", "Extract Dialogue Audio"),
                ("2", "Transcribe Speech (S1)"),
                ("3", "Translate Subtitles (S2)"),
                ("4", "Synthesize Voices (A2)"),
                ("5", "Render Master Video"),
                ("V", "Select Dub Voice"),
                ("E", "Improve Emotion"),
                ("A", "Audio Analysis"),
                ("T", "Match Timing"),
                ("R", "Rewrite Translation"),
                ("S", "Shorten Translation"),
                ("P", "Fix Pronunciation"),
                ("i", "Properties"),
            ]

            for icon, name in actions:
                btn = QPushButton(f"{icon}  {name}", self)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background:transparent;color:#C2C6CD;font-size:11px;text-align:left;"
                    "  border:none;padding:4px 6px;border-radius:2px;min-height:20px;"
                    "}"
                    "QPushButton:hover{background:#272B31;color:#FFF;}"
                )
                btn.clicked.connect(lambda _, n=name: self.action_clicked.emit(n))
                layout.addWidget(btn)

            layout.addStretch()

            self.stage_lbl = QLabel("Ready · dubbing pipeline", self)
            self.stage_lbl.setWordWrap(True)
            self.stage_lbl.setStyleSheet("font-size:9px;color:#A9B2C3;")
            self.stage_lbl.setVisible(False)
            layout.addWidget(self.stage_lbl)
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(4)
            self.progress_bar.setVisible(False)
            layout.addWidget(self.progress_bar)
            self.quality_lbl = QLabel("QUALITY GATE · NOT RUN", self)
            self.quality_lbl.setStyleSheet("font-size:8px;font-weight:800;color:#64748B;")
            self.quality_lbl.setVisible(False)
            layout.addWidget(self.quality_lbl)
            self.run_btn = QPushButton("✦  AUTO DUB MASTER", self)
            self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.run_btn.setVisible(True)
            self.run_btn.setToolTip(
                "Run the complete dubbing pipeline using the selected target language"
            )
            self.run_btn.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFF;border:1px solid #3B82F6;"
                "border-radius:5px;padding:5px;font-size:10px;font-weight:800;}"
                "QPushButton:hover{background:#3B82F6;}"
            )
            self.run_btn.clicked.connect(self._on_run_clicked)
            layout.addWidget(self.run_btn)

        def _on_run_clicked(self) -> None:
            if self._busy:
                self.cancel_requested.emit()
            else:
                self.run_requested.emit()

        def set_progress(self, message: str, percent: int) -> None:
            self._busy = percent < 100
            self.status_badge.setText("● RUNNING")
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#22D3EE;")
            self.stage_lbl.setVisible(True)
            self.progress_bar.setVisible(True)
            self.run_btn.setVisible(True)
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
            self.stage_lbl.setVisible(True)
            self.progress_bar.setVisible(True)
            self.quality_lbl.setVisible(True)
            self.run_btn.setVisible(True)
            self.stage_lbl.setText(message)
            self.run_btn.setText("↻  RUN NEW REVISION")
            if quality_passed is not None:
                self.quality_lbl.setText(f"QUALITY GATE · {'PASS' if quality_passed else 'REVIEW'}")
                color = "#22C55E" if quality_passed else "#F59E0B"
                self.quality_lbl.setStyleSheet(f"font-size:8px;font-weight:800;color:{color};")

        def set_failed(self, message: str) -> None:
            self._busy = False
            self.status_badge.setText("● STOPPED")
            self.status_badge.setStyleSheet("font-size:8px;font-weight:800;color:#EF4444;")
            self.stage_lbl.setText(message)
            self.stage_lbl.setVisible(True)
            self.progress_bar.setVisible(True)
            self.quality_lbl.setVisible(True)
            self.run_btn.setVisible(True)
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
                self.quality_lbl.setStyleSheet(f"font-size:8px;font-weight:800;color:{color};")

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline Header Track Panel
    # ─────────────────────────────────────────────────────────────────────────
    class _TimelineHeaderPanel(QFrame):
        track_lock_toggled = Signal(str, bool)
        track_visibility_toggled = Signal(str, bool)
        track_import_requested = Signal(str)

        def __init__(self, parent: QWidget | None = None) -> None:
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

                lock_btn = QPushButton("🔓", cell)
                lock_btn.setCheckable(True)
                lock_btn.setChecked(False)
                lock_btn.setFixedSize(22, 20)
                lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                lock_btn.setToolTip(f"Lock / Unlock Track {tid}")
                lock_btn.setStyleSheet(
                    "QPushButton{background:transparent;border:none;font-size:10px;color:#64748B;padding:0;min-height:0;}"
                    "QPushButton:checked{color:#EF4444;background:#261214;border-radius:2px;}"
                    "QPushButton:hover{background:#1E293B;}"
                )

                def _on_lock_toggled(
                    checked: bool, track_id: str = tid, btn: QPushButton = lock_btn
                ) -> None:
                    btn.setText("🔒" if checked else "🔓")
                    self.track_lock_toggled.emit(track_id, checked)

                lock_btn.toggled.connect(_on_lock_toggled)
                c_lay.addWidget(lock_btn)

                default_icon = "👁️" if ttype == "video" else "🎙" if ttype == "audio" else "💬"
                mute_icon = "🚫" if ttype == "video" else "🔇" if ttype == "audio" else "🗨️"
                eye_btn = QPushButton(default_icon, cell)
                eye_btn.setCheckable(True)
                eye_btn.setChecked(False)
                eye_btn.setFixedSize(22, 20)
                eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                eye_btn.setToolTip(f"Toggle Mute / Visibility for Track {tid}")
                eye_btn.setStyleSheet(
                    "QPushButton{background:transparent;border:none;font-size:10px;color:#8C9BAE;padding:0;min-height:0;}"
                    "QPushButton:checked{color:#F59E0B;background:#2A2010;border-radius:2px;}"
                    "QPushButton:hover{background:#1E293B;}"
                )

                def _on_vis_toggled(
                    checked: bool,
                    track_id: str = tid,
                    def_ico: str = default_icon,
                    m_ico: str = mute_icon,
                    btn: QPushButton = eye_btn,
                ) -> None:
                    btn.setText(m_ico if checked else def_ico)
                    self.track_visibility_toggled.emit(track_id, not checked)

                eye_btn.toggled.connect(_on_vis_toggled)
                c_lay.addWidget(eye_btn)

                t_lbl = QLabel(f"{tid}  {label}", cell)
                t_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{col};")
                c_lay.addWidget(t_lbl, stretch=1)

                if tid in {"S1", "S2"} or tid.startswith("A"):
                    imp_btn = QPushButton("📂", cell)
                    imp_btn.setFixedSize(20, 20)
                    imp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    imp_btn.setToolTip(f"Import {label} into {tid}…")
                    imp_btn.setStyleSheet(
                        "QPushButton{background:transparent;border:none;font-size:10px;color:#38BDF8;padding:0;min-height:0;}"
                        "QPushButton:hover{background:#1E293B;border-radius:2px;}"
                    )
                    imp_btn.clicked.connect(lambda _, t=tid: self.track_import_requested.emit(t))
                    c_lay.addWidget(imp_btn)

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

        def __init__(self, parent: QWidget | None = None) -> None:
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
            self._edit_history: list[list[ClipTuple]] = []
            self._edit_future: list[list[ClipTuple]] = []
            self._timeline_toggles = {"Toggle Snapping": True, "Linked Selection": True}
            self._mixer_levels: dict[str, float] = {
                "A1": 1.0,
                "A2": 1.0,
                "A3": 0.7,
                "A4": 0.8,
                "A5": 0.6,
                "master": 1.0,
            }
            self._mixer_mutes: set[str] = set()
            self._mixer_solos: set[str] = set()
            self._sidechain_ducking_enabled: bool = True
            self._sidechain_ducking_depth: float = 12.0
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
            self._active_lipsync_worker: Any | None = None
            self._assistant_worker: Any | None = None
            self._audio_analysis_dialog: Any | None = None
            self._tts_worker: Any | None = None
            self._timing_worker: Any | None = None
            self._pending_timing_edit: dict[str, Any] | None = None
            self._take_audio_player: Any | None = None
            self._take_audio_output: Any | None = None
            self._selected_voice_name: str | None = None
            self._active_opened_project: Any | None = None
            self._extraction_worker: Any | None = None
            self._transcription_worker: Any | None = None
            self._translation_worker: Any | None = None
            self._synthesis_worker: Any | None = None
            self._render_worker: Any | None = None
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
            self.workspace_splitter.setStyleSheet("QSplitter::handle{background:#1E2838;}")

            # Main 3-column Studio workspace.
            upper_splitter = QSplitter(Qt.Orientation.Horizontal, self.workspace_splitter)
            upper_splitter.setHandleWidth(1)
            upper_splitter.setMinimumHeight(380)
            upper_splitter.setStyleSheet("QSplitter::handle{background:#1E2838;}")

            # Left Column (Media Browser)
            self.media_panel = _MediaBrowserPanel(upper_splitter)
            self.media_panel.setFixedWidth(376)
            upper_splitter.addWidget(self.media_panel)

            # Center Column (Program Video Monitor)
            self.monitor_panel = _ProgramMonitorPanel(upper_splitter)
            upper_splitter.addWidget(self.monitor_panel)

            # Right Column (Dialogue Inspector & Dual VU Level Meter)
            self.inspector_panel = _DialogueInspectorPanel(upper_splitter)
            self.inspector_panel.setFixedWidth(494)
            upper_splitter.addWidget(self.inspector_panel)

            upper_splitter.setStretchFactor(0, 0)
            upper_splitter.setStretchFactor(1, 1)
            upper_splitter.setStretchFactor(2, 0)
            upper_splitter.setSizes([376, 664, 494])
            self.workspace_splitter.addWidget(upper_splitter)

            # Lower multitrack timeline and agentic actions.
            tl_container = QWidget(self.workspace_splitter)
            tl_lay = QHBoxLayout(tl_container)
            tl_lay.setContentsMargins(0, 0, 0, 0)
            tl_lay.setSpacing(0)

            self.navigation_rail = _StudioNavigationRail(tl_container)
            tl_lay.addWidget(self.navigation_rail)

            self.tool_palette = _TimelineToolPalette(tl_container)
            tl_lay.addWidget(self.tool_palette)

            timeline_editor = QWidget(tl_container)
            timeline_editor_layout = QVBoxLayout(timeline_editor)
            timeline_editor_layout.setContentsMargins(0, 0, 0, 0)
            timeline_editor_layout.setSpacing(0)
            self.timeline_bar = _TimelineEditorBar(timeline_editor)
            timeline_editor_layout.addWidget(self.timeline_bar)

            timeline_tracks = QWidget(timeline_editor)
            timeline_tracks_layout = QHBoxLayout(timeline_tracks)
            timeline_tracks_layout.setContentsMargins(0, 0, 0, 0)
            timeline_tracks_layout.setSpacing(0)
            self.header_p = _TimelineHeaderPanel(timeline_tracks)
            timeline_tracks_layout.addWidget(self.header_p)
            self.canvas_view = _TimelineCanvasView(timeline_tracks)
            timeline_tracks_layout.addWidget(self.canvas_view, stretch=1)
            timeline_editor_layout.addWidget(timeline_tracks, stretch=1)
            tl_lay.addWidget(timeline_editor, stretch=1)

            # AI Actions Dock Panel
            self.ai_overlay = _FloatingAIActionsPanel(tl_container)
            tl_lay.addWidget(self.ai_overlay)

            self.workspace_splitter.addWidget(tl_container)
            self.workspace_splitter.setStretchFactor(0, 1)
            self.workspace_splitter.setStretchFactor(1, 1)
            self.workspace_splitter.setSizes([480, 435])
            root.addWidget(self.workspace_splitter, stretch=1)

            # Bottom status bar reports only real operations.
            dock_bar = QFrame(self)
            dock_bar.setFixedHeight(38)
            dock_bar.setStyleSheet("background:#111315;border-top:1px solid #08090B;")
            d_lay = QHBoxLayout(dock_bar)
            d_lay.setContentsMargins(12, 0, 10, 0)
            d_lay.setSpacing(5)

            self.autosave_lbl = QLabel("●  Auto-saved · Ready", dock_bar)
            self.autosave_lbl.setFixedWidth(190)
            self.autosave_lbl.setStyleSheet("font-size:10px;color:#6DCA73;")
            d_lay.addWidget(self.autosave_lbl)
            self.status_msg_lbl = QLabel("Ready · import a movie to begin", dock_bar)
            self.status_msg_lbl.setStyleSheet("font-size:10px;color:#737A86;")
            d_lay.addWidget(self.status_msg_lbl)

            d_lay.addStretch()

            self.status_dock = dock_bar
            root.addWidget(dock_bar)

        def _wire_signals(self) -> None:
            # Monitor playhead sync
            self.monitor_panel.playhead_changed.connect(self.canvas_view.set_playhead)
            self.monitor_panel.playhead_changed.connect(self.timeline_bar.set_timecode)
            self.canvas_view.timecode_changed.connect(self.monitor_panel.set_playhead)
            self.canvas_view.timecode_changed.connect(self.timeline_bar.set_timecode)
            self.canvas_view.clips_edited.connect(self._on_canvas_clips_edited)
            self.monitor_panel.action_triggered.connect(self._show_status)
            self.monitor_panel.import_requested.connect(self.import_media_dialog)
            self.monitor_panel.duration_resolved.connect(self._on_media_duration_resolved)
            self.monitor_panel.first_frame_decoded.connect(self.canvas_view.set_video_thumbnail)

            # Media selection sync
            self.media_panel.media_selected.connect(self._on_media_selected)

            # Timeline clip selection -> Inspector sync
            self.canvas_view.clip_clicked.connect(self._on_timeline_clip_clicked)

            # Inspector live text sync -> Timeline canvas
            self.inspector_panel.original_changed.connect(self._on_original_changed)
            self.inspector_panel.character_changed.connect(self._on_character_changed)
            self.inspector_panel.translation_changed.connect(self._on_translation_changed)
            self.inspector_panel.trans_in.editingFinished.connect(self._commit_translation)
            self.inspector_panel.lang_in.editingFinished.connect(self._on_target_language_changed)

            # Inspector Action buttons & Subtitle Imports
            self.inspector_panel.regenerate_requested.connect(self._on_ai_regenerate_voice)
            self.inspector_panel.retake_requested.connect(self._on_perform_single_line_retake)
            self.inspector_panel.open_lipsync_inspector_requested.connect(
                self._open_lipsync_inspector
            )
            self.inspector_panel.ai_fix_requested.connect(self._on_ai_fix_all)
            self.inspector_panel.preview_take_requested.connect(self._preview_selected_take)
            self.inspector_panel.import_source_srt_requested.connect(
                lambda: self.import_subtitle_dialog(target=False)
            )
            self.inspector_panel.import_target_srt_requested.connect(
                lambda: self.import_subtitle_dialog(target=True)
            )
            self.inspector_panel.import_bilingual_srt_requested.connect(
                self.import_bilingual_subtitle_dialog
            )
            self.inspector_panel.manage_characters_requested.connect(self._open_character_manager)
            self.inspector_panel.casting_requested.connect(self._open_character_casting_studio)
            self.inspector_panel.export_requested.connect(self._open_broadcast_export)
            self.inspector_panel.cloud_gpu_requested.connect(self._open_kaggle_accelerator)
            self.inspector_panel.audio_analysis_requested.connect(self._open_audio_analysis)
            self.inspector_panel.action_clicked.connect(self._on_ai_action_clicked)
            self.inspector_panel.dialogue_card_selected.connect(self._on_dialogue_card_selected)
            self.inspector_panel.track_level_changed.connect(self._on_track_level_changed)
            self.inspector_panel.track_mute_toggled.connect(self._on_track_mute_toggled)
            self.inspector_panel.track_solo_toggled.connect(self._on_track_solo_toggled)
            self.inspector_panel.ducking_changed.connect(self._on_ducking_changed)
            self.inspector_panel.fit_to_slot_requested.connect(self._on_fit_to_slot)
            self.inspector_panel.nudge_timing_requested.connect(self._on_nudge_timing)

            # Floating AI Actions
            self.ai_overlay.action_clicked.connect(self._on_ai_action_clicked)
            self.ai_overlay.run_requested.connect(self._run_agentic_dub)
            self.ai_overlay.cancel_requested.connect(self._cancel_agentic_dub)
            self.stage_bar.home_requested.connect(self._show_home_dashboard)
            self.stage_bar.workspace_selected.connect(self._on_workspace_selected)
            self.stage_bar.kaggle_requested.connect(self._open_kaggle_accelerator)
            self.stage_bar.voice_model_requested.connect(self._open_voice_model_selector)
            self.stage_bar.casting_requested.connect(self._open_character_casting_studio)
            self.stage_bar.export_requested.connect(self._open_broadcast_export)
            self.stage_bar.dub_requested.connect(self.open_dub_dialog)
            self.stage_bar.undo_requested.connect(self.undo)
            self.stage_bar.redo_requested.connect(self.redo)
            self.navigation_rail.route_requested.connect(self._on_navigation_route)
            self.tool_palette.tool_selected.connect(self.canvas_view.set_tool)
            self.tool_palette.tool_selected.connect(
                lambda tool: self._show_status(f"Timeline tool: {tool}")
            )
            self.timeline_bar.action_requested.connect(self._on_timeline_toolbar_action)
            self.header_p.track_lock_toggled.connect(self.canvas_view.set_track_locked)
            self.header_p.track_visibility_toggled.connect(self.canvas_view.set_track_visible)
            self.header_p.track_import_requested.connect(self._on_track_import_requested)

        def _show_home_dashboard(self) -> None:
            window = self.window()
            show_home = getattr(window, "show_home", None)
            if callable(show_home):
                show_home()

        def _open_kaggle_accelerator(self) -> None:
            from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog

            source_path = str(self._current_project_data.get("file_path", ""))
            voice_engine = str(self._current_project_data.get("voice_engine", "chatterbox"))
            dlg = KaggleAcceleratorDialog(
                self,
                movie_path=source_path,
                target_language=self._automation_state.target_language or "bn",
                voice_engine=voice_engine,
                enable_lipsync=bool(self._current_project_data.get("lipsync", True)),
            )
            if dlg.exec():
                res = dlg.get_sync_result()
                if res and res.success:
                    if res.dubbed_audio_path and res.dubbed_audio_path.is_file():
                        self._current_project_data["dubbed_audio_path"] = str(res.dubbed_audio_path)
                    if res.dubbed_video_path and res.dubbed_video_path.is_file():
                        self._current_project_data["dubbed_video_path"] = str(res.dubbed_video_path)
                    if res.subtitle_path and res.subtitle_path.is_file():
                        self._current_project_data["subtitle_path"] = str(res.subtitle_path)
                    self._show_status(
                        f"✓ Cloud GPU Master Synced: {res.total_files} deliverables ingested"
                    )

        def _open_lipsync_inspector(self) -> None:
            from aidub.ui.dialogs.lipsync_inspector_dialog import LipSyncInspectorDialog

            line_text = (
                self.inspector_panel.trans_in.text().strip()
                or self.inspector_panel.orig_in.text().strip()
                or "Dialogue line"
            )
            dur = 2.0
            idx = 0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
                clip_label = str(self._active_clip_info.get("label", ""))
                import re

                m = re.search(r"(\d+)", clip_label)
                if m:
                    idx = max(0, int(m.group(1)) - 1)

            dlg = LipSyncInspectorDialog(
                utterance_index=idx,
                dialogue_text=line_text,
                duration_s=dur,
                language=self._automation_state.target_language or "bn",
                parent=self,
            )
            dlg.offset_applied.connect(self._on_lipsync_offset_applied)
            dlg.exec()

        def _on_lipsync_offset_applied(self, utterance_index: int, offset_s: float) -> None:
            self._show_status(
                f"✓ Lip-Sync slip offset {offset_s * 1000.0:+.1f}ms applied to line #{utterance_index + 1}"
            )

        def _open_voice_model_selector(self) -> None:
            from aidub.ui.dialogs.voice_model_dialog import VoiceModelDialog

            current_engine = str(self._current_project_data.get("voice_engine", "chatterbox"))
            dlg = VoiceModelDialog(
                self,
                current_engine=current_engine,
                target_language=self._automation_state.target_language or "bn",
            )
            if dlg.exec():
                config = dlg.get_configuration()
                self._current_project_data["voice_engine"] = config["engine"]
                self._current_project_data["voice_emotion"] = config["emotion"]
                self._current_project_data["voice_name"] = config["voice"]
                self._current_project_data["voice_rate"] = config["rate"]
                self._current_project_data["voice_pitch"] = config["pitch"]
                if config["language"]:
                    self._automation_state.target_language = config["language"]
                    self.inspector_panel.lang_in.setText(config["language"])
                self._show_status(
                    f"AI Voice: {config['engine'].upper()} · {config['voice']} ({config['rate']}) · Emotion: {config['emotion']}"
                )

        def _open_character_casting_studio(self) -> None:
            from aidub.ui.dialogs.character_casting_dialog import CharacterCastingStudioDialog

            counts = self._compute_character_counts()
            char_list = (
                list(counts.keys())
                if counts
                else ["Protagonist (Speaker 0)", "Antagonist (Speaker 1)"]
            )
            current_voices = self._current_project_data.get("character_voices", {})

            dlg = CharacterCastingStudioDialog(
                self,
                characters=char_list,
                current_casting=current_voices,
                target_language=self._automation_state.target_language or "bn",
            )
            if dlg.exec():
                new_mapping = dlg.get_character_voices()
                self._current_project_data.setdefault("character_voices", {}).update(new_mapping)
                self._show_status(
                    f"✓ AI Character Voices Cast: {len(new_mapping)} characters assigned"
                )

        def _open_broadcast_export(self) -> None:
            from aidub.ui.dialogs.broadcast_export_dialog import BroadcastExportDialog

            video_p = str(self._current_project_data.get("file_path", ""))
            sub_p = str(self._current_project_data.get("subtitle_path", ""))
            aud_p = str(self._current_project_data.get("dubbed_audio_path", ""))
            music_p = str(self._current_project_data.get("background_audio_path", ""))

            dlg = BroadcastExportDialog(
                self,
                video_path=video_p,
                audio_path=aud_p or video_p,
                music_path=music_p,
                subtitle_path=sub_p,
                default_output_name=f"broadcast_master_{Path(video_p).stem if video_p else 'movie'}.mp4",
            )
            dlg.exec()

        def open_isometric_dialog(self) -> None:
            """Open the AI Text Translation dialog for subtitle localization."""
            from PySide6.QtWidgets import (
                QComboBox,
                QDialog,
                QHBoxLayout,
                QLabel,
                QPushButton,
                QVBoxLayout,
            )

            from aidub.ui.design.stylesheet import build_stylesheet

            dlg = QDialog(self)
            dlg.setWindowTitle("AI Text Translation \u2014 Subtitle Localization")
            dlg.setMinimumSize(480, 280)
            dlg.setStyleSheet(build_stylesheet())

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)

            # Header
            header = QLabel("\U0001f310  AI Subtitle Translation", dlg)
            header.setStyleSheet("font-size: 16px; font-weight: 800; color: #C084FC;")
            layout.addWidget(header)

            sub = QLabel(
                "Translate source subtitles (S1) into the target language using AI. "
                "Source cues must exist in track S1 (import SRT or run transcription first).",
                dlg,
            )
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
            layout.addWidget(sub)

            # Language selection
            lang_row = QHBoxLayout()
            lang_row.setSpacing(12)

            lang_lbl = QLabel("Target Language:", dlg)
            lang_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #E2E8F0;")
            lang_row.addWidget(lang_lbl)

            lang_combo = QComboBox(dlg)
            lang_options = [
                ("Bengali (\u09ac\u09be\u0982\u09b2\u09be)", "bn-BD"),
                ("English (US)", "en-US"),
                ("Hindi (\u0939\u093f\u0928\u094d\u0926\u0940)", "hi-IN"),
                ("Spanish (Espa\u00f1ol)", "es-ES"),
                ("French (Fran\u00e7ais)", "fr-FR"),
                ("German (Deutsch)", "de-DE"),
                ("Japanese (\u65e5\u672c\u8a9e)", "ja-JP"),
                ("Chinese (\u4e2d\u6587)", "zh-CN"),
                ("Arabic (\u0627\u0644\u0639\u0631\u0628\u064a\u0629)", "ar-SA"),
                ("Portuguese (Portugu\u00eas)", "pt-BR"),
                ("Russian (\u0420\u0443\u0441\u0441\u043a\u0438\u0439)", "ru-RU"),
                ("Korean (\ud55c\uad6d\uc5b4)", "ko-KR"),
            ]
            for name, code in lang_options:
                lang_combo.addItem(name, code)

            current_lang = self.inspector_panel.lang_in.text().strip() or self._automation_state.target_language or "bn-BD"
            for i in range(lang_combo.count()):
                if lang_combo.itemData(i) == current_lang:
                    lang_combo.setCurrentIndex(i)
                    break

            lang_combo.setStyleSheet(
                "QComboBox { background: #111827; color: #F8FAFC; border: 1px solid #1F2937; "
                "border-radius: 6px; padding: 7px 12px; font-size: 12px; min-width: 200px; }"
            )
            lang_row.addWidget(lang_combo, stretch=1)
            layout.addLayout(lang_row)

            # Action buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel", dlg)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #334155; "
                "border-radius: 6px; padding: 8px 18px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background: #334155; color: #FFF; }"
            )
            cancel_btn.clicked.connect(dlg.reject)
            btn_row.addWidget(cancel_btn)

            translate_btn = QPushButton("\u2713  Start Translation", dlg)
            translate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            translate_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #8B5CF6); "
                "color: #FFF; border: none; border-radius: 6px; padding: 8px 24px; font-weight: 800; font-size: 12px; }"
                "QPushButton:hover { background: #9333EA; }"
            )

            def on_translate() -> None:
                target_lang = lang_combo.currentData()
                self.inspector_panel.lang_in.setText(target_lang)
                dlg.accept()
                self._run_modular_translate_subtitles()

            translate_btn.clicked.connect(on_translate)
            btn_row.addWidget(translate_btn)

            layout.addLayout(btn_row)

            dlg.exec()

        def keyPressEvent(self, event: Any) -> None:  # noqa: N802
            # Modifier shortcuts (Ctrl+...)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_K:
                    self._open_kaggle_accelerator()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_D:
                    self._run_agentic_dub()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_I:
                    self.import_media_dialog()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_E:
                    self._open_broadcast_export()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_M:
                    self._open_character_casting_studio()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_B:
                    if hasattr(self, "canvas_view") and self.canvas_view.split_at_playhead():
                        self._show_status("Clip split at playhead · Ctrl+Z to undo")
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_Z:
                    self.undo()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_Y:
                    self.redo()
                    event.accept()
                    return

            # Bare S key: Split clip at playhead (universal NLE hotkey)
            if event.key() == Qt.Key.Key_S and not (
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                if hasattr(self, "canvas_view") and self.canvas_view.split_at_playhead():
                    self._show_status("Clip split at playhead · Ctrl+Z to undo")
                event.accept()
                return

            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if hasattr(self, "canvas_view") and self.canvas_view.delete_selected_clips():
                    self._show_status("Clip deleted · Ctrl+Z to undo")
                    event.accept()
                    return

            # Space toggles playback (industry NLE standard)
            if event.key() == Qt.Key.Key_Space:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._toggle_play()
                event.accept()
                return

            # Bare J, K, L shuttle keys
            if event.key() == Qt.Key.Key_J:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._on_step_back()
                event.accept()
                return
            if event.key() == Qt.Key.Key_K:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    if self.monitor_panel._is_playing:
                        self.monitor_panel._toggle_play()
                event.accept()
                return
            if event.key() == Qt.Key.Key_L:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._on_step_forward()
                event.accept()
                return

            super().keyPressEvent(event)

        def _on_workspace_selected(self, workspace: str) -> None:
            if workspace == "Ingest":
                self.import_media_dialog()
            elif workspace == "Dubbing":
                self.canvas_view.setFocus()
                self._show_status("Dubbing workspace active")
            elif workspace == "Review":
                self._run_subtitle_qc()
            elif workspace == "Delivery":
                self._show_delivery()

        def _on_navigation_route(self, route: str) -> None:
            if route == "Subtitles":
                choice, accepted = QInputDialog.getItem(
                    self,
                    "Subtitle Track",
                    "Choose the subtitle track to import:",
                    ["Source subtitles", "Target subtitles", "Bilingual subtitles (S1 + S2)"],
                    0,
                    False,
                )
                if accepted:
                    if choice.startswith("Bilingual"):
                        self.import_bilingual_subtitle_dialog()
                    else:
                        self.import_subtitle_dialog(target=choice == "Target subtitles")
                return
            if route == "Pipeline Readiness":
                self._show_pipeline_readiness()
                return
            self._show_status(f"Unknown Studio action: {route}")

        def _show_pipeline_readiness(self) -> None:
            from aidub.diagnostics.dubbing import collect_dubbing_diagnostics

            report = collect_dubbing_diagnostics()
            QMessageBox.information(self, "Pipeline Readiness", report.render())

        def _open_audio_analysis(self) -> None:
            """Open the integrated audio analyzer for the loaded source and selected interval."""

            if self._audio_analysis_dialog is not None:
                if self._audio_analysis_dialog.isVisible():
                    self._audio_analysis_dialog.raise_()
                    self._audio_analysis_dialog.activateWindow()
                    return

            from aidub.ui.audio_analysis_dialog import AudioAnalysisDialog

            path = str(self._current_project_data.get("file_path", ""))
            start = 0.0
            interval = 30.0
            active = self._active_clip_info
            if active is not None:
                try:
                    start = max(0.0, float(active.get("start", 0.0)))
                    clip_duration = max(0.0, float(active.get("dur", 0.0)))
                    if clip_duration > 0:
                        interval = min(30.0, clip_duration)
                except (TypeError, ValueError):
                    start, interval = 0.0, 30.0

            self._audio_analysis_dialog = AudioAnalysisDialog(
                path,
                start_seconds=start,
                duration_seconds=interval,
                parent=self,
            )
            self._audio_analysis_dialog.show()
            self._audio_analysis_dialog.raise_()
            self._audio_analysis_dialog.activateWindow()

        def _run_subtitle_qc(self) -> None:
            """Run broadcast subtitle rules against the current target subtitle track."""
            from aidub.subtitles.qc import SubtitleCue, SubtitleQcEngine

            target_clips = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == "S2"
            ]
            if not target_clips:
                message = (
                    "No target subtitle cues are loaded. Import a target-language subtitle file "
                    "or run Auto Dub Master before running subtitle QC."
                )
                self._show_status("Subtitle QC not run: target subtitle track is empty")
                QMessageBox.information(self, "Subtitle Quality Control", message)
                return

            cues = [
                SubtitleCue(
                    cue_id=str(index),
                    start_ms=round(float(clip[1]) * 1_000),
                    end_ms=round((float(clip[1]) + float(clip[2])) * 1_000),
                    text=str(clip[3]),
                )
                for index, clip in enumerate(target_clips, start=1)
            ]
            report = SubtitleQcEngine().check("subtitle_target", cues)
            self.inspector_panel.set_subtitle_qc_report(report)

            status = "PASS" if report.passed else "REVIEW"
            self._show_status(
                f"Subtitle QC {status}: {report.total_cues} cues, "
                f"{report.error_count} errors, {report.warning_count} warnings"
            )
            details = [
                f"Target subtitle track: {report.total_cues} cues",
                "Rules: maximum 37 characters per line, 17 characters/second, "
                "1–7 second cue duration, no overlaps, and at least 80 ms between cues.",
                f"Result: {status} · {report.error_count} errors · {report.warning_count} warnings",
            ]
            if report.violations:
                details.extend(["", "Findings:"])
                details.extend(
                    f"[{item.severity.upper()}] {item.message}" for item in report.violations[:40]
                )
                omitted = len(report.violations) - 40
                if omitted > 0:
                    details.append(f"… {omitted} additional findings")
            else:
                details.extend(["", "No subtitle rule violations were found."])

            dialog = QMessageBox.warning if report.error_count else QMessageBox.information
            dialog(self, "Subtitle Quality Control", "\n".join(details))

        def _show_delivery(self) -> None:
            self._open_broadcast_export()

        def _on_timeline_toolbar_action(self, action: str) -> None:
            if action in {"Add Marker", "Marker"}:
                self._add_timeline_marker()
            elif action == "Undo":
                self.undo()
            elif action == "Redo":
                self.redo()
            elif action == "Split Screen":
                self.monitor_panel.toggle_split_view()
            elif action == "Zoom In":
                self._set_timeline_zoom(150.0)
            elif action == "Zoom Out":
                self._set_timeline_zoom(75.0)
            elif action == "Timeline Settings":
                self._show_timeline_settings()
            else:
                self._show_status(f"Action applied: {action}")

        def _set_timeline_toggle(self, action: str, enabled: bool) -> None:
            if action not in self._timeline_toggles:
                self._show_status(f"Unknown timeline setting: {action}")
                return
            self._timeline_toggles[action] = enabled
            if action == "Toggle Snapping":
                self.canvas_view.set_snapping_enabled(enabled)
            else:
                self.canvas_view.set_linked_selection_enabled(enabled)
            self._show_status(f"{action}: {'enabled' if enabled else 'disabled'}")

        def _build_timeline_settings_menu(self) -> QMenu:
            menu = QMenu(self)
            snapping = menu.addAction("Snap to clip edges and markers")
            snapping.setCheckable(True)
            snapping.setChecked(self._timeline_toggles["Toggle Snapping"])
            snapping.triggered.connect(
                lambda checked: self._set_timeline_toggle("Toggle Snapping", checked)
            )
            linked = menu.addAction("Link related dialogue and dub clips")
            linked.setCheckable(True)
            linked.setChecked(self._timeline_toggles["Linked Selection"])
            linked.triggered.connect(
                lambda checked: self._set_timeline_toggle("Linked Selection", checked)
            )
            menu.addSeparator()
            zoom = menu.addAction("Set horizontal zoom?")
            zoom.triggered.connect(self._set_timeline_zoom_dialog)
            fit = menu.addAction("Fit timeline to window")
            fit.triggered.connect(self._fit_timeline_to_window)
            return menu

        def _show_timeline_settings(self) -> None:
            menu = self._build_timeline_settings_menu()
            menu.exec(self.timeline_bar.mapToGlobal(self.timeline_bar.rect().bottomRight()))

        def _set_timeline_zoom_dialog(self) -> None:
            current_zoom = self.canvas_view.transform().m11() * 100
            zoom, accepted = QInputDialog.getDouble(
                self,
                "Timeline Zoom",
                "Horizontal zoom percentage:",
                current_zoom,
                55.0,
                350.0,
                0,
            )
            if accepted:
                self._set_timeline_zoom(zoom)

        def _set_timeline_zoom(self, zoom: float) -> None:
            zoom = max(55.0, min(350.0, float(zoom)))
            self.canvas_view.resetTransform()
            self.canvas_view.scale(zoom / 100.0, 1.0)
            self._show_status(f"Timeline zoom set to {zoom:.0f}%")

        def _fit_timeline_to_window(self) -> None:
            duration = max(1.0, float(self._current_project_data.get("duration", 1.0)))
            available_width = max(1, self.canvas_view.viewport().width() - 24)
            zoom = max(0.55, min(3.5, available_width / (duration * PX_PER_SEC_DEFAULT)))
            self.canvas_view.resetTransform()
            self.canvas_view.scale(zoom, 1.0)
            self._show_status("Timeline fitted to the available window width")

        def _add_timeline_marker(self) -> None:
            seconds = self.monitor_panel._playhead_sec
            if not self.canvas_view.add_marker(seconds):
                self._show_status(f"A marker already exists at {_format_tc(seconds)}")
                return
            markers = list(self._current_project_data.get("markers", []))
            markers.append(seconds)
            self._current_project_data["markers"] = markers
            self._show_status(f"Marker added at {_format_tc(seconds)}")

        def _on_canvas_clips_edited(self, clips: list[ClipTuple]) -> None:
            previous = list(self._current_project_data.get("clips", []))
            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = list(clips)
            self._show_status("Razor edit applied · Ctrl+Z to undo")

        def load_project_data(self, project_info: dict[str, Any]) -> None:
            """Load a real movie and derive all initial UI state from that file."""
            file_path = str(project_info.get("file_path") or project_info.get("movie_path", ""))
            source = Path(file_path) if file_path else None
            target_language = str(
                project_info.get("target_language")
                or next(
                    iter(project_info.get("target_languages", [])),
                    self._automation_state.target_language,
                )
            )
            if source is None or not source.is_file():
                self._show_status("The selected source movie does not exist")
                return
            if source.suffix.lower() in {".srt", ".vtt"}:
                self.import_subtitle_file(str(source))
                return

            proj_name = str(project_info.get("name") or source.stem)
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

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
                self._parse_subtitle_file_cues(str(sidecar), track_id="S1") if sidecar else []
            )
            clips: list[ClipTuple] = [
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
            self._active_clip_info = None
            self._selected_voice_name = None
            self._edit_history.clear()
            self._edit_future.clear()
            self.canvas_view.clear_markers()
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
            self.stage_bar.set_project_title(data["name"])
            self.inspector_panel.update_clip_info(
                data["original_text"],
                data["translation_text"],
                data["character"],
                target_language,
            )
            cues_list = [
                {
                    "speaker": f"Speaker {(idx % 2) + 1}",
                    "orig": c[3],
                    "trans": "",
                    "start": c[1],
                    "end": c[1] + c[2],
                }
                for idx, c in enumerate(data.get("clips", []))
                if c[0] in {"S1", "S2"}
            ]
            if cues_list:
                self.inspector_panel.set_dialogue_cues(cues_list)
            self.header_p.set_header_title(data["name"])
            self.timeline_bar.set_title(data["name"])
            self.canvas_view.set_clips(data["clips"], data["duration"])
            self.inspector_panel.clear_quality_report()
            try:
                saved_state = self._session_store.load(proj_name)
            except (OSError, ValueError):
                saved_state = None
            if (
                saved_state is None
                or (file_path and saved_state.source_path and saved_state.source_path != file_path)
                or (saved_state is not None and saved_state.target_language != target_language)
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

        def load_project(self, project: str | Path | dict[str, Any]) -> None:
            """Universal project loader supporting .aidub packages, media paths, or project info dicts."""
            if isinstance(project, dict):
                self.load_project_data(project)
                return
            path = Path(project)
            if (path.is_dir() and path.suffix.casefold() == ".aidub") or (
                path.is_dir() and (path / "project.db").is_file()
            ):
                self.open_project_package(path)
            elif path.is_file():
                self.open_media_path(path)
            else:
                self._show_status(f"Cannot load project path: {path}")

        def open_project_package(self, package_path: Path | str) -> None:
            """Open an .aidub project directory via ProjectPackageService and load into Timeline."""
            from aidub.application.projects import ProjectPackageService
            from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

            catalog = ProjectCatalog(default_catalog_path())
            try:
                catalog.initialize()
            except Exception:
                pass
            service = ProjectPackageService(catalog=catalog)
            opened = service.open(package_path)
            self.load_opened_project(opened)

        def load_opened_project(self, opened: Any) -> None:
            """Load an OpenedProject instance, restoring its database state, media, and subtitle tracks."""
            self._active_opened_project = opened
            proj = opened.project
            paths = opened.paths
            name = proj.name

            # Check for media in source-links or project root
            media_path = ""
            source_links_dir = paths.source_links
            if source_links_dir.is_dir():
                for f in source_links_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {
                        ".mp4",
                        ".mkv",
                        ".mov",
                        ".avi",
                        ".m2ts",
                    }:
                        media_path = str(f)
                        break

            # Read persisted timeline state if present (with backup recovery)
            timeline_state_file = paths.transcripts / "timeline_state.json"
            timeline_bak_file = paths.transcripts / "timeline_state.json.bak"
            clips: list[ClipTuple] = []
            duration = 1.0
            raw: dict[str, Any] | None = None
            if timeline_state_file.is_file():
                try:
                    raw = json.loads(timeline_state_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Corrupted timeline_state.json in %s: %s", paths.root, exc)
                    if timeline_bak_file.is_file():
                        try:
                            raw = json.loads(timeline_bak_file.read_text(encoding="utf-8"))
                            logger.info(
                                "Recovered timeline state from backup %s", timeline_bak_file
                            )
                        except Exception as bak_exc:
                            logger.warning("Failed to recover from timeline backup: %s", bak_exc)
            elif timeline_bak_file.is_file():
                try:
                    raw = json.loads(timeline_bak_file.read_text(encoding="utf-8"))
                    logger.info("Recovered timeline state from backup %s", timeline_bak_file)
                except Exception as bak_exc:
                    logger.warning("Failed to recover from timeline backup: %s", bak_exc)

            if raw is not None:
                try:
                    if not media_path and raw.get("media_path"):
                        media_path = raw.get("media_path", "")
                    duration = float(raw.get("duration", 1.0))
                    for item in raw.get("clips", []):
                        if isinstance(item, (list, tuple)):
                            clips.append(
                                (
                                    str(item[0]),
                                    float(item[1]),
                                    float(item[2]),
                                    str(item[3]),
                                    item[4] if len(item) > 4 else None,
                                )
                            )
                        elif isinstance(item, dict):
                            clips.append(
                                (
                                    str(item.get("track", "V1")),
                                    float(item.get("start", 0.0)),
                                    float(item.get("duration", 1.0)),
                                    str(item.get("text", "")),
                                    item.get("take_id"),
                                )
                            )
                    mixer_data = raw.get("mixer", {})
                    if mixer_data:
                        self._mixer_levels.update(mixer_data.get("levels", {}))
                        self._mixer_mutes = set(mixer_data.get("mutes", []))
                        self._mixer_solos = set(mixer_data.get("solos", []))
                        self._sidechain_ducking_enabled = bool(
                            mixer_data.get("sidechain_ducking", True)
                        )
                        self._sidechain_ducking_depth = float(mixer_data.get("ducking_depth", 12.0))
                        for trk, lvl in self._mixer_levels.items():
                            self.inspector_panel.set_track_level(trk, lvl)
                        for trk in ["A1", "A2", "A3", "A4", "A5", "master"]:
                            self.inspector_panel.set_track_mute(trk, trk in self._mixer_mutes)
                            if trk != "master":
                                self.inspector_panel.set_track_solo(trk, trk in self._mixer_solos)
                        self.inspector_panel.chk_sidechain_duck.setChecked(
                            self._sidechain_ducking_enabled
                        )
                except Exception as exc:
                    logger.warning("Could not read timeline_state.json: %s", exc)

            # Check for existing S1 / S2 subtitle files in transcripts directory
            s1_file = paths.transcripts / "subtitles_S1.srt"
            if s1_file.is_file() and not any(c[0] == "S1" for c in clips):
                s1_cues = self._parse_subtitle_file_cues(str(s1_file), track_id="S1")
                clips.extend(s1_cues)
            s2_file = paths.transcripts / "subtitles_S2.srt"
            if s2_file.is_file() and not any(c[0] == "S2" for c in clips):
                s2_cues = self._parse_subtitle_file_cues(str(s2_file), track_id="S2")
                clips.extend(s2_cues)

            # If media found but no video/audio clips, generate V1 / A1 clips
            if media_path and Path(media_path).is_file():
                try:
                    from aidub.media.ffmpeg_ops import probe

                    info = probe(media_path)
                    duration = max(0.001, float(info["format"]["duration"]))
                except Exception:
                    pass
                if not any(c[0] == "V1" for c in clips):
                    clips.insert(0, ("V1", 0.0, duration, Path(media_path).name, None))
                if not any(c[0] == "A1" for c in clips):
                    clips.insert(1, ("A1", 0.0, duration, Path(media_path).name, None))

            target_lang = "bn-BD"
            if paths.localizations.is_dir():
                for loc_dir in paths.localizations.iterdir():
                    if loc_dir.is_dir():
                        target_lang = loc_dir.name
                        break

            data: dict[str, Any] = {
                "name": name,
                "movie_name": Path(media_path).name if media_path else "",
                "file_path": media_path,
                "character": "",
                "duration": duration,
                "original_text": next((c[3] for c in clips if c[0] == "S1"), ""),
                "translation_text": next((c[3] for c in clips if c[0] == "S2"), ""),
                "quote": "",
                "clips": clips,
                "generated_paths": (),
            }

            self._current_project_data = data
            self._active_clip_info = None
            self._selected_voice_name = None
            self._edit_history.clear()
            self._edit_future.clear()
            self.canvas_view.clear_markers()
            self.canvas_view.clear_video_thumbnail()
            self.media_panel.set_project_name(name, data["movie_name"], media_path)
            self.monitor_panel.set_project_info(
                name, data["movie_name"], "", "", duration, media_path
            )
            self.stage_bar.set_project_title(name)
            self.inspector_panel.update_clip_info(
                data["original_text"],
                data["translation_text"],
                "",
                target_lang,
            )
            cues_list = [
                {
                    "speaker": f"Speaker {(idx % 2) + 1}",
                    "orig": c[3] if c[0] == "S1" else "",
                    "trans": c[3] if c[0] == "S2" else "",
                    "start": c[1],
                    "end": c[1] + c[2],
                }
                for idx, c in enumerate(clips)
                if c[0] in {"S1", "S2"}
            ]
            if cues_list:
                self.inspector_panel.set_dialogue_cues(cues_list)
            self.header_p.set_header_title(name)
            self.timeline_bar.set_title(name)
            self.canvas_view.set_clips(clips, duration)
            self.project_loaded.emit(name)
            self._show_status(f"Loaded project package: {name}")

        @staticmethod
        def _format_clips_as_srt(clips: list[ClipTuple]) -> str:
            lines: list[str] = []

            def _to_srt_time(sec: float) -> str:
                ms = round((sec % 1.0) * 1000)
                total_s = int(sec)
                s = total_s % 60
                total_m = total_s // 60
                m = total_m % 60
                h = total_m // 60
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            for idx, c in enumerate(clips, 1):
                start_str = _to_srt_time(float(c[1]))
                end_str = _to_srt_time(float(c[1]) + float(c[2]))
                text = str(c[3]).strip()
                lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
            return "\n".join(lines)

        def save_to_project(self, opened: Any | None = None) -> bool:
            """Save timeline clips, subtitle cues, and project metadata into the active .aidub package."""
            target_opened = opened or getattr(self, "_active_opened_project", None)
            if target_opened is None:
                self._show_status("No project package open to save")
                return False

            paths = target_opened.paths
            database = target_opened.database
            proj = target_opened.project

            # Save timeline state JSON
            clips = list(self._current_project_data.get("clips", []))
            timeline_state = {
                "project_name": proj.name,
                "media_path": self._current_project_data.get("file_path", ""),
                "duration": self._current_project_data.get("duration", 1.0),
                "clips": [
                    {
                        "track": c[0],
                        "start": c[1],
                        "duration": c[2],
                        "text": c[3],
                        "take_id": c[4] if len(c) > 4 else None,
                    }
                    for c in clips
                ],
                "mixer": {
                    "levels": dict(self._mixer_levels),
                    "mutes": list(self._mixer_mutes),
                    "solos": list(self._mixer_solos),
                    "sidechain_ducking": self._sidechain_ducking_enabled,
                    "ducking_depth": self._sidechain_ducking_depth,
                },
            }
            # Save timeline state JSON atomically with backup
            state_file = paths.transcripts / "timeline_state.json"
            state_tmp = paths.transcripts / "timeline_state.json.tmp"
            state_bak = paths.transcripts / "timeline_state.json.bak"
            if state_file.is_file():
                try:
                    import shutil

                    shutil.copy2(state_file, state_bak)
                except Exception as bak_err:
                    logger.debug("Could not create timeline backup: %s", bak_err)
            payload = json.dumps(timeline_state, indent=2, ensure_ascii=False)
            state_tmp.write_text(payload, encoding="utf-8")
            state_tmp.replace(state_file)

            # Save S1 / S2 subtitles to SRT files atomically
            s1_clips = [c for c in clips if c[0] == "S1"]
            if s1_clips:
                s1_file = paths.transcripts / "subtitles_S1.srt"
                s1_tmp = paths.transcripts / "subtitles_S1.srt.tmp"
                s1_tmp.write_text(self._format_clips_as_srt(s1_clips), encoding="utf-8")
                s1_tmp.replace(s1_file)

            s2_clips = [c for c in clips if c[0] == "S2"]
            if s2_clips:
                s2_file = paths.transcripts / "subtitles_S2.srt"
                s2_tmp = paths.transcripts / "subtitles_S2.srt.tmp"
                s2_tmp.write_text(self._format_clips_as_srt(s2_clips), encoding="utf-8")
                s2_tmp.replace(s2_file)

            # Update SQLite database audit event
            from uuid import uuid4

            from aidub.infrastructure.persistence import AuditEventRecord
            from aidub.infrastructure.persistence.models import utc_now

            with database.transaction() as conn:
                conn.execute(
                    "UPDATE projects SET updated_at = ?, revision = revision + 1 WHERE id = ?",
                    (utc_now(), proj.project_id),
                )
            database.append_audit_event(
                AuditEventRecord(
                    id=f"evt_{uuid4().hex}",
                    project_id=proj.project_id,
                    action="PROJECT_SAVED",
                    actor_type="USER",
                    actor_id="studio.operator",
                    target_type="PROJECT",
                    target_id=proj.project_id,
                    details={"clip_count": len(clips)},
                )
            )
            database.checkpoint_wal(truncate=True)
            self._show_status(f"Project saved: {proj.name}")
            return True

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
                    c for c in self._current_project_data.get("clips", []) if c[0] != track_id
                ]
                current_clips.extend(cues)
                self._current_project_data["clips"] = current_clips
                self._current_project_data["duration"] = dur
                self.canvas_view.set_clips(current_clips, dur)

                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                clip_chars = self._current_project_data.setdefault("clip_characters", {})
                detected_chars: set[str] = set()
                for c in cues:
                    spk, _ = extract_speaker_from_cue_text(c[3])
                    if spk:
                        clip_chars[f"{c[0]}:{round(float(c[1]), 3)}"] = spk
                        detected_chars.add(spk)
                if detected_chars:
                    self.inspector_panel.update_characters(sorted(detected_chars))
                    self.inspector_panel.meta_chars_lbl.setText(f"{len(detected_chars)} speakers")

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
        ) -> list[ClipTuple]:
            """Parse SRT or WebVTT file into track tuple items."""
            results: list[ClipTuple] = []
            from aidub.subtitles.codec import parse_srt, parse_webvtt

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
            elif path.is_file() and suffix in {".wav", ".flac", ".mp3", ".aac", ".m4a"}:
                self._import_audio_asset(path)
            else:
                self._show_status(f"Unsupported or missing media: {media_ref}")

        def import_media_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Source Movie",
                self._default_asset_directory(),
                "Movies (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
            )
            if path:
                self.load_project_data({"name": Path(path).stem, "file_path": path})

        def _default_asset_directory(self) -> str:
            current_path = str(self._current_project_data.get("file_path", ""))
            if current_path:
                current_parent = Path(current_path).parent
                if current_parent.is_dir():
                    return str(current_parent)
            test_movies = Path.cwd() / "test movies"
            return str(test_movies if test_movies.is_dir() else Path.cwd())

        def open_media_path(self, path: str | Path) -> None:
            self._on_media_selected(str(path))

        def _on_track_import_requested(self, tid: str) -> None:
            if tid == "S1":
                self.import_subtitle_dialog(target=False)
            elif tid == "S2":
                self.import_subtitle_dialog(target=True)
            elif tid.startswith("A"):
                path, _selected = QFileDialog.getOpenFileName(
                    self,
                    f"Import Audio into Track {tid}",
                    "",
                    "Audio (*.wav *.flac *.mp3 *.aac);;All Files (*)",
                )
                if path:
                    self._import_audio_to_track(Path(path), tid)

        def _import_audio_to_track(self, path: Path, track_id: str) -> None:
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

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
            self._show_status(f"Imported audio asset {path.name} onto track {track_id}")

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
            track_id = {
                "Dubbed Voice (A2)": "A2",
                "Music (A3)": "A3",
                "SFX (A4)": "A4",
                "Ambience (A5)": "A5",
            }[selection]
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

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

        def _on_dialogue_card_selected(self, idx: int, data: dict[str, Any]) -> None:
            start_s = float(data.get("start", 0.0))
            self.canvas_view.set_playhead(start_s)
            self.monitor_panel.set_playhead(start_s)
            self.timeline_bar.set_timecode(start_s)
            self._show_status(f"Selected Dialogue Line #{idx + 1} at {_format_tc(start_s)}")

        def _on_timeline_clip_clicked(self, clip_info: dict[str, Any]) -> None:
            lbl = clip_info.get("label", "")
            tid = clip_info.get("tid", "")
            self._active_clip_info = clip_info
            self.clip_selected.emit(clip_info)
            start = float(clip_info.get("start", 0.0))
            duration = float(clip_info.get("dur", 0.0))
            score = clip_info.get("score")

            clip_key = f"{tid}:{round(start, 3)}"
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            char_name = clip_chars.get(clip_key)
            if not char_name:
                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                spk, _ = extract_speaker_from_cue_text(lbl)
                char_name = spk or str(self._current_project_data.get("character", "SPEAKER_00"))
                clip_chars[clip_key] = char_name

            self.monitor_panel.set_playhead(start)
            self.canvas_view.set_playhead(start)
            if tid.startswith("S"):
                if tid == "S1":
                    orig = lbl
                    matching = self._matching_subtitle("S2", start, duration)
                    trans = matching[3] if matching is not None else ""
                else:
                    matching = self._matching_subtitle("S1", start, duration)
                    orig = matching[3] if matching is not None else ""
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
                self.inspector_panel.set_timing_alert(duration, duration)
                self._show_status(f"Selected Subtitle Clip [{tid}]: '{lbl}'")
            elif tid == "A2":
                source_cue = self._matching_subtitle("S1", start, duration)
                target_cue = self._matching_subtitle("S2", start, duration)
                orig = source_cue[3] if source_cue is not None else ""
                trans = target_cue[3] if target_cue is not None else ""
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
                self.inspector_panel.set_timing_alert(source_duration, duration)
                self.inspector_panel.take_combo.setCurrentText(lbl.replace(" ★", ""))
                self._show_status(f"Selected Dub Audio Clip [{tid}]: '{lbl}'")

        def _on_track_level_changed(self, track_id: str, level: float) -> None:
            self._mixer_levels[track_id] = level
            if track_id == "master":
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel.set_volume(int(level * 100))
            is_clip = level > 1.2 or (self._mixer_levels.get("A1", 1.0) * level > 1.4)
            peak_db = 20.0 * math.log10(max(1e-4, level))
            self.inspector_panel.set_peak_warning(is_clip, peak_db)

        def _on_track_mute_toggled(self, track_id: str, muted: bool) -> None:
            if muted:
                self._mixer_mutes.add(track_id)
            else:
                self._mixer_mutes.discard(track_id)
            if track_id == "master":
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel.set_muted(muted)
            self._show_status(f"Track {track_id} {'MUTED' if muted else 'UNMUTED'}.")

        def _on_track_solo_toggled(self, track_id: str, solo: bool) -> None:
            if solo:
                self._mixer_solos.add(track_id)
            else:
                self._mixer_solos.discard(track_id)
            self._show_status(f"Track {track_id} {'SOLO' if solo else 'UNSOLO'}.")

        def _on_ducking_changed(self, enabled: bool, depth_db: float) -> None:
            self._sidechain_ducking_enabled = enabled
            self._sidechain_ducking_depth = depth_db
            status_txt = f"Sidechain ducking {'ENABLED (-' + str(int(depth_db)) + 'dB)' if enabled else 'DISABLED'}."
            self._show_status(status_txt)

        def _on_fit_to_slot(self) -> None:
            """Apply time-stretching to fit active dubbing take into target slot duration."""
            if not self._active_clip_info:
                self._show_status("Select a dialogue clip to fit to slot.")
                return
            start = float(self._active_clip_info.get("start", 0.0))
            current_dur = float(self._active_clip_info.get("dur", 0.0))
            source_dur = self._nearest_source_duration(start, current_dur)
            if source_dur <= 0 or abs(current_dur - source_dur) < 0.05:
                self._show_status("Clip already matches target slot duration.")
                return
            self.canvas_view._update_clip_timing(self._active_clip_info, start, source_dur)
            self._active_clip_info["dur"] = source_dur
            self.inspector_panel.set_timing_alert(source_dur, source_dur)
            self._show_status(
                f"⚡ Fitted clip duration from {current_dur:.2f}s to {source_dur:.2f}s."
            )

        def _on_nudge_timing(self, delta_s: float) -> None:
            """Nudge selected clip timing forward/backward."""
            if not self._active_clip_info:
                self._show_status("Select a clip to nudge timing.")
                return
            start = float(self._active_clip_info.get("start", 0.0))
            dur = float(self._active_clip_info.get("dur", 0.0))
            new_start = max(0.0, start + delta_s)
            self.canvas_view._update_clip_timing(self._active_clip_info, new_start, dur)
            self._active_clip_info["start"] = new_start
            self.canvas_view.set_playhead(new_start)
            self.monitor_panel.set_playhead(new_start)
            self._show_status(f"⏱ Nudged clip by {delta_s:+.2f}s to {_format_tc(new_start)}.")

        def _nearest_source_duration(self, start: float, fallback: float) -> float:
            source_clips = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == "S1"
            ]
            if not source_clips:
                return fallback
            nearest = min(source_clips, key=lambda clip: abs(float(clip[1]) - start))
            if abs(float(nearest[1]) - start) > max(1.0, float(nearest[2])):
                return fallback
            return float(nearest[2])

        def _matching_subtitle(
            self,
            track_id: str,
            start: float,
            duration: float = 1.0,
        ) -> ClipTuple | None:
            candidates = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == track_id
            ]
            if not candidates:
                return None
            end = start + max(0.1, duration)
            for clip in candidates:
                c_start = float(clip[1])
                c_end = c_start + max(0.1, float(clip[2]))
                if max(start, c_start) < min(end, c_end):
                    score = float(clip[4]) if len(clip) > 4 and clip[4] is not None else None
                    return (str(clip[0]), float(clip[1]), float(clip[2]), str(clip[3]), score)
            nearest = min(candidates, key=lambda clip: abs(float(clip[1]) - start))
            if abs(float(nearest[1]) - start) <= 2.0:
                score = float(nearest[4]) if len(nearest) > 4 and nearest[4] is not None else None
                return (
                    str(nearest[0]),
                    float(nearest[1]),
                    float(nearest[2]),
                    str(nearest[3]),
                    score,
                )
            return None

        def _on_original_changed(self, text: str) -> None:
            self._current_project_data["original_text"] = text
            active = self._active_clip_info or {}
            if active.get("tid") == "S1":
                self.canvas_view.update_subtitle_text(text, float(active.get("start", 0.0)))

        def _on_character_changed(self, char_name: str) -> None:
            char_name = char_name.strip()
            if not char_name:
                return
            self._current_project_data["character"] = char_name
            active = self._active_clip_info or {}
            if active:
                active["character"] = char_name
                tid = active.get("tid", "")
                start = float(active.get("start", 0.0))
                clip_key = f"{tid}:{round(start, 3)}"
                self._current_project_data.setdefault("clip_characters", {})[clip_key] = char_name
                self._show_status(f"Character set to '{char_name}' for [{tid}] at {start:.2f}s")

        def _compute_character_counts(self) -> dict[str, int]:
            """Compute accurate line/cue counts per character across timeline cues."""
            from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

            counts: dict[str, int] = {}
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            for clip in clips:
                tid, start_s = clip[0], float(clip[1])
                key = f"{tid}:{round(start_s, 3)}"
                char = clip_chars.get(key)
                if not char:
                    spk, _ = extract_speaker_from_cue_text(clip[3])
                    char = spk or str(self._current_project_data.get("character", "SPEAKER_00"))
                    clip_chars[key] = char
                counts[char] = counts.get(char, 0) + 1
            return counts

        def _open_character_manager(self) -> None:
            from aidub.ui.character_manager_dialog import CharacterManagerDialog

            counts = self._compute_character_counts()
            if not counts:
                counts = {"SPEAKER_00": 0, "SPEAKER_01": 0}

            voices = self._current_project_data.get("character_voices", {})
            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            dlg = CharacterManagerDialog(
                counts,
                voices,
                parent=self,
                media_path=self._current_project_data.get("file_path"),
                clips=clips,
                clip_characters=self._current_project_data.get("clip_characters", {}),
            )
            dlg.characters_updated.connect(self._on_characters_updated)
            dlg.exec()

        def _on_characters_updated(self, data: dict[str, Any]) -> None:
            renames = data.get("renames", {})
            voices = data.get("voices", {})
            characters = data.get("characters", [])

            clip_chars = self._current_project_data.setdefault("clip_characters", {})

            if renames:
                for old_c, new_c in renames.items():
                    for k, v in list(clip_chars.items()):
                        if v == old_c:
                            clip_chars[k] = new_c
                    if self._current_project_data.get("character") == old_c:
                        self._current_project_data["character"] = new_c
                self._show_status(f"Characters renamed/reassigned: {renames}")

            if voices:
                self._current_project_data["character_voices"] = voices

            if characters:
                self.inspector_panel.update_characters(characters)
                self.inspector_panel.meta_chars_lbl.setText(f"{len(characters)} speakers")

            # Update active clip's character in inspector
            if self._active_clip_info:
                tid = self._active_clip_info.get("tid", "")
                start = float(self._active_clip_info.get("start", 0.0))
                active_char = clip_chars.get(
                    f"{tid}:{round(start, 3)}"
                ) or self._current_project_data.get("character", "")
                if active_char:
                    self.inspector_panel.char_in.blockSignals(True)
                    self.inspector_panel.char_in.setCurrentText(active_char)
                    self.inspector_panel.char_in.blockSignals(False)

        def auto_detect_characters(self) -> list[str]:
            """Detect and recognize movie characters from dialogue cues, media audio, and diarization."""
            from aidub.ai.voice.character_cloning_engine import (
                CharacterDetectionEngine,
                extract_speaker_from_cue_text,
            )

            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            media_path = str(self._current_project_data.get("file_path", ""))

            detected_names: set[str] = set()

            # 1. Scan existing timeline clips for speaker tags (e.g. [SPEAKER_00] or John:)
            for clip in clips:
                tid, start_s, _dur, text = clip[0], float(clip[1]), float(clip[2]), clip[3]
                key = f"{tid}:{round(start_s, 3)}"
                spk, _clean = extract_speaker_from_cue_text(text)
                if spk:
                    clip_chars[key] = spk
                    detected_names.add(spk)

            # 2. Check work_dir for asr_segments.json
            for cand_dir in (self._session_store.workspace, Path.cwd() / "work"):
                asr_json = cand_dir / "asr_segments.json"
                if asr_json.is_file():
                    try:
                        segs = json.loads(asr_json.read_text(encoding="utf-8"))
                        engine = CharacterDetectionEngine()
                        chars = engine.detect_movie_characters(segs)
                        for c in chars:
                            detected_names.add(c.canonical_name)
                        for seg in segs:
                            start_s = float(seg.get("start", 0.0))
                            spk = str(seg.get("speaker", "0"))
                            spk_label = (
                                f"Speaker {spk}" if not spk.lower().startswith("speaker") else spk
                            )
                            clip_chars[f"S1:{round(start_s, 3)}"] = spk_label
                            clip_chars[f"S2:{round(start_s, 3)}"] = spk_label
                        break
                    except Exception:
                        pass

            # 3. If still no characters detected and media_path exists, run media diarization
            if not detected_names and media_path and Path(media_path).is_file():
                try:
                    engine = CharacterDetectionEngine()
                    chars, _turns = engine.detect_from_media(
                        media_path, self._automation_state.target_language
                    )
                    for c in chars:
                        detected_names.add(c.canonical_name)
                except Exception as exc:
                    logger.debug("Media diarization character detection: %s", exc)

            if not detected_names:
                detected_names = {"SPEAKER_00", "SPEAKER_01"}

            # Map default voices for detected characters
            voices = self._current_project_data.setdefault("character_voices", {})
            available_voices = [
                "bn-BD-PradeepNeural",
                "bn-BD-NabanitaNeural",
                "bn-IN-BashkarNeural",
                "bn-IN-TanishaaNeural",
            ]
            sorted_chars = sorted(detected_names)
            for idx, char in enumerate(sorted_chars):
                if char not in voices:
                    voices[char] = available_voices[idx % len(available_voices)]

            # If cues had no character assigned, assign default
            for clip in clips:
                tid, start_s = clip[0], float(clip[1])
                key = f"{tid}:{round(start_s, 3)}"
                if key not in clip_chars:
                    clip_chars[key] = sorted_chars[0]

            self.inspector_panel.update_characters(sorted_chars)
            self.inspector_panel.meta_chars_lbl.setText(f"{len(sorted_chars)} speakers")
            self._show_status(
                f"Recognized {len(sorted_chars)} character(s): {', '.join(sorted_chars)}"
            )
            return sorted_chars

        def import_bilingual_subtitle_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Bilingual Subtitles",
                self._default_asset_directory(),
                "Subtitles (*.srt *.vtt);;All Files (*)",
            )
            if path:
                self.import_bilingual_subtitle_file(path)

        def import_bilingual_subtitle_file(self, path: str) -> None:
            from aidub.subtitles.codec import parse_srt, parse_webvtt

            content = Path(path).read_text(encoding="utf-8-sig")
            doc = parse_webvtt(content) if path.lower().endswith(".vtt") else parse_srt(content)

            s1_cues: list[ClipTuple] = []
            s2_cues: list[ClipTuple] = []

            for cue in doc.cues:
                start_s = cue.time_range.start.ticks / 1000.0
                end_s = cue.time_range.end_exclusive.ticks / 1000.0
                dur_s = max(0.001, end_s - start_s)

                lines = [line.strip() for line in cue.text.splitlines() if line.strip()]
                if len(lines) >= 2:
                    s1_text = lines[0]
                    s2_text = lines[1]
                elif lines:
                    s1_text = lines[0]
                    s2_text = lines[0]
                else:
                    continue

                s1_cues.append(("S1", start_s, dur_s, s1_text, None))
                s2_cues.append(("S2", start_s, dur_s, s2_text, None))

            if s1_cues or s2_cues:
                other_clips = [
                    c
                    for c in self._current_project_data.get("clips", [])
                    if c[0] not in {"S1", "S2"}
                ]
                all_clips = other_clips + s1_cues + s2_cues
                all_clips.sort(key=lambda c: (c[1], c[0]))
                current_duration = float(self._current_project_data.get("duration", 1.0))
                dur = max([c[1] + c[2] for c in all_clips] + [current_duration])

                self._current_project_data["clips"] = all_clips
                self._current_project_data["duration"] = dur
                self.canvas_view.set_clips(all_clips, dur)

                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                clip_chars = self._current_project_data.setdefault("clip_characters", {})
                detected_chars: set[str] = set()
                for c in s1_cues + s2_cues:
                    spk, _ = extract_speaker_from_cue_text(c[3])
                    if spk:
                        clip_chars[f"{c[0]}:{round(float(c[1]), 3)}"] = spk
                        detected_chars.add(spk)
                if detected_chars:
                    self.inspector_panel.update_characters(sorted(detected_chars))
                    self.inspector_panel.meta_chars_lbl.setText(f"{len(detected_chars)} speakers")

                if s1_cues:
                    self._current_project_data["original_text"] = s1_cues[0][3]
                if s2_cues:
                    self._current_project_data["translation_text"] = s2_cues[0][3]

                self.inspector_panel.update_clip_info(
                    str(self._current_project_data.get("original_text", "")),
                    str(self._current_project_data.get("translation_text", "")),
                    str(self._current_project_data.get("character", "")),
                    self._automation_state.target_language,
                )
                self.inspector_panel.update_metadata_display(self._current_project_data)
                self._show_status(
                    f"Imported bilingual subtitles: {len(s1_cues)} cues loaded to S1 and S2"
                )

        def _on_translation_changed(self, text: str) -> None:
            self._current_project_data["translation_text"] = text
            active = self._active_clip_info or {}
            if active.get("tid") in {"S1", "S2", "A2"}:
                self.canvas_view.update_subtitle_text(text, float(active.get("start", 0.0)))

        def _commit_translation(self) -> None:
            text = self.inspector_panel.trans_in.text().strip()
            active = self._active_clip_info or {}
            if active.get("tid") not in {"S1", "S2", "A2"}:
                return
            start = float(active.get("start", 0.0))
            duration = float(active.get("dur", 0.0))
            if duration <= 0 or not text:
                return

            previous = list(self._current_project_data.get("clips", []))
            updated = list(previous)
            target_index = next(
                (
                    index
                    for index, clip in enumerate(updated)
                    if clip[0] == "S2" and abs(float(clip[1]) - start) < 0.05
                ),
                None,
            )
            if target_index is None:
                updated.append(("S2", start, duration, text, None))
            else:
                old = updated[target_index]
                updated[target_index] = ("S2", old[1], old[2], text, old[4])
            if updated == previous:
                return

            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = updated
            self.canvas_view.set_clips(
                updated,
                float(self._current_project_data.get("duration", 1.0)),
            )
            cue = self._matching_subtitle("S2", start)
            if cue is not None:
                self._active_clip_info = {
                    "tid": "S2",
                    "start": cue[1],
                    "dur": cue[2],
                    "label": cue[3],
                    "score": cue[4],
                }
            self._show_status("Target subtitle cue saved on the selected timeline time")

        def _on_ai_action_clicked(self, action_name: str) -> None:
            if action_name in {"Extract Dialogue Audio", "Extract Audio"}:
                self._run_modular_extract_audio()
            elif action_name in {"Transcribe Speech (S1)", "Transcribe Speech", "Transcribe"}:
                self._run_modular_transcribe_speech()
            elif action_name in {
                "Translate Subtitles (S2)",
                "Translate Subtitles",
                "Translate S1 to S2",
            }:
                self._run_modular_translate_subtitles()
            elif action_name in {
                "Synthesize Voices (A2)",
                "Synthesize Voices",
                "Synthesize Dialogue",
            }:
                self._run_modular_synthesize_voices()
            elif action_name in {
                "Render Master Video",
                "Render Video Master",
                "Render Master",
            }:
                self._run_modular_render_master()
            elif action_name in {"Auto-Detect Characters", "Auto-Detect Movie Characters"}:
                self.auto_detect_characters()
            elif action_name in {
                "Select Dub Voice",
                "Voice Model",
                "AI Voice Engine",
                "Chatterbox",
            }:
                self._open_voice_model_selector()
            elif action_name in {"Kaggle GPU", "Cloud GPU Accelerator", "Kaggle Accelerator"}:
                self._open_kaggle_accelerator()
            elif action_name in {"Audio Analysis", "Audio Analysis & Diagnostics"}:
                self._open_audio_analysis()
            elif action_name in {"Manage Characters", "Character & Speaker Manager"}:
                self._open_character_manager()
            elif action_name == "Subtitle QC":
                self._run_subtitle_qc()
            elif action_name == "Pipeline Readiness":
                self._show_pipeline_readiness()
            elif action_name == "Improve Emotion":
                self._run_translation_assistant(
                    shorten=False,
                    instruction_override=(
                        "Rewrite the localized line for a more emotionally faithful screen "
                        "performance while preserving meaning and timing."
                    ),
                )
            elif action_name == "Match Timing":
                self._apply_timing_fix()
            elif action_name in {"Rewrite Translation", "Shorten Translation"}:
                self._run_translation_assistant(shorten=action_name.startswith("Shorten"))
            elif action_name in {
                "Lip Sync Shot",
                "Lip Sync",
                "Render Lip Sync",
                "Selective Lip Sync",
            }:
                self._render_lip_sync()
            elif action_name == "Fix Pronunciation":
                self._run_translation_assistant(
                    shorten=False,
                    instruction_override=(
                        "Revise the localized dialogue for unambiguous natural pronunciation "
                        "while preserving the character's words and intent."
                    ),
                )
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
                self._show_status(f"No operation is registered for: {action_name}")

        def _get_work_dir(self, subfolder: str = "work") -> Path:
            proj = getattr(self, "_active_opened_project", None)
            if proj is not None and hasattr(proj, "paths"):
                return Path(proj.paths.work)
            p = self._session_store.workspace / subfolder
            p.mkdir(parents=True, exist_ok=True)
            return p

        def _run_modular_extract_audio(self) -> None:
            if (
                hasattr(self, "_extraction_worker")
                and self._extraction_worker is not None
                and self._extraction_worker.isRunning()
            ):
                self._show_status("Audio extraction is already running")
                return
            video_file = self._current_project_data.get("file_path")
            if not video_file or not Path(str(video_file)).is_file():
                self._show_status("Please open or import a video file first")
                return
            v_path = Path(str(video_file))
            work_dir = self._get_work_dir("work")
            out_audio = work_dir / f"{v_path.stem}_audio16k.wav"

            from aidub.ui.workers import ModularExtractionWorker

            self._extraction_worker = ModularExtractionWorker(v_path, out_audio, parent=self)

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Extract Audio: {pct}% · {msg}")
                self.ai_overlay.set_progress(f"Extracting Audio: {pct}%", pct)

            def _on_done(audio_file: str, dur_s: float) -> None:
                self._current_project_data["extracted_audio"] = audio_file
                clips = list(self._current_project_data.get("clips", []))
                clips = [c for c in clips if c[0] != "A1"]
                clips.insert(0, ("A1", 0.0, dur_s, "Production Dialogue", None))
                self._current_project_data["clips"] = clips
                self.canvas_view.set_clips(
                    clips, max(dur_s, float(self._current_project_data.get("duration", 1.0)))
                )
                self._show_status(
                    f"Dialogue audio extracted ({dur_s:.1f}s): {Path(audio_file).name}"
                )
                self.ai_overlay.set_progress("Audio Extracted (100%)", 100)
                self._extraction_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Audio extraction failed: {err}")
                self.ai_overlay.set_progress("Audio extraction failed", 0)
                self._extraction_worker = None

            def _on_cancel() -> None:
                self._show_status("Audio extraction cancelled by operator")
                self.ai_overlay.set_progress("Extraction cancelled", 0)
                self._extraction_worker = None

            self._extraction_worker.progress_updated.connect(_on_prog)
            self._extraction_worker.extraction_completed.connect(_on_done)
            self._extraction_worker.extraction_failed.connect(_on_fail)
            self._extraction_worker.extraction_cancelled.connect(_on_cancel)
            self._extraction_worker.start()
            self._show_status(f"Started audio extraction from {v_path.name}…")

        def _run_modular_transcribe_speech(self) -> None:
            if (
                hasattr(self, "_transcription_worker")
                and self._transcription_worker is not None
                and self._transcription_worker.isRunning()
            ):
                self._show_status("Speech transcription is already running")
                return
            audio_file = self._current_project_data.get("extracted_audio")
            if not audio_file or not Path(str(audio_file)).is_file():
                video_file = self._current_project_data.get("file_path")
                if video_file and Path(str(video_file)).is_file():
                    audio_file = str(video_file)
                else:
                    self._show_status("Please open or import a media file first")
                    return

            from aidub.ui.workers import ModularTranscriptionWorker

            opened = getattr(self, "_active_opened_project", None)
            src_proj = getattr(opened, "project", None)
            lang_tag = src_proj.settings.source_language if src_proj else "en"

            self._transcription_worker = ModularTranscriptionWorker(
                audio_path=audio_file,
                language=lang_tag if lang_tag != "auto" else None,
                model_size="base",
                parent=self,
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"ASR: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(cues: list[Any]) -> None:
                clips = [c for c in self._current_project_data.get("clips", []) if c[0] != "S1"]
                for cue in cues:
                    clips.append(("S1", cue.start_s, cue.duration_s, cue.text, cue.confidence))
                self._current_project_data["clips"] = clips
                self._current_project_data["cues"] = cues
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                if cues:
                    tot_dur = max(tot_dur, *(c.end_s for c in cues))
                self.canvas_view.set_clips(clips, tot_dur)
                if cues:
                    self.inspector_panel.orig_in.setText(cues[0].text)
                    self.inspector_panel.char_in.setCurrentText(cues[0].speaker)
                self.save_to_project()
                self._show_status(f"Transcribed {len(cues)} dialogue cues into track S1.")
                self.ai_overlay.set_complete(f"Transcribed {len(cues)} cues (S1)")
                self._transcription_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Transcription failed: {err}")
                self.ai_overlay.set_progress("Transcription failed", 0)
                self._transcription_worker = None

            def _on_cancel() -> None:
                self._show_status("Transcription cancelled by operator")
                self.ai_overlay.set_progress("Transcription cancelled", 0)
                self._transcription_worker = None

            self._transcription_worker.progress_updated.connect(_on_prog)
            self._transcription_worker.transcription_completed.connect(_on_done)
            self._transcription_worker.transcription_failed.connect(_on_fail)
            self._transcription_worker.transcription_cancelled.connect(_on_cancel)
            self._transcription_worker.start()
            self._show_status("Started speech recognition (Faster-Whisper)…")

        def _run_modular_translate_subtitles(self) -> None:
            if (
                hasattr(self, "_translation_worker")
                and self._translation_worker is not None
                and self._translation_worker.isRunning()
            ):
                self._show_status("Translation is already running")
                return
            clips = self._current_project_data.get("clips", [])
            s1_clips = [c for c in clips if c[0] == "S1"]
            if not s1_clips:
                self._show_status(
                    "No source dialogue cues in S1. Transcribe speech or import an SRT first."
                )
                return

            from aidub.application.modular_pipeline import TranscriptCue
            from aidub.ui.workers import ModularTranslationWorker

            cues: list[TranscriptCue] = []
            for idx, c in enumerate(s1_clips):
                cues.append(
                    TranscriptCue(
                        cue_id=f"cue_{idx + 1:04d}",
                        start_s=float(c[1]),
                        end_s=float(c[1]) + float(c[2]),
                        text=str(c[3]),
                        speaker="SPEAKER_00",
                        confidence=float(c[4]) if len(c) > 4 and c[4] is not None else 1.0,
                    )
                )

            src_lang = "en-US"
            tgt_lang = (
                self.inspector_panel.lang_in.text().strip()
                or self._automation_state.target_language
                or "bn-BD"
            )

            self._translation_worker = ModularTranslationWorker(
                cues=cues,
                source_lang=src_lang,
                target_lang=tgt_lang,
                parent=self,
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Translate: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(translated_cues: list[Any]) -> None:
                clips_updated = [
                    c for c in self._current_project_data.get("clips", []) if c[0] != "S2"
                ]
                for t in translated_cues:
                    clips_updated.append(
                        ("S2", t.start_s, t.duration_s, t.target_text, t.confidence)
                    )
                self._current_project_data["clips"] = clips_updated
                self._current_project_data["translated_cues"] = translated_cues
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                self.canvas_view.set_clips(clips_updated, tot_dur)
                if translated_cues:
                    self.inspector_panel.trans_in.setText(translated_cues[0].target_text)
                self.save_to_project()
                self._show_status(
                    f"Translated {len(translated_cues)} cues into track S2 ({tgt_lang})."
                )
                self.ai_overlay.set_complete(f"Translated {len(translated_cues)} cues (S2)")
                self._translation_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Translation failed: {err}")
                self.ai_overlay.set_progress("Translation failed", 0)
                self._translation_worker = None

            def _on_cancel() -> None:
                self._show_status("Translation cancelled by operator")
                self.ai_overlay.set_progress("Translation cancelled", 0)
                self._translation_worker = None

            self._translation_worker.progress_updated.connect(_on_prog)
            self._translation_worker.translation_completed.connect(_on_done)
            self._translation_worker.translation_failed.connect(_on_fail)
            self._translation_worker.translation_cancelled.connect(_on_cancel)
            self._translation_worker.start()
            self._show_status(f"Translating {len(cues)} cues to {tgt_lang}…")

        def _run_modular_synthesize_voices(self) -> None:
            if (
                hasattr(self, "_batch_tts_worker")
                and self._batch_tts_worker is not None
                and self._batch_tts_worker.isRunning()
            ):
                self._show_status("Voice synthesis is already running")
                return
            clips = self._current_project_data.get("clips", [])
            s2_clips = [c for c in clips if c[0] == "S2"]
            if not s2_clips:
                s2_clips = [c for c in clips if c[0] == "S1"]
            if not s2_clips:
                self._show_status(
                    "No dialogue cues in S2 or S1 to synthesize. Transcribe or translate first."
                )
                return

            from aidub.application.modular_pipeline import TranslatedCue
            from aidub.ui.workers import ModularBatchSynthesisWorker

            tgt_lang = (
                self.inspector_panel.lang_in.text().strip()
                or self._automation_state.target_language
                or "bn-BD"
            )
            work_dir = self._get_work_dir("takes")

            cues: list[TranslatedCue] = []
            for idx, c in enumerate(s2_clips):
                cues.append(
                    TranslatedCue(
                        cue_id=f"cue_{idx + 1:04d}",
                        start_s=float(c[1]),
                        end_s=float(c[1]) + float(c[2]),
                        source_text=str(c[3]),
                        target_text=str(c[3]),
                        target_language=tgt_lang,
                        speaker="SPEAKER_00",
                        confidence=float(c[4]) if len(c) > 4 and c[4] is not None else 1.0,
                    )
                )

            self._batch_tts_worker = ModularBatchSynthesisWorker(
                cues=cues,
                target_lang=tgt_lang,
                output_dir=work_dir,
                voice_name=self._selected_voice_name,
                parent=self,
            )
            self._synthesis_worker = self._batch_tts_worker

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"TTS: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(takes: list[Any]) -> None:
                clips_updated = [
                    c for c in self._current_project_data.get("clips", []) if c[0] != "A2"
                ]
                flagged_count = 0
                for take in takes:
                    if take.flagged_for_review:
                        flagged_count += 1
                    clips_updated.append(
                        (
                            "A2",
                            take.start_s,
                            take.actual_duration_s,
                            f"{take.voice_name} [{take.cue_id}]",
                            None,
                        )
                    )
                self._current_project_data["clips"] = clips_updated
                self._current_project_data["takes"] = takes
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                self.canvas_view.set_clips(clips_updated, tot_dur)
                if takes:
                    self.inspector_panel.set_take_audio(
                        f"Take {takes[0].cue_id}", takes[0].audio_path
                    )
                msg = f"Synthesized {len(takes)} voice takes onto track A2."
                if flagged_count > 0:
                    msg += f" Note: {flagged_count} take(s) flagged for timing review."
                self._show_status(msg)
                self.ai_overlay.set_complete(msg)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Voice synthesis failed: {err}")
                self.ai_overlay.set_progress("Voice synthesis failed", 0)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            def _on_cancel() -> None:
                self._show_status("Voice synthesis cancelled by operator")
                self.ai_overlay.set_progress("Synthesis cancelled", 0)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            self._batch_tts_worker.progress_updated.connect(_on_prog)
            self._batch_tts_worker.synthesis_completed.connect(_on_done)
            self._batch_tts_worker.synthesis_failed.connect(_on_fail)
            self._batch_tts_worker.synthesis_cancelled.connect(_on_cancel)
            self._batch_tts_worker.start()
            self._show_status(f"Started synthesis of {len(cues)} voice cues ({tgt_lang})…")

        def _run_modular_render_master(self) -> None:
            if (
                hasattr(self, "_render_worker")
                and self._render_worker is not None
                and self._render_worker.isRunning()
            ):
                self._show_status("Rendering is already in progress")
                return
            video_file = self._current_project_data.get("file_path")
            if not video_file or not Path(str(video_file)).is_file():
                self._show_status("Please open or import a source video file first")
                return

            v_path = Path(str(video_file))
            takes = self._current_project_data.get("takes", [])
            work_dir = self._get_work_dir("work")

            from aidub.application.modular_pipeline import ModularDubbingPipelineService
            from aidub.ui.workers import ModularRenderWorker

            if takes:
                service = ModularDubbingPipelineService()
                tot_dur = float(self._current_project_data.get("duration", 10.0))
                audio_for_render = work_dir / f"{v_path.stem}_dubbed_mix.wav"
                service.mix_timeline_audio(takes, tot_dur, audio_for_render)
            else:
                extracted = self._current_project_data.get("extracted_audio")
                if extracted and Path(str(extracted)).is_file():
                    audio_for_render = Path(str(extracted))
                else:
                    self._show_status(
                        "Synthesize voice takes (A2) or extract audio before rendering master."
                    )
                    return

            out_dir = v_path.parent / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_master = out_dir / f"{v_path.stem}_master_rendered.mp4"

            self._render_worker = ModularRenderWorker(
                v_path, audio_for_render, output_master, parent=self
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Render: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(res_path: str) -> None:
                self._current_project_data["rendered_master"] = res_path
                self._show_status(f"Master video rendered successfully: {Path(res_path).name}")
                self.ai_overlay.set_complete("Master video rendered")
                if Path(res_path).is_file():
                    try:
                        self.monitor_panel.load_media(res_path)
                        self.monitor_panel.prog_title_lbl.setText(
                            f"Program: {Path(res_path).stem} [RENDERED MASTER]"
                        )
                    except Exception as exc:
                        logger.debug("Failed loading rendered master in monitor: %s", exc)
                self._render_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Rendering failed: {err}")
                self.ai_overlay.set_progress("Rendering failed", 0)
                self._render_worker = None

            def _on_cancel() -> None:
                self._show_status("Rendering cancelled by operator")
                self.ai_overlay.set_progress("Rendering cancelled", 0)
                self._render_worker = None

            self._render_worker.progress_updated.connect(_on_prog)
            self._render_worker.render_completed.connect(_on_done)
            self._render_worker.render_failed.connect(_on_fail)
            self._render_worker.render_cancelled.connect(_on_cancel)
            self._render_worker.start()
            self._show_status(f"Started master rendering: {output_master.name}…")

        def _render_lip_sync(self) -> None:
            """Render lip-sync video for the active project/shot."""
            if not self._current_project_data.get("file_path"):
                self._show_status("Open a project with a video file before running lip-sync.")
                return
            video_path = Path(str(self._current_project_data["file_path"]))
            if not video_path.is_file():
                self._show_status(f"Video file does not exist: {video_path}")
                return

            generated = self._current_project_data.get("generated_paths", ())
            audio_path: Path | None = None
            for p in generated:
                candidate = Path(p)
                if candidate.suffix.lower() in {".wav", ".m4a", ".mp3"} and candidate.is_file():
                    audio_path = candidate
                    break

            if not audio_path:
                work_dir = video_path.parent / "work"
                for candidate_name in ("dubbed_vocals.wav", "dubbed_audio.m4a", "vocals.wav"):
                    cand = work_dir / candidate_name
                    if cand.is_file():
                        audio_path = cand
                        break

            if not audio_path:
                self._show_status(
                    "Dubbed audio not found. Run 'Auto Dub Master' first before rendering lip-sync."
                )
                return

            out_dir = video_path.parent / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_file = out_dir / f"{video_path.stem}_lipsync.mp4"

            from aidub.ui.workers import LipSyncRenderWorker

            self._show_status("Lip-sync render started in background...")
            self.ai_overlay.set_progress("Rendering lip-sync...", 15)

            worker = LipSyncRenderWorker(
                video_path=video_path,
                audio_path=audio_path,
                output_file=output_file,
                model_name="musetalk",
                parent=self,
            )
            self._active_lipsync_worker = worker

            def _on_progress(pct: int, msg: str) -> None:
                self.ai_overlay.set_progress(msg, pct)
                self._show_status(f"Lip-Sync · {pct}% · {msg}")

            def _on_completed(res_path: str) -> None:
                self._show_status(f"Lip-sync completed: {res_path}")
                self.ai_overlay.set_complete("Lip-sync render complete")
                state = self._automation_state
                state = state.update_stage(
                    AutomationStage.LIP_SYNC,
                    status=StageStatus.SUCCEEDED,
                    progress=100,
                    detail=f"Rendered: {Path(res_path).name}",
                )
                self._automation_state = state
                self._persist_automation_state()
                self.ai_overlay.set_state(state)
                self.inspector_panel.l_score_lbl.setText("Lip Sync:  Rendered (100%)")
                self.inspector_panel.l_score_lbl.setStyleSheet("color:#4ADE80;font-weight:700;")
                if Path(res_path).is_file():
                    try:
                        self.monitor_panel.load_media(res_path)
                        self.monitor_panel.load_comparison_media(str(video_path))
                        self.monitor_panel.prog_title_lbl.setText(
                            f"Program: {Path(res_path).stem} [LIP-SYNCED MASTER]"
                        )
                    except Exception as exc:
                        logger.debug("Failed loading lipsynced master into monitor: %s", exc)
                self._active_lipsync_worker = None

            def _on_failed(err: str) -> None:
                self._show_status(f"Lip-sync failed: {err}")
                self.ai_overlay.set_progress("Lip-sync failed", 0)
                state = self._automation_state
                state = state.update_stage(
                    AutomationStage.LIP_SYNC,
                    status=StageStatus.FAILED,
                    progress=0,
                    detail=err[-80:],
                )
                self._automation_state = state
                self._persist_automation_state()
                self.ai_overlay.set_state(state)
                self._active_lipsync_worker = None

            worker.lipsync_progress.connect(_on_progress)
            worker.lipsync_completed.connect(_on_completed)
            worker.lipsync_failed.connect(_on_failed)
            worker.start()

        def _select_dub_voice(self) -> None:
            from aidub.adapters.voice.edge_tts_adapter import (
                available_voices_for_language,
                default_voice_for_language,
            )

            language = self._automation_state.target_language
            try:
                voices = available_voices_for_language(language)
            except ValueError as exc:
                self._show_status(str(exc))
                return
            selected, accepted = QInputDialog.getItem(
                self,
                "Dub Voice",
                f"Choose the synthesized voice for {language} dialogue:",
                list(voices),
                max(0, voices.index(self._selected_voice_name))
                if self._selected_voice_name in voices
                else 0,
                False,
            )
            if accepted and selected:
                self._selected_voice_name = selected
                self._show_status(f"Dub voice set to {selected}")
            elif self._selected_voice_name is None:
                self._selected_voice_name = default_voice_for_language(language)

        def _on_ai_regenerate_voice(self) -> None:
            if self._tts_worker is not None and self._tts_worker.isRunning():
                self._show_status("Voice synthesis is already running")
                return
            text = self.inspector_panel.trans_in.text().strip()
            if not text:
                text = self.inspector_panel.orig_in.text().strip()
                if text:
                    self.inspector_panel.trans_in.setText(text)
            if not text:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S2", "S1", "A2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                    text = (
                        self.inspector_panel.trans_in.text().strip()
                        or self.inspector_panel.orig_in.text().strip()
                    )
            if not text:
                self._show_status("Enter a translated dialogue line before synthesis")
                return
            from aidub.ui.workers import TTSPreviewWorker

            preview_dir = self._session_store.workspace / "previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            take_index = len(self._current_project_data.get("clips", [])) + 1
            output = preview_dir / f"take_{take_index:04d}.mp3"
            while output.exists():
                take_index += 1
                output = preview_dir / f"take_{take_index:04d}.mp3"
            from aidub.adapters.voice.edge_tts_adapter import default_voice_for_language

            active_char = self.inspector_panel.char_in.currentText().strip() or str(
                self._current_project_data.get("character", "")
            )
            char_voice = self._current_project_data.get("character_voices", {}).get(active_char)
            try:
                voice_name = (
                    self._selected_voice_name
                    or char_voice
                    or default_voice_for_language(self._automation_state.target_language)
                )
            except ValueError as exc:
                self._show_status(str(exc))
                return
            self._tts_worker = TTSPreviewWorker(
                text,
                voice_name=voice_name,
                output_file=output,
                parent=self,
            )
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
            if getattr(self, "_pending_preview_take", False):
                self._pending_preview_take = False
                self._preview_selected_take()

        def _on_perform_single_line_retake(self, options: dict[str, Any] | None = None) -> None:
            if (
                hasattr(self, "_retake_worker")
                and self._retake_worker is not None
                and self._retake_worker.isRunning()
            ):
                self._show_status("ADR retake operation is already in progress...")
                return

            opts = options or {}
            ripple = bool(opts.get("ripple", False))
            isometric = bool(opts.get("isometric", True))
            reverb = opts.get("reverb")

            text = self.inspector_panel.trans_in.text().strip()
            if not text:
                text = self.inspector_panel.orig_in.text().strip()
            if not text:
                self._show_status(
                    "Please enter dialogue text in the Inspector before running ADR Retake"
                )
                return

            # Determine utterance index
            utterance_index = 0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                clip_label = str(self._active_clip_info.get("label", ""))
                import re

                m = re.search(r"(\d+)", clip_label)
                if m:
                    utterance_index = max(0, int(m.group(1)) - 1)
                else:
                    clip_start = float(self._active_clip_info.get("start", 0.0))
                    clips = [
                        c
                        for c in self._current_project_data.get("clips", [])
                        if c[0] in {"S2", "S1", "A2"}
                    ]
                    if clips:
                        for idx, c in enumerate(clips):
                            if abs(float(c[1]) - clip_start) < 0.05:
                                utterance_index = idx
                                break

            active_char = self.inspector_panel.char_in.currentText().strip() or str(
                self._current_project_data.get("character", "")
            )
            char_voice = self._current_project_data.get("character_voices", {}).get(active_char)
            from aidub.adapters.voice.edge_tts_adapter import default_voice_for_language

            try:
                voice_name = (
                    self._selected_voice_name
                    or char_voice
                    or default_voice_for_language(self._automation_state.target_language)
                )
            except Exception:
                voice_name = None

            from aidub.ui.workers import UtteranceRetakeWorker

            self._retake_worker = UtteranceRetakeWorker(
                work_dir=self._session_store.workspace,
                utterance_index=utterance_index,
                new_target_text=text,
                target_language=self._automation_state.target_language,
                voice_name=voice_name,
                optimize_isometric=isometric,
                acoustic_preset=reverb,
                ripple_edit=ripple,
                parent=self,
            )
            self._retake_worker.retake_progress.connect(
                lambda pct, msg: self._show_status(f"ADR Retake #{utterance_index}: {msg} ({pct}%)")
            )
            self._retake_worker.retake_completed.connect(self._on_adr_retake_completed)
            self._retake_worker.retake_failed.connect(
                lambda err: self._show_status(f"ADR Retake failed: {err}")
            )
            self._retake_worker.finished.connect(lambda: setattr(self, "_retake_worker", None))
            self._show_status(
                f"Started ADR retake for line #{utterance_index} (Ripple={ripple}, Isometric={isometric})..."
            )
            self._retake_worker.start()

        def _on_adr_retake_completed(self, result: Any) -> None:
            if not result or not result.success:
                self._show_status("ADR Retake did not complete successfully")
                return

            self._show_status(
                f"✓ ADR Retake line #{result.utterance_index} applied in {result.elapsed_seconds:.1f}s "
                f"(Dur: {result.audio_duration_s:.2f}s, Ripple: {result.ripple_shift_s:+0.2f}s)"
            )
            take_name = f"ADR Take {result.utterance_index + 1}"
            self.inspector_panel.set_take_audio(take_name, result.dubbed_audio_path)
            self.inspector_panel.dub_dur_lbl.setText(
                f"Dub Duration:     {result.audio_duration_s:.2f}s"
            )
            if result.isometric_score is not None:
                self.inspector_panel.l_score_lbl.setText(f"Isometric: {result.isometric_score:.2f}")

            from aidub.pipeline.utterance_store import UtteranceStore

            try:
                store = UtteranceStore(
                    self._automation_state.target_language, self._session_store.workspace
                )
                loaded_segs, _ = store.load_utterances()
                if loaded_segs:
                    updated_clips = []
                    for i, seg in enumerate(loaded_segs):
                        s = float(seg.get("start", 0.0))
                        dur = float(seg.get("duration", float(seg.get("end", s + 1.0)) - s))
                        txt = str(seg.get("tgt", ""))
                        updated_clips.append(("A2", s, dur, f"Line {i + 1}: {txt[:16]}", None))
                    self._current_project_data["clips"] = updated_clips
                    self._current_project_data["duration"] = result.updated_timeline_duration
                    self.canvas_view.set_clips(
                        updated_clips, float(result.updated_timeline_duration)
                    )
            except Exception as exc:
                logger.warning("Could not refresh timeline clips after retake: %s", exc)

        def _run_translation_assistant(
            self,
            *,
            shorten: bool,
            instruction_override: str | None = None,
        ) -> None:
            if self._assistant_worker is not None and self._assistant_worker.isRunning():
                self._show_status("Translation agent is already processing a request")
                return
            source = self.inspector_panel.orig_in.text().strip()
            current = self.inspector_panel.trans_in.text().strip()
            if not source and current:
                source = current
            if not source:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S1", "S2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                    source = (
                        self.inspector_panel.orig_in.text().strip()
                        or self.inspector_panel.trans_in.text().strip()
                    )
                    current = self.inspector_panel.trans_in.text().strip()
            if not source:
                self._show_status("Select a dialogue segment before rewriting")
                return
            from aidub.ui.workers import AIAssistantWorker

            instruction = instruction_override or (
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
                self._commit_translation()
                self._show_status("Translation revision applied; voice and timing are now stale")

        def _apply_timing_fix(self) -> None:
            if self._timing_worker is not None and self._timing_worker.isRunning():
                self._show_status("Timing fit is already running")
                return
            clip = self._active_clip_info or {}
            if clip.get("tid") != "A2":
                start = float(clip.get("start", 0.0))
                matching_a2 = self._matching_subtitle("A2", start, float(clip.get("dur", 1.0)))
                if matching_a2 is not None:
                    clip = {
                        "tid": matching_a2[0],
                        "start": matching_a2[1],
                        "dur": matching_a2[2],
                        "label": matching_a2[3],
                        "score": matching_a2[4] if len(matching_a2) > 4 else None,
                    }
                    self._active_clip_info = clip
                else:
                    self._show_status("Select a dubbed voice clip on A2 before matching timing")
                    return
            source_audio = str(self.inspector_panel.take_combo.currentData() or "")
            if not source_audio or not Path(source_audio).is_file():
                for p in self._current_project_data.get("generated_paths", ()):
                    path_obj = Path(p)
                    if path_obj.is_file() and path_obj.suffix.lower() in {".wav", ".mp3"}:
                        source_audio = str(path_obj)
                        self.inspector_panel.set_take_audio(path_obj.stem, path_obj)
                        break
            if not source_audio or not Path(source_audio).is_file():
                self._show_status("Select or import a playable dubbed voice take first")
                return
            start = float(clip.get("start", 0.0))
            source_cue = self._matching_subtitle("S1", start)
            if source_cue is None:
                self._show_status(
                    "Import source subtitles to provide measured dialogue timing for this take"
                )
                return

            from aidub.ui.workers import TimingFitWorker

            output_dir = self._session_store.workspace / "takes"
            output_dir.mkdir(parents=True, exist_ok=True)
            base = output_dir / f"{Path(source_audio).stem}_{round(start * 1_000)}ms_fit.wav"
            output_path = base
            revision = 2
            while output_path.exists():
                output_path = base.with_name(f"{base.stem}_{revision:02d}{base.suffix}")
                revision += 1

            self._pending_timing_edit = {
                "start": start,
                "source_label": str(clip.get("label", "Dub take")),
                "target_duration": float(source_cue[2]),
            }
            self._timing_worker = TimingFitWorker(
                source_audio,
                float(source_cue[2]),
                output_path,
                self,
            )
            self._timing_worker.fit_completed.connect(self._on_timing_fit_ready)
            self._timing_worker.fit_failed.connect(
                lambda error: self._show_status(f"Timing fit failed: {error}")
            )
            self._timing_worker.finished.connect(lambda: setattr(self, "_timing_worker", None))
            self._show_status("Fitting the selected voice take to the source subtitle slot…")
            self._timing_worker.start()

        def _on_timing_fit_ready(self, output_path: str, fitted_duration: float) -> None:
            pending = self._pending_timing_edit or {}
            start = float(pending.get("start", -1.0))
            source_label = str(pending.get("source_label", "Dub take"))
            fitted_label = f"{source_label} (timed)"
            previous = list(self._current_project_data.get("clips", []))
            updated = list(previous)
            matched_index = next(
                (
                    index
                    for index, clip in enumerate(updated)
                    if clip[0] == "A2"
                    and abs(float(clip[1]) - start) < 0.05
                    and clip[3] == source_label
                ),
                None,
            )
            if matched_index is None:
                self._show_status("Fitted audio was saved, but its timeline take has changed")
                return

            old = updated[matched_index]
            updated[matched_index] = ("A2", old[1], fitted_duration, fitted_label, old[4])
            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = updated
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (
                output_path,
            )
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_clips(
                updated,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self.inspector_panel.set_take_audio(fitted_label, output_path)
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            self._active_clip_info = {
                "tid": "A2",
                "start": old[1],
                "dur": fitted_duration,
                "label": fitted_label,
                "score": old[4],
            }
            self.inspector_panel.update_clip_info(
                self.inspector_panel.orig_in.text(),
                self.inspector_panel.trans_in.text(),
                self.inspector_panel.char_in.currentText(),
                self.inspector_panel.lang_in.text(),
                float(pending.get("target_duration", fitted_duration)),
                fitted_duration,
                old[4],
            )
            self._show_status(f"Timed take saved: {output_path}")

        def open_dub_dialog(self) -> None:
            """Prompt the user for target language (Bengali default) and Fast/Quality profile, then start dubbing."""
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                self._show_status("A dubbing job is already running")
                return

            input_path = Path(str(self._current_project_data.get("file_path", "")))
            if not input_path.is_file():
                selected, _selected_filter = QFileDialog.getOpenFileName(
                    self,
                    "Select Source Movie for Automated Dubbing",
                    self._default_asset_directory(),
                    "Movie Files (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
                )
                if not selected:
                    return
                input_path = Path(selected)
                self.load_project_data(
                    {
                        "name": self._current_project_data.get("name", input_path.stem),
                        "file_path": str(input_path),
                        "target_language": self._automation_state.target_language or "bn",
                        "quality_profile": self._automation_state.quality_profile or "quality",
                    }
                )

            from aidub.ui.dub_dialog import DubDialog

            current_lang = self._automation_state.target_language or "bn"
            current_profile = self._automation_state.quality_profile or "quality"
            dialog = DubDialog(self, current_lang=current_lang, current_profile=current_profile)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            advanced = dialog.get_advanced_settings()
            target_lang = advanced.get("target_lang", "bn")
            quality_profile = advanced.get("quality_profile", "quality")
            self._current_project_data["isometric_alignment"] = advanced.get(
                "isometric_alignment", True
            )
            self._current_project_data["acoustic_preset"] = advanced.get("acoustic_preset", "none")
            self._current_project_data["broadcast_spec"] = advanced.get("broadcast_spec", "netflix")
            self._current_project_data["embed_c2pa_provenance"] = advanced.get(
                "embed_c2pa_provenance", True
            )
            self._current_project_data["lipsync"] = advanced.get("lipsync", True)
            self._current_project_data["lipsync_tier"] = advanced.get(
                "lipsync_tier", "studio_viseme"
            )
            self._current_project_data["voice_engine"] = advanced.get("voice_engine", "gemini_tts")
            self._run_agentic_dub(target_lang=target_lang, quality_profile=quality_profile)

        def _run_agentic_dub(
            self,
            *,
            target_lang: str | None = None,
            quality_profile: str | None = None,
        ) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                return
            input_path = Path(str(self._current_project_data.get("file_path", "")))
            if not input_path.is_file():
                selected, _selected_filter = QFileDialog.getOpenFileName(
                    self,
                    "Select Source Movie for Automated Dubbing",
                    self._default_asset_directory(),
                    "Movie Files (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
                )
                if not selected:
                    return
                input_path = Path(selected)
                self.load_project_data(
                    {
                        "name": self._current_project_data.get("name", input_path.stem),
                        "file_path": str(input_path),
                        "target_language": target_lang
                        or self._automation_state.target_language
                        or "bn",
                        "quality_profile": quality_profile
                        or self._automation_state.quality_profile
                        or "quality",
                    }
                )

            lang = target_lang or self._automation_state.target_language or "bn"
            profile = quality_profile or self._automation_state.quality_profile or "quality"

            from aidub.ui.workers import DubbingEngineWorker

            self._automation_state = create_automation_plan(
                str(self._current_project_data.get("name", input_path.stem)),
                source_path=str(input_path.resolve()),
                target_language=lang,
                quality_profile=profile,
            )
            self.inspector_panel.clear_quality_report()
            self.ai_overlay.set_state(self._automation_state)
            lipsync_enabled = bool(self._current_project_data.get("lipsync", True))
            lipsync_tier = str(self._current_project_data.get("lipsync_tier", "studio_viseme"))
            voice_engine = str(self._current_project_data.get("voice_engine", "gemini_tts"))
            self._dubbing_worker = DubbingEngineWorker(
                input_path,
                lang,
                profile,
                self,
                voice_name=self._selected_voice_name,
                voice_engine=voice_engine,
                character_voices=self._current_project_data.get("character_voices"),
                lipsync=lipsync_enabled,
                lipsync_tier=lipsync_tier,
            )
            self._dubbing_worker.progress_updated.connect(self._on_dubbing_progress)
            self._dubbing_worker.dubbing_completed.connect(self._on_dubbing_completed)
            self._dubbing_worker.dubbing_failed.connect(self._on_dubbing_failed)
            self._dubbing_worker.dubbing_cancelled.connect(self._on_dubbing_cancelled)
            self._dubbing_worker.finished.connect(lambda: setattr(self, "_dubbing_worker", None))
            self.ai_overlay.set_progress("Preparing autonomous production graph…", 1)
            self._show_status("Agentic dubbing job started · background execution enabled")
            win = self.window()
            if hasattr(win, "update_dub_progress"):
                win.update_dub_progress("ingest", 1, "Starting dubbing pipeline…")
            self._dubbing_worker.start()

        def _cancel_agentic_dub(self) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                self._dubbing_worker.cancel()
                self._show_status("Cancellation requested · waiting for a safe stage boundary")

        def _on_dubbing_progress(self, pipeline_stage: str, percent: int, message: str) -> None:
            stage_map = {
                "ingest": AutomationStage.INGEST,
                "extract_audio": AutomationStage.INGEST,
                "separate_stems": AutomationStage.AUDIO_SEPARATION,
                "diarize": AutomationStage.SPEAKER_ANALYSIS,
                "asr": AutomationStage.TRANSCRIPTION,
                "translate": AutomationStage.TRANSLATION,
                "tts": AutomationStage.SYNTHESIS,
                "assemble": AutomationStage.TIMING,
                "lipsync": AutomationStage.LIP_SYNC,
                "mix": AutomationStage.MIX,
                "mux": AutomationStage.MASTER_EXPORT,
                "complete": AutomationStage.MASTER_EXPORT,
            }
            skipped = pipeline_stage.endswith("_skipped")
            current_stage = stage_map.get(
                pipeline_stage.removesuffix("_skipped") if skipped else pipeline_stage
            )
            state = self._automation_state
            if current_stage is not None and skipped:
                state = state.update_stage(
                    current_stage,
                    status=StageStatus.SKIPPED,
                    progress=100,
                    detail=message,
                )
            elif current_stage is not None:
                executed_stages = [
                    AutomationStage.INGEST,
                    AutomationStage.AUDIO_SEPARATION,
                    AutomationStage.SPEAKER_ANALYSIS,
                    AutomationStage.TRANSCRIPTION,
                    AutomationStage.TRANSLATION,
                    AutomationStage.SYNTHESIS,
                    AutomationStage.TIMING,
                    AutomationStage.LIP_SYNC,
                    AutomationStage.MIX,
                    AutomationStage.MASTER_EXPORT,
                ]
                current_index = executed_stages.index(current_stage)
                for stage in executed_stages[:current_index]:
                    stage_state = state.stage(stage)
                    if stage_state.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                        state = state.update_stage(
                            stage,
                            status=StageStatus.SUCCEEDED,
                            progress=100,
                            detail="Completed by the pipeline",
                        )
                if current_stage is AutomationStage.SYNTHESIS:
                    voice_casting = state.stage(AutomationStage.VOICE_CASTING)
                    if voice_casting.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                        state = state.update_stage(
                            AutomationStage.VOICE_CASTING,
                            status=StageStatus.SKIPPED,
                            progress=100,
                            detail="This run uses one configured voice; per-character casting is not configured",
                        )
                if state.stage(current_stage).status is not StageStatus.SUCCEEDED:
                    state = state.update_stage(
                        current_stage,
                        status=StageStatus.RUNNING,
                        progress=percent,
                        detail=message,
                    )
            stage_name = pipeline_stage.replace("_skipped", "").replace("_", " ").upper()
            self._automation_state = state
            self._persist_automation_state()
            self.ai_overlay.set_progress(f"[{stage_name}] {message}", percent)
            self._show_status(f"Stage: {stage_name} ({percent}%) · {message}")
            win = self.window()
            if hasattr(win, "update_dub_progress"):
                win.update_dub_progress(stage_name, percent, message)

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

            work_dir = Path(result.get("work_dir", ""))
            asr_json = work_dir / "asr_segments.json"
            detected_chars: list[str] = []
            if asr_json.is_file():
                try:
                    from aidub.ai.voice.character_cloning_engine import CharacterDetectionEngine

                    segs = json.loads(asr_json.read_text(encoding="utf-8"))
                    engine = CharacterDetectionEngine()
                    chars = engine.detect_movie_characters(segs)
                    detected_chars = [c.canonical_name for c in chars]
                    clip_chars = self._current_project_data.setdefault("clip_characters", {})
                    for seg in segs:
                        start_s = float(seg.get("start", 0.0))
                        spk = str(seg.get("speaker", "0"))
                        spk_label = (
                            f"Speaker {spk}" if not spk.lower().startswith("speaker") else spk
                        )
                        clip_chars[f"S1:{round(start_s, 3)}"] = spk_label
                        clip_chars[f"S2:{round(start_s, 3)}"] = spk_label
                    if detected_chars:
                        self.inspector_panel.update_characters(detected_chars)
                        self.inspector_panel.meta_chars_lbl.setText(
                            f"{len(detected_chars)} speakers"
                        )
                except Exception as exc:
                    logger.debug("Failed loading asr_segments in on_dubbing_completed: %s", exc)

            state = self._automation_state
            for item in state.stages:
                if item.stage is AutomationStage.LIP_SYNC:
                    lipsynced = str(result.get("lipsynced_video", ""))
                    if lipsynced and Path(lipsynced).is_file():
                        state = state.update_stage(
                            item.stage,
                            status=StageStatus.SUCCEEDED,
                            progress=100,
                            detail=f"Lip-sync synthesized: {Path(lipsynced).name}",
                        )
                        self.inspector_panel.l_score_lbl.setText("Lip Sync:  Not measured")
                        self.inspector_panel.l_score_lbl.setStyleSheet("color:#8C9BAE;")
                    else:
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
                elif item.stage is AutomationStage.VOICE_CASTING:
                    status = StageStatus.SUCCEEDED if detected_chars else StageStatus.SKIPPED
                    detail = (
                        f"Applied character voice casting for {len(detected_chars)} character(s)"
                        if detected_chars
                        else "Per-character voice casting is not configured for this run"
                    )
                    state = state.update_stage(
                        item.stage,
                        status=status,
                        progress=100,
                        detail=detail,
                    )
                elif item.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
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
            master_file = str(result.get("output_file", ""))
            self._show_status(f"Master created: {master_file}")

            # Automatically load the newly created dubbed video in the Program Monitor
            dubbed_video = str(result.get("lipsynced_video") or result.get("output_file") or "")
            orig_video = str(self._current_project_data.get("file_path", ""))
            if dubbed_video and Path(dubbed_video).is_file():
                try:
                    self.monitor_panel.load_media(dubbed_video)
                    if orig_video and Path(orig_video).is_file():
                        self.monitor_panel.load_comparison_media(orig_video)
                    self.monitor_panel.prog_title_lbl.setText(
                        f"Program: {Path(dubbed_video).stem} [DUBBED MASTER]"
                    )
                    self.monitor_panel.source_lbl.setText(f"Dubbed: {Path(dubbed_video).name}")
                    self._show_status(
                        f"Dubbed video loaded in Program monitor: {Path(dubbed_video).name}"
                    )
                except Exception as exc:
                    logger.debug("Failed auto-loading dubbed master in monitor: %s", exc)
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(True, dubbed_video or master_file)

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
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(False, error)
            try:
                from aidub.ui.dub_dialog import DubbingErrorDialog

                dialog = DubbingErrorDialog(
                    self,
                    title="Dubbing Pipeline Error",
                    message="The automated dubbing pipeline encountered an issue. See details below:",
                    details=error,
                )
                dialog.exec()
            except Exception:
                try:
                    QMessageBox.critical(
                        self,
                        "Dubbing Pipeline Notice",
                        f"The automated dubbing pipeline encountered an issue:\n\n{error}\n\n"
                        "Remediation steps:\n"
                        "• Verify that the movie has audible speech.\n"
                        "• Check FFmpeg installation.\n"
                        "• If using external AI models, verify your API keys (e.g. GEMINI_API_KEY).\n"
                        "• Check destination disk permissions.",
                    )
                except Exception:
                    pass

        def _on_dubbing_cancelled(self) -> None:
            self.ai_overlay.set_failed("Automation cancelled safely · revision preserved")
            self._show_status("Dubbing job cancelled; completed stage artifacts remain resumable")
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(False, "Cancelled")

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
            if self._current_project_data.get("file_path") and (
                self._dubbing_worker is None or not self._dubbing_worker.isRunning()
            ):
                self.autosave_lbl.setText("●  Auto-saved · just now")

        def _on_ai_fix_all(self) -> None:
            if self._active_clip_info is None:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S2", "S1", "A2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                else:
                    self._show_status("Select a dialogue or dubbed voice clip before Auto Fix")
                    return
            self._apply_timing_fix()
            if self.inspector_panel.orig_in.text().strip():
                self._run_translation_assistant(shorten=False)

        def _preview_selected_take(self) -> None:
            audio_path = str(self.inspector_panel.take_combo.currentData() or "")
            if not audio_path or not Path(audio_path).is_file():
                candidates: list[Path] = []
                for p in self._current_project_data.get("generated_paths", ()):
                    path_obj = Path(p)
                    if path_obj.is_file() and path_obj.suffix.lower() in {
                        ".mp3",
                        ".wav",
                        ".aac",
                        ".flac",
                        ".m4a",
                    }:
                        candidates.append(path_obj)
                preview_dir = self._session_store.workspace / "previews"
                if preview_dir.is_dir():
                    for p in preview_dir.glob("take_*.mp3"):
                        if p.is_file() and p not in candidates:
                            candidates.append(p)
                takes_dir = self._session_store.workspace / "takes"
                if takes_dir.is_dir():
                    for p in takes_dir.glob("*.wav"):
                        if p.is_file() and p not in candidates:
                            candidates.append(p)
                if candidates:
                    latest = max(candidates, key=lambda f: f.stat().st_mtime)
                    self.inspector_panel.set_take_audio(latest.stem, latest)
                    audio_path = str(latest)
                else:
                    text = (
                        self.inspector_panel.trans_in.text().strip()
                        or self.inspector_panel.orig_in.text().strip()
                    )
                    if text:
                        self._show_status("No saved take found — synthesizing voice preview now…")
                        self._pending_preview_take = True
                        self._on_ai_regenerate_voice()
                        return
                    self._show_status("Select or import a playable voice take before previewing")
                    return
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

            if self._take_audio_player is None:
                audio_devices = QMediaDevices.audioOutputs()
                if audio_devices:
                    self._take_audio_output = QAudioOutput(self)
                    self._take_audio_output.setVolume(1.0)
                    self._take_audio_player = QMediaPlayer(self)
                    self._take_audio_player.setAudioOutput(self._take_audio_output)
                    self._take_audio_player.errorOccurred.connect(
                        lambda _error, message: self._show_status(
                            f"Take playback failed: {message}"
                        )
                    )
                else:
                    self._take_audio_output = None
                    self._show_status("No audio output device detected; cannot preview voice take")
                    return
            if self._take_audio_output is not None:
                self._take_audio_output.setVolume(1.0)
                self._take_audio_output.setMuted(False)
            if self._take_audio_player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
                self._take_audio_player.pause()
                self._show_status("Voice take preview paused")
                return
            self._take_audio_player.setSource(QUrl.fromLocalFile(str(Path(audio_path).resolve())))
            self._take_audio_player.play()
            self._show_status(f"Playing voice take: {Path(audio_path).name}")

        def _on_target_language_changed(self) -> None:
            language = self.inspector_panel.lang_in.text().strip()
            if not language or language == self._automation_state.target_language:
                return
            self._selected_voice_name = None
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

        def undo(self) -> None:
            if not self._edit_history:
                self._show_status("Nothing to undo")
                return
            current = list(self._current_project_data.get("clips", []))
            previous = self._edit_history.pop()
            self._edit_future.append(current)
            self._current_project_data["clips"] = previous
            self.canvas_view.set_clips(
                previous,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self._show_status("Timeline edit undone")

        def redo(self) -> None:
            if not self._edit_future:
                self._show_status("Nothing to redo")
                return
            current = list(self._current_project_data.get("clips", []))
            following = self._edit_future.pop()
            self._edit_history.append(current)
            self._current_project_data["clips"] = following
            self.canvas_view.set_clips(
                following,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self._show_status("Timeline edit restored")

        def mark_in(self) -> None:
            self.monitor_panel._on_mark_in()
            self._show_status(f"Mark In · {_format_tc(self.monitor_panel._mark_in_sec)}")

        def mark_out(self) -> None:
            self.monitor_panel._on_mark_out()
            self._show_status(f"Mark Out · {_format_tc(self.monitor_panel._mark_out_sec)}")

        def play_pause(self) -> None:
            self.monitor_panel._toggle_play()

        def step_backward(self) -> None:
            self.monitor_panel._on_step_back()

        def step_forward(self) -> None:
            self.monitor_panel._on_step_forward()

        def export_snapshot(self) -> None:
            self.monitor_panel._on_export_snapshot()

        def export_dubbed_video(self) -> None:
            """Export or render the master dubbed video to a chosen destination file."""
            default_name = (
                f"{self._current_project_data.get('name', 'dubbed_movie')}_"
                f"{self._automation_state.target_language}.mp4"
            )
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Dubbed Master Video",
                str(Path.cwd() / default_name),
                "MP4 Video (*.mp4);;Matroska Video (*.mkv);;QuickTime (*.mov);;All Files (*)",
            )
            if not target_path:
                return

            dest = Path(target_path).resolve()
            src_video = self._current_project_data.get("file_path")
            if src_video and Path(str(src_video)).resolve() == dest:
                QMessageBox.critical(
                    self,
                    "Destination Conflict",
                    "The destination path cannot overwrite the source movie file.\n"
                    "Please choose a different output filename.",
                )
                return

            work_dir = Path(self._current_project_data.get("work_dir", "work"))
            rendered_master = self._current_project_data.get("rendered_master")
            dubbed_video_path = self._current_project_data.get("dubbed_video_path")

            candidates: list[Path] = []
            if rendered_master:
                candidates.append(Path(rendered_master))
            candidates.append(work_dir / "dubbed_video.mp4")
            if dubbed_video_path:
                candidates.append(Path(dubbed_video_path))
            candidates.extend(
                [
                    Path(f"out_{self._automation_state.target_language}.mp4"),
                    Path("out_bn.mp4"),
                ]
            )
            source_dub = next((c for c in candidates if c.is_file()), None)
            if source_dub:
                if source_dub.resolve() != dest:
                    import shutil

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_dub, dest)
                self._show_status(f"Exported dubbed video: {dest.name}")
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported dubbed master video:\n{target_path}",
                )
            else:
                self._show_status("No rendered dub found; running Auto Dub Master first…")
                self.run_auto_dub()

        def export_subtitles_dialog(self, *, target: bool = True, bilingual: bool = False) -> None:
            """Export current timeline cues as standard single-language or dual-language bilingual SRT."""
            from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt

            clips = self._current_project_data.get("clips", [])
            s1_clips = [c for c in clips if c[0] == "S1"]
            s2_clips = [c for c in clips if c[0] == "S2"]

            if not s1_clips and not s2_clips:
                QMessageBox.warning(
                    self,
                    "Export Subtitles",
                    "No subtitle cues are present on the timeline to export.",
                )
                return

            ext = "bilingual" if bilingual else ("target" if target else "source")
            default_name = f"{self._current_project_data.get('name', 'subtitles')}_{ext}.srt"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Subtitles (SRT)",
                str(Path.cwd() / default_name),
                "SRT Subtitles (*.srt);;All Files (*)",
            )
            if not save_path:
                return

            if bilingual:
                segments: list[dict[str, Any]] = []
                for s1 in s1_clips:
                    match_s2 = self._matching_subtitle("S2", s1[1], s1[2])
                    segments.append(
                        {
                            "start": s1[1],
                            "end": s1[1] + s1[2],
                            "text": s1[3],
                            "tgt": match_s2[3] if match_s2 else "",
                        }
                    )
                write_bilingual_srt(segments, save_path, LineMode.BILINGUAL_TARGET_BOTTOM)
            else:
                chosen = s2_clips if target else s1_clips
                segments = [
                    {
                        "start": c[1],
                        "end": c[1] + c[2],
                        "text": c[3],
                        "tgt": c[3],
                    }
                    for c in chosen
                ]
                write_srt(segments, save_path, translated=False)

            self._show_status(f"Exported {len(segments)} subtitle cues to: {Path(save_path).name}")
            QMessageBox.information(
                self, "Export Complete", f"Subtitles exported successfully:\n{save_path}"
            )

        def run_auto_dub(self, *, prompt_dialog: bool = False) -> None:
            if prompt_dialog:
                self.open_dub_dialog()
            else:
                self._run_agentic_dub()

        def cancel_active_job(self) -> None:
            self._cancel_agentic_dub()
            for worker_name in (
                "_extraction_worker",
                "_transcription_worker",
                "_translation_worker",
                "_batch_tts_worker",
                "_synthesis_worker",
                "_render_worker",
                "_active_lipsync_worker",
                "_assistant_worker",
                "_timing_worker",
                "_tts_worker",
            ):
                worker = getattr(self, worker_name, None)
                if worker is not None and worker.isRunning():
                    if hasattr(worker, "cancel"):
                        worker.cancel()
            self._show_status("Cancellation requested for active job(s)")

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
            workers = (
                self._dubbing_worker,
                getattr(self, "_extraction_worker", None),
                getattr(self, "_transcription_worker", None),
                getattr(self, "_translation_worker", None),
                getattr(self, "_batch_tts_worker", None),
                getattr(self, "_synthesis_worker", None),
                getattr(self, "_render_worker", None),
                getattr(self, "_active_lipsync_worker", None),
                getattr(self, "_assistant_worker", None),
                getattr(self, "_timing_worker", None),
                getattr(self, "_tts_worker", None),
            )
            return any(w is not None and w.isRunning() for w in workers)

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            for worker_name in (
                "_assistant_worker",
                "_timing_worker",
                "_tts_worker",
                "_dubbing_worker",
                "_extraction_worker",
                "_transcription_worker",
                "_translation_worker",
                "_batch_tts_worker",
                "_synthesis_worker",
                "_render_worker",
                "_active_lipsync_worker",
            ):
                worker = getattr(self, worker_name, None)
                if worker is not None and worker.isRunning():
                    if hasattr(worker, "cancel"):
                        worker.cancel()
                    worker.quit()
                    worker.wait(1_500)
            if self._take_audio_player is not None:
                self._take_audio_player.stop()
                self._take_audio_player = None
                self._take_audio_output = None
            if self.monitor_panel._player is not None:
                self.monitor_panel._player.stop()
            super().closeEvent(event)


__all__ = ["TimelineScreen"]
