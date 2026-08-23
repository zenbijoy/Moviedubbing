"""
AI Movie Dubbing Studio — Complete QSS Design System.

Color tokens exactly as specified in Master Spec Section 2:
  BG0  #080B10   BG1  #0D1118   BG2  #121822
  Panel #161D28  Elevated #1C2431  Border #283241

Accent palette:
  Primary Blue    #4F8CFF   AI Violet    #8B5CF6
  Voice Cyan      #22D3EE   Translation  #A855F7
  Audio Green     #10B981   Lip Sync     #EC4899
  Warning Amber   #F59E0B   Danger Red   #EF4444
  Success Green   #22C55E

Typography hierarchy per spec:
  App title: 28px/Semibold   Screen title: 22px
  Panel title: 15px/Semibold  Normal UI: 13-14px
  Metadata: 12px  Timeline: 11px
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Color constants (single source of truth — keeps QSS readable)
# ---------------------------------------------------------------------------
BG0 = "#080B10"
BG1 = "#0D1118"
BG2 = "#121822"
PANEL = "#161D28"
ELEVATED = "#1C2431"
BORDER = "#283241"
BORDER_LIGHT = "#34415A"

PRIMARY = "#4F8CFF"
PRIMARY_HOVER = "#6BA3FF"
PRIMARY_PRESSED = "#3A74EF"

AI_VIOLET = "#8B5CF6"
AI_VIOLET_HOVER = "#9E74F7"
VOICE_CYAN = "#22D3EE"
TRANS_PURPLE = "#A855F7"
AUDIO_GREEN = "#10B981"
LIPSYNC_PINK = "#EC4899"
WARNING = "#F59E0B"
DANGER = "#EF4444"
SUCCESS = "#22C55E"

TEXT_PRIMARY = "#F7F9FC"
TEXT_SECONDARY = "#A9B2C3"
TEXT_MUTED = "#687386"

SELECTION_BG = "#1E3A5F"
SELECTION_BORDER = "#4F8CFF"

APPLICATION_STYLE = f"""
/* =====================================================================
   BASE RESET
   ===================================================================== */
QWidget {{
    background-color: {BG1};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_PRIMARY};
}}

QLabel {{
    background-color: transparent;
}}

/* =====================================================================
   MAIN WINDOW
   ===================================================================== */
QMainWindow {{
    background-color: {BG0};
}}

QMainWindow::separator {{
    background-color: {BORDER};
    width: 1px;
    height: 1px;
}}

/* =====================================================================
   MENU BAR
   ===================================================================== */
QMenuBar {{
    background-color: {BG1};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 6px;
    font-size: 13px;
}}

QMenuBar::item {{
    padding: 5px 12px;
    border-radius: 5px;
}}

QMenuBar::item:selected {{
    background-color: {ELEVATED};
}}

QMenuBar::item:pressed {{
    background-color: {SELECTION_BG};
}}

QMenu {{
    background-color: {ELEVATED};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 8px 28px 8px 16px;
    border-radius: 5px;
    font-size: 13px;
}}

QMenu::item:selected {{
    background-color: {SELECTION_BG};
    color: {TEXT_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* =====================================================================
   TOP BAR (custom widget)
   ===================================================================== */
QWidget#TopBar {{
    background-color: {BG1};
    border-bottom: 1px solid {BORDER};
    min-height: 46px;
    max-height: 46px;
}}

QLabel#AppTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.3px;
}}

QLabel#ProjectName {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

QLabel#TopBarMeta {{
    font-size: 12px;
    color: {TEXT_MUTED};
    padding: 0 6px;
}}

QPushButton#TopBarBtn {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 5px;
}}

QPushButton#TopBarBtn:hover {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
}}

QPushButton#GpuBtn {{
    background: {ELEVATED};
    border: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 5px;
}}

QPushButton#GpuBtn:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}

