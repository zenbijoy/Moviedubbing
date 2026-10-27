"""Unit tests for the unified UI design system."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from aidub.ui.design import (
    APPLICATION_STYLE,
    ColorTokens,
    ThemeMode,
    build_stylesheet,
    get_icon,
    get_pixmap,
    get_theme_tokens,
    is_reduce_motion_enabled,
    setup_application_fonts,
)
from aidub.ui.design.components import (
    ScoreRingWidget,
    StatusChip,
    StudioButton,
    StudioCard,
    SyllableBudgetIndicator,
)
from aidub.ui.styles import APPLICATION_STYLE as LEGACY_APPLICATION_STYLE


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_theme_tokens_and_presets():
    for mode in ThemeMode:
        tokens = get_theme_tokens(mode)
        assert isinstance(tokens, ColorTokens)
        assert tokens.bg_base.startswith("#")
        assert tokens.bg_surface.startswith("#")
        assert tokens.accent.startswith("#")
        assert tokens.success.startswith("#")
        assert tokens.warning.startswith("#")
        assert tokens.danger.startswith("#")
        assert tokens.ai_purple.startswith("#")


def test_stylesheet_generation():
    for mode in ThemeMode:
        tokens = get_theme_tokens(mode)
        qss = build_stylesheet(tokens)
        assert "QMainWindow" in qss
        assert "QPushButton" in qss
        assert "QLineEdit" in qss
        assert tokens.bg_base in qss
        assert tokens.accent in qss

    # Legacy re-export check
    assert len(LEGACY_APPLICATION_STYLE) > 100
    assert len(APPLICATION_STYLE) > 100


def test_lucide_icon_rendering(qapp):
    icon_names = ["play", "pause", "film", "mic", "sparkles", "cloud", "settings", "check"]
    for name in icon_names:
        pix = get_pixmap(name, size=16, color_hex="#3B82F6")
        assert isinstance(pix, QPixmap)
        assert not pix.isNull()
        assert pix.width() == 16
        assert pix.height() == 16

        icon = get_icon(name, size=16)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()


def test_components_lifecycle(qapp):
    btn = StudioButton("Dub Movie", variant="primary", icon_name="mic")
    assert btn.text() == "Dub Movie"
    assert btn.property("variant") == "primary"

    card = StudioCard(tier="elevated")
    assert card.property("tier") == "elevated"

    chip = StatusChip("Offline", state="info")
    assert chip._text_lbl.text() == "Offline"
    chip.update_state("success", "Done")
    assert chip._text_lbl.text() == "Done"

    meter = SyllableBudgetIndicator()
    meter.set_budget(orig_dur=2.5, dub_dur=2.7, orig_syl=8, dub_syl=9)
    assert abs(meter.delta_seconds - 0.2) < 0.001

    ring = ScoreRingWidget(score=0.88)
    assert ring.score == 0.88
    ring.set_score(None)
    assert ring.score is None

    setup_application_fonts(qapp)
    assert isinstance(is_reduce_motion_enabled(), bool)
