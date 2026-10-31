"""Enterprise unified stylesheet generator for AI Dubbing Studio."""

from __future__ import annotations

from aidub.ui.design.tokens import (
    FONT_BODY,
    FONT_PANEL_TITLE,
    FONT_TITLE,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    ColorTokens,
    ThemeMode,
    get_theme_tokens,
)


def build_stylesheet(tokens: ColorTokens | None = None) -> str:
    """Generate a single, broadcast-grade stylesheet for all Qt Widgets."""
    t = tokens or get_theme_tokens(ThemeMode.STUDIO_DARK)

    return f"""
    /* Root Window and Core Canvas */
    QMainWindow, QDialog {{
        background-color: {t.bg_base};
        color: {t.text_primary};
        font-size: {FONT_BODY}px;
    }}

    QWidget {{
        color: {t.text_primary};
        selection-background-color: {t.accent};
        selection-color: {t.text_inverse};
        outline: none;
    }}

    QWidget:disabled {{
        color: {t.text_muted};
    }}

    /* Tier 1 Surfaces & Structural Panels */
    QFrame[tier="base"] {{
        background-color: {t.bg_base};
        border: none;
    }}

    QFrame[tier="surface"], QFrame#SideNavRail, QFrame#InspectorSurface {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_LG}px;
    }}

    QFrame[tier="elevated"], QFrame#StudioCard {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_MD}px;
    }}

    QFrame[tier="overlay"] {{
        background-color: {t.bg_overlay};
        border: 1px solid {t.border_strong};
        border-radius: {RADIUS_LG}px;
    }}

    /* Labels & Typography */
    QLabel {{
        background: transparent;
        color: {t.text_secondary};
    }}

    QLabel[role="display"] {{
        color: {t.text_primary};
        font-size: 22px;
        font-weight: 800;
        letter-spacing: -0.3px;
    }}

    QLabel[role="title"] {{
        color: {t.text_primary};
        font-size: {FONT_TITLE}px;
        font-weight: 700;
        letter-spacing: -0.2px;
    }}

    QLabel[role="panel_title"] {{
        color: {t.text_primary};
        font-size: {FONT_PANEL_TITLE}px;
        font-weight: 700;
        letter-spacing: 0.2px;
    }}

    QLabel[role="meta"] {{
        color: {t.text_muted};
        font-size: 12px;
    }}

    QLabel[role="status"] {{
        font-size: 11px;
        font-weight: 600;
    }}

    /* Push Buttons */
    QPushButton {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_MD}px;
        padding: 6px 14px;
        font-size: {FONT_BODY}px;
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton:hover {{
        background-color: {t.bg_overlay};
        border-color: {t.border_strong};
        color: {t.text_primary};
    }}

    QPushButton:pressed {{
        background-color: {t.border_strong};
    }}

    QPushButton:focus {{
        border: 1px solid {t.border_accent};
    }}

    QPushButton:disabled {{
        background-color: {t.bg_surface};
        border-color: {t.border_subtle};
        color: {t.text_muted};
    }}

    /* Primary Accent Button */
    QPushButton[variant="primary"], QPushButton#PrimaryActionButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.accent}, stop:1 {t.accent_hover});
        color: {t.text_inverse};
        border: 1px solid {t.border_accent};
        font-weight: 700;
        letter-spacing: 0.2px;
    }}

    QPushButton[variant="primary"]:hover, QPushButton#PrimaryActionButton:hover {{
        background: {t.accent_hover};
        border-color: {t.accent_hover};
        color: #FFFFFF;
    }}

    QPushButton[variant="primary"]:pressed, QPushButton#PrimaryActionButton:pressed {{
        background-color: {t.accent_pressed};
        border-color: {t.accent_pressed};
    }}

    /* AI Purple Button (Spec Sec 26: Purple = AI Generated) */
    QPushButton[variant="ai"], QPushButton#AiActionButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.ai_purple}, stop:1 #9333EA);
        color: #FFFFFF;
        border: 1px solid {t.ai_purple};
        font-weight: 700;
    }}

    QPushButton[variant="ai"]:hover, QPushButton#AiActionButton:hover {{
        background: #9333EA;
        border-color: #A855F7;
        color: #FFFFFF;
    }}

    /* Success Button */
    QPushButton[variant="success"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 {t.success});
        color: #FFFFFF;
        border: 1px solid {t.success};
        font-weight: 700;
    }}

    QPushButton[variant="success"]:hover {{
        background: #059669;
        border-color: #34D399;
    }}

    /* Ghost Button */
    QPushButton[variant="ghost"] {{
        background-color: transparent;
        border: 1px solid transparent;
        color: {t.text_secondary};
    }}

    QPushButton[variant="ghost"]:hover {{
        background-color: {t.accent_subtle};
        border-color: transparent;
        color: {t.text_primary};
    }}

    /* Destructive Button */
    QPushButton[variant="destructive"] {{
        background-color: {t.danger_subtle};
        border: 1px solid {t.danger};
        color: {t.danger};
        font-weight: 600;
    }}

    QPushButton[variant="destructive"]:hover {{
        background-color: {t.danger};
        border-color: {t.danger};
        color: #FFFFFF;
    }}

    /* Tool Buttons */
    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_SM}px;
        padding: 4px;
        color: {t.text_secondary};
    }}

    QToolButton:hover {{
        background-color: {t.bg_elevated};
        border-color: {t.border_subtle};
        color: {t.text_primary};
    }}

    QToolButton:pressed {{
        background-color: {t.bg_overlay};
    }}

    QToolButton:checked {{
        background-color: {t.accent_subtle};
        border-color: {t.border_accent};
        color: {t.accent};
    }}

    /* Text Inputs */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {t.bg_base};
        color: {t.text_primary};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_MD}px;
        padding: 6px 10px;
        font-size: {FONT_BODY}px;
    }}

    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
        border-color: {t.border_strong};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {t.border_accent};
        background-color: {t.bg_surface};
    }}

    /* Dropdowns / ComboBoxes */
    QComboBox {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_MD}px;
        padding: 6px 12px;
        font-size: {FONT_BODY}px;
        min-height: 22px;
    }}

    QComboBox:hover {{
        border-color: {t.border_strong};
    }}

    QComboBox:focus {{
        border-color: {t.border_accent};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: none;
    }}

    QComboBox QAbstractItemView {{
        background-color: {t.bg_overlay};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        border-radius: {RADIUS_MD}px;
        padding: 4px;
        selection-background-color: {t.accent};
        selection-color: {t.text_inverse};
    }}

    /* Table, List, and Tree Views */
    QTableWidget, QTableView, QListWidget, QListView, QTreeWidget, QTreeView {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border_subtle};
        border-radius: {RADIUS_MD}px;
        gridline-color: {t.border_subtle};
        selection-background-color: {t.accent_subtle};
        selection-color: {t.text_primary};
        alternate-background-color: {t.bg_base};
    }}

    QHeaderView::section {{
        background-color: {t.bg_elevated};
        color: {t.text_muted};
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border: none;
        border-bottom: 1px solid {t.border_subtle};
        border-right: 1px solid {t.border_subtle};
        padding: 6px 10px;
    }}

    /* Scrollbars (Modern 8px auto-hiding style) */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {t.border_strong};
        min-height: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {t.accent};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        background: none;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background: {t.border_strong};
        min-width: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {t.accent};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        background: none;
    }}

    /* Sliders */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {t.border_strong};
        border-radius: 2px;
    }}

    QSlider::sub-page:horizontal {{
        background: {t.accent};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {t.text_primary};
        border: 2px solid {t.accent};
        width: 14px;
        margin-top: -5px;
        margin-bottom: -5px;
        border-radius: 7px;
    }}

    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
        border-color: {t.accent_hover};
    }}

    /* Progress Bars */
    QProgressBar {{
        background-color: {t.bg_base};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        height: 6px;
        text-align: center;
        color: {t.text_muted};
        font-size: 10px;
        font-weight: 700;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.accent}, stop:1 {t.info});
        border-radius: 3px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {t.bg_overlay};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        border-radius: {RADIUS_MD}px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 500;
    }}

    /* Menus & Context Menus */
    QMenuBar {{
        background-color: {t.bg_base};
        color: {t.text_secondary};
        border-bottom: 1px solid {t.border_subtle};
        padding: 2px 6px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 4px 10px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
    }}

    QMenu {{
        background-color: {t.bg_overlay};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        border-radius: {RADIUS_LG}px;
        padding: 6px;
    }}

    QMenu::item {{
        padding: 6px 24px 6px 10px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {t.accent_subtle};
        color: {t.text_primary};
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {t.border_subtle};
        margin: 4px 6px;
    }}

    /* Splitters */
    QSplitter::handle {{
        background-color: {t.border_subtle};
    }}

    QSplitter::handle:hover {{
        background-color: {t.border_accent};
    }}

    /* Tab Widgets */
    QTabWidget::pane {{
        border: 1px solid {t.border_subtle};
        background: {t.bg_surface};
        border-radius: {RADIUS_MD}px;
    }}

    QTabBar::tab {{
        background: {t.bg_elevated};
        color: {t.text_muted};
        border: 1px solid {t.border_subtle};
        padding: 6px 14px;
        border-top-left-radius: {RADIUS_SM}px;
        border-top-right-radius: {RADIUS_SM}px;
        margin-right: 2px;
        font-size: 11px;
        font-weight: 600;
    }}

    QTabBar::tab:hover {{
        background: {t.bg_overlay};
        color: {t.text_primary};
    }}

    QTabBar::tab:selected {{
        background: {t.bg_surface};
        color: {t.text_primary};
        border-bottom-color: {t.bg_surface};
        border-top: 2px solid {t.accent};
        font-weight: 700;
    }}

    /* ScrollArea */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {t.bg_base};
        color: {t.text_muted};
        border-top: 1px solid {t.border_subtle};
        font-size: 11px;
    }}
    """


# Backward-compatible global stylesheet constant
APPLICATION_STYLE: str = build_stylesheet()