QLabel#StatusBadge[tone="safe"] {{
    background: rgba(34,197,94,0.15);
    color: {SUCCESS};
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#StatusBadge[tone="warn"] {{
    background: rgba(245,158,11,0.15);
    color: {WARNING};
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#StatusBadge[tone="danger"] {{
    background: rgba(239,68,68,0.15);
    color: {DANGER};
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#StatusBadge[tone="info"] {{
    background: rgba(79,140,255,0.15);
    color: {PRIMARY};
    border: 1px solid rgba(79,140,255,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* =====================================================================
   SIDEBAR / NAVIGATION
   ===================================================================== */
QWidget#Sidebar {{
    background-color: {PANEL};
    border-right: 1px solid {BORDER};
}}

QLabel#SidebarBrand {{
    font-size: 13px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.5px;
    padding: 0 4px;
}}

QLabel#NavSectionHeading {{
    font-size: 10px;
    font-weight: 700;
    color: {TEXT_MUTED};
    letter-spacing: 1.2px;
    padding: 0 4px;
}}

QListWidget#NavList {{
    background: transparent;
    border: none;
    outline: none;
    padding: 2px 0;
}}

QListWidget#NavList::item {{
    border-radius: 7px;
    margin: 1px 6px;
    padding: 9px 10px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets', 'Segoe UI Variable', sans-serif;
}}

QListWidget#NavList::item:selected {{
    background-color: {SELECTION_BG};
    color: {TEXT_PRIMARY};
    font-weight: 600;
    border: 1px solid rgba(79,140,255,0.2);
}}

QListWidget#NavList::item:hover:!selected {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
}}

QPushButton#SidebarCollapseBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 14px;
    padding: 4px;
    border-radius: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}}

QPushButton#SidebarCollapseBtn:hover {{
    background: {ELEVATED};
    color: {TEXT_PRIMARY};
}}

/* =====================================================================
   STATUS BAR
   ===================================================================== */
QStatusBar {{
    background-color: {BG1};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0 8px;
    min-height: 26px;
}}

QStatusBar::item {{
    border: none;
}}

QLabel#StatusBarLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0 8px;
}}

QLabel#AutosaveLabel {{
    color: {SUCCESS};
    font-size: 11px;
    padding: 0 8px;
}}

/* =====================================================================
   DOCK WIDGETS
   ===================================================================== */
QDockWidget {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    titlebar-close-icon: none;
}}

QDockWidget::title {{
    background-color: {PANEL};
    padding: 8px 12px;
    border-bottom: 1px solid {BORDER};
}}

QDockWidget::close-button, QDockWidget::float-button {{
    border: none;
    background: transparent;
    padding: 2px;
}}

/* =====================================================================
   BUTTONS
   ===================================================================== */
QPushButton {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: #253447;
    border-color: {PRIMARY};
}}

QPushButton:pressed {{
    background-color: {SELECTION_BG};
}}

