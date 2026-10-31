from __future__ import annotations

import pytest

from aidub.ui import application as desktop_application
from aidub.ui.qt_support import (
    PYSIDE6_AVAILABLE,
    DesktopDependencyError,
    desktop_dependency_message,
    require_pyside6,
)


def test_dependency_diagnostic_is_actionable() -> None:
    message = desktop_dependency_message()

    assert "PySide6" in message
    assert "install" in message.casefold()


def test_require_pyside6_matches_reported_availability() -> None:
    if PYSIDE6_AVAILABLE:
        require_pyside6()
    else:
        with pytest.raises(DesktopDependencyError, match="PySide6"):
            require_pyside6()


def test_run_desktop_returns_diagnostic_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class MissingDesktop:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise DesktopDependencyError("desktop dependency test failure")

    monkeypatch.setattr(desktop_application, "DesktopApplication", MissingDesktop)

    assert desktop_application.run_desktop([]) == 2
    assert "desktop dependency test failure" in capsys.readouterr().err
