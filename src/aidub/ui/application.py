"""Desktop application lifecycle and a graceful optional-dependency entrypoint."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from aidub import __version__
from aidub.i18n import CatalogError, LocaleService

from .qt_support import DesktopDependencyError, require_pyside6
from .styles import APPLICATION_STYLE

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
        from PySide6.QtCore import QCoreApplication  # noqa: PLC0415
        from PySide6.QtGui import QFont  # noqa: PLC0415
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415

        from .studio_window import AIDubStudioWindow  # noqa: PLC0415

        existing = QApplication.instance()
        self.application = existing or QApplication(list(argv) if argv is not None else sys.argv)
        self.owns_application = existing is None
        QCoreApplication.setOrganizationName("AI Dubbing Studio")
        QCoreApplication.setOrganizationDomain("aidubbing.studio")
        QCoreApplication.setApplicationName("AI Movie Dubbing Studio")
        QCoreApplication.setApplicationVersion(__version__)
        if hasattr(self.application, "setFont"):
            default_font = QFont("Segoe UI", 10)
            default_font.setStyleHint(QFont.StyleHint.SansSerif)
            QFont.insertSubstitutions(
                "Segoe UI", ["Segoe UI Variable", "Inter", "Arial", "sans-serif"]
            )
            self.application.setFont(default_font)
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
        desktop = DesktopApplication(argv, locale=locale)
    except (DesktopDependencyError, CatalogError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    return desktop.run()


if __name__ == "__main__":
    sys.exit(run_desktop())
