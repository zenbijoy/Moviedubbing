"""Desktop application lifecycle and a graceful optional-dependency entrypoint."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from aidub import __version__
from aidub.i18n import CatalogError, LocaleService
from aidub.ui.design import APPLICATION_STYLE, setup_application_fonts
from aidub.ui.qt_support import DesktopDependencyError, require_pyside6

if TYPE_CHECKING:
    from collections.abc import Sequence


class DesktopApplication:
    """Own the Qt application, localization service and top-level window."""

    def __init__(
        self,
        argv: Sequence[str] | None = None,
        *,
        locale: str | None = None,
    ) -> None:
        require_pyside6()
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication

        from .studio_window import AIDubStudioWindow

        existing = QApplication.instance()
        self.application = existing or QApplication(list(argv) if argv is not None else sys.argv)
        self.owns_application = existing is None
        QCoreApplication.setOrganizationName("AI Dubbing Studio")
        QCoreApplication.setOrganizationDomain("aidubbing.studio")
        QCoreApplication.setApplicationName("AI Movie Dubbing Studio")
        QCoreApplication.setApplicationVersion(__version__)
        if hasattr(self.application, "setFont"):
            setup_application_fonts(self.application)
        if hasattr(self.application, "setStyleSheet"):
            self.application.setStyleSheet(APPLICATION_STYLE)
        self.locale_service = LocaleService(locale)
        self.window = AIDubStudioWindow(locale_service=self.locale_service)

    def show(self) -> None:
        if hasattr(self.window, "show"):
            self.window.show()

    def run(self) -> int:
        self.show()
        if hasattr(self.application, "exec"):
            return int(self.application.exec())
        return 0


def run_desktop(
    argv: Sequence[str] | None = None,
    *,
    locale: str | None = None,
) -> int:
    """Start the desktop UI and return a process exit code.

    Missing Qt packages and damaged localization resources are reported as
    concise operator diagnostics, making this safe as a console-script target.
    """

    try:
        app = DesktopApplication(argv, locale=locale)
        return app.run()
    except DesktopDependencyError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2
    except CatalogError as exc:
        sys.stderr.write(f"Localization Error: {exc}\n")
        return 2