QPushButton:disabled {{
    background-color: {PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QPushButton[primary="true"] {{
    background-color: {PRIMARY};
    color: #FFFFFF;
    border-color: {PRIMARY_HOVER};
}}

QPushButton[primary="true"]:hover {{
    background-color: {PRIMARY_HOVER};
}}

QPushButton[primary="true"]:pressed {{
    background-color: {PRIMARY_PRESSED};
}}

QPushButton[accent="ai"] {{
    background-color: rgba(139,92,246,0.2);
    color: {AI_VIOLET};
    border-color: rgba(139,92,246,0.4);
}}

QPushButton[accent="ai"]:hover {{
    background-color: rgba(139,92,246,0.35);
    border-color: {AI_VIOLET};
}}

QPushButton[accent="danger"] {{
    background-color: rgba(239,68,68,0.15);
    color: {DANGER};
    border-color: rgba(239,68,68,0.3);
}}

QPushButton[accent="danger"]:hover {{
    background-color: rgba(239,68,68,0.3);
}}

QPushButton[accent="success"] {{
    background-color: rgba(16,185,129,0.15);
    color: {AUDIO_GREEN};
    border-color: rgba(16,185,129,0.3);
}}

/* =====================================================================
   LINE EDITS / TEXT EDITS / SPINBOXES
   ===================================================================== */
QLineEdit {{
    background-color: {BG2};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 13px;
    min-height: 32px;
    selection-background-color: {SELECTION_BG};
}}

QLineEdit:focus {{
    border-color: {PRIMARY};
    background-color: {PANEL};
}}

QLineEdit:disabled {{
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {BG2};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 8px;
    font-size: 13px;
    selection-background-color: {SELECTION_BG};
}}

QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {PRIMARY};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {BG2};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 32px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {PRIMARY};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {ELEVATED};
    border: none;
    width: 18px;
}}

/* =====================================================================
   COMBO BOXES
   ===================================================================== */
QComboBox {{
    background-color: {BG2};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 32px;
    min-width: 100px;
}}

QComboBox:focus {{
    border-color: {PRIMARY};
}}

QComboBox:hover {{
    border-color: {BORDER_LIGHT};
    background-color: {PANEL};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {ELEVATED};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    selection-background-color: {SELECTION_BG};
    color: {TEXT_PRIMARY};
    padding: 4px;
}}

/* =====================================================================
   LIST/TREE VIEWS
   ===================================================================== */
QListWidget, QTreeWidget, QListView, QTreeView {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    alternate-background-color: {BG2};
    outline: none;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QListWidget::item, QTreeWidget::item,
QListView::item, QTreeView::item {{
    padding: 7px 10px;
    border-radius: 5px;
}}

QListWidget::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QTreeView::item:selected {{
    background-color: {SELECTION_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid rgba(79,140,255,0.25);
}}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected,
QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: {ELEVATED};
}}

QHeaderView::section {{
    background-color: {ELEVATED};
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 600;
}}

/* =====================================================================
   TABLE VIEWS
   ===================================================================== */
QTableWidget, QTableView {{
    background-color: {PANEL};
    alternate-background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    outline: none;
}}

QTableWidget::item, QTableView::item {{
    padding: 7px 10px;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {SELECTION_BG};
}}

/* =====================================================================
   SCROLL BARS
   ===================================================================== */
QScrollBar:vertical {{
    background: {BG1};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {BG1};
    height: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* =====================================================================
   SLIDERS
   ===================================================================== */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {PRIMARY};
    border: 2px solid {BG0};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}

QSlider::handle:horizontal:hover {{
    background: {PRIMARY_HOVER};
}}

QSlider::sub-page:horizontal {{
    background: {PRIMARY};
    border-radius: 2px;
}}

QSlider::groove:vertical {{
    width: 4px;
    background: {BORDER};
    border-radius: 2px;
}}

QSlider::handle:vertical {{
    background: {PRIMARY};
    border: 2px solid {BG0};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: 0 -5px;
}}

QSlider::sub-page:vertical {{
    background: {PRIMARY};
    border-radius: 2px;
}}

/* =====================================================================
   PROGRESS BAR
   ===================================================================== */
QProgressBar {{
    background: {BG2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    min-height: 8px;
    max-height: 12px;
    text-align: center;
    font-size: 11px;
    color: {TEXT_SECONDARY};
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PRIMARY}, stop:1 {AI_VIOLET});
    border-radius: 5px;
}}

QProgressBar[accent="success"]::chunk {{
    background: {AUDIO_GREEN};
}}

QProgressBar[accent="warning"]::chunk {{
    background: {WARNING};
}}

QProgressBar[accent="danger"]::chunk {{
    background: {DANGER};
}}

/* =====================================================================
   PANELS / FRAMES
   ===================================================================== */
QFrame#Panel {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#ElevatedPanel {{
    background-color: {ELEVATED};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 10px;
}}

QFrame#Card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#Card:hover {{
    border-color: {BORDER_LIGHT};
}}

QFrame#DividerH {{
    background-color: {BORDER};
    max-height: 1px;
    min-height: 1px;
}}

QFrame#DividerV {{
    background-color: {BORDER};
    max-width: 1px;
    min-width: 1px;
}}

/* =====================================================================
   LABELS — TYPOGRAPHY HIERARCHY
   ===================================================================== */
QLabel#ScreenTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    padding: 0;
}}

QLabel#PanelTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.2px;
}}

QLabel#SectionLabel {{
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_MUTED};
    letter-spacing: 0.8px;
}}

QLabel#MetaLabel {{
    font-size: 12px;
    color: {TEXT_MUTED};
}}

QLabel#ValueLabel {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

QLabel#MutedLabel {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}

