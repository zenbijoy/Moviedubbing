from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="desktop dependency is tested in the Windows desktop lane")

from aidub.ui.application import DesktopApplication


def test_native_shell_starts_and_switches_indic_locales(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    desktop = DesktopApplication([], locale="bn-BD")
    try:
        desktop.show()
        desktop.application.processEvents()
        assert desktop.window.isVisible()
        assert desktop.window.stack.currentWidget() is desktop.window.home_view
        desktop.window.show_studio()
        assert desktop.window.stack.currentWidget() is desktop.window.studio
        assert desktop.locale_service.locale == "bn-BD"
        assert desktop.window.windowTitle() == desktop.locale_service("app.title")

        desktop.locale_service.set_locale("hi-IN")
        desktop.application.processEvents()
        assert desktop.locale_service.locale == "hi-IN"
        assert desktop.window.windowTitle() == desktop.locale_service("app.title")
    finally:
        desktop.window.close()
        desktop.application.processEvents()