/* =====================================================================
   TABS
   ===================================================================== */
QTabWidget::pane {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    border-top-left-radius: 0;
}}

QTabBar::tab {{
    background: {BG2};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 20px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-size: 13px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    background: {PANEL};
    color: {TEXT_PRIMARY};
    border-color: {BORDER_LIGHT};
}}

QTabBar::tab:hover:!selected {{
    background: {ELEVATED};
    color: {TEXT_SECONDARY};
}}

/* =====================================================================
   GROUP BOX
   ===================================================================== */
QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 8px 8px 8px;
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {TEXT_SECONDARY};
    background: transparent;
}}

/* =====================================================================
   TOOLTIPS
   ===================================================================== */
QToolTip {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 12px;
}}

/* =====================================================================
   SPLITTER
   ===================================================================== */
QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:hover {{
    background-color: {PRIMARY};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* =====================================================================
   CHECKBOXES / RADIO BUTTONS
   ===================================================================== */
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER_LIGHT};
    border-radius: 4px;
    background: {BG2};
}}

QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

QCheckBox::indicator:hover {{
    border-color: {PRIMARY};
}}

QRadioButton {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER_LIGHT};
    border-radius: 9px;
    background: {BG2};
}}

QRadioButton::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

/* =====================================================================
   DIALOGS
   ===================================================================== */
QDialog {{
    background-color: {PANEL};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 12px;
}}

QDialog QLabel#DialogTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

/* =====================================================================
   COMMAND PALETTE (override)
   ===================================================================== */
QDialog#CommandPalette {{
    background: {BG0};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 12px;
}}

QListWidget#CommandResults {{
    border: 0;
    background: {BG0};
    outline: 0;
    border-radius: 8px;
}}

QListWidget#CommandResults::item {{
    padding: 10px 14px;
    border-bottom: 1px solid {BORDER};
    border-radius: 0;
}}

QListWidget#CommandResults::item:selected {{
    background: {SELECTION_BG};
    border-bottom-color: {SELECTION_BORDER};
    border-radius: 5px;
}}

/* =====================================================================
   POLICY BANNER (legacy compat)
   ===================================================================== */
QFrame#PolicyBanner {{
    background: {BG1};
    border-bottom: 1px solid {BORDER};
}}

/* Legacy status tone labels */
QLabel[statusTone="safe"] {{
    background: rgba(34,197,94,0.12);
    color: {SUCCESS};
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel[statusTone="warning"] {{
    background: rgba(245,158,11,0.12);
    color: {WARNING};
    border: 1px solid rgba(245,158,11,0.25);
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel[statusTone="danger"] {{
    background: rgba(239,68,68,0.12);
    color: {DANGER};
    border: 1px solid rgba(239,68,68,0.25);
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}}

QLabel[statusTone="info"] {{
    background: rgba(79,140,255,0.12);
    color: {PRIMARY};
    border: 1px solid rgba(79,140,255,0.25);
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}}

/* =====================================================================
   SCREEN-SPECIFIC (panels that show up across screens)
   ===================================================================== */
QFrame#EmptyState {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#StatusCard {{
    background: {ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

/* Waveform area */
QWidget#WaveformArea {{
    background: {BG0};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

/* Score badge colors */
QLabel#ScoreBadge[level="high"] {{
    background: rgba(34,197,94,0.15);
    color: {SUCCESS};
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#ScoreBadge[level="mid"] {{
    background: rgba(245,158,11,0.15);
    color: {WARNING};
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#ScoreBadge[level="low"] {{
    background: rgba(239,68,68,0.15);
    color: {DANGER};
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 700;
}}

/* Timeline clip types */
QFrame#ClipVideo {{
    background: rgba(59,130,246,0.2);
    border: 1px solid rgba(59,130,246,0.4);
    border-radius: 4px;
}}

QFrame#ClipAudio {{
    background: rgba(16,185,129,0.2);
    border: 1px solid rgba(16,185,129,0.4);
    border-radius: 4px;
}}

QFrame#ClipSubtitle {{
    background: rgba(249,115,22,0.2);
    border: 1px solid rgba(249,115,22,0.4);
    border-radius: 4px;
}}
"""
