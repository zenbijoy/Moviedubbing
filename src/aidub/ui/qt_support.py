"""Optional Qt dependency boundary and operator-facing diagnostics."""

from __future__ import annotations

try:
    import PySide6  # noqa: F401
except Exception as _error:
    _PYSIDE6_IMPORT_ERROR: Exception | None = _error
else:
    _PYSIDE6_IMPORT_ERROR = None

PYSIDE6_AVAILABLE = _PYSIDE6_IMPORT_ERROR is None


class DesktopDependencyError(RuntimeError):
    """The optional native desktop runtime is not available."""


def desktop_dependency_message() -> str:
    message = (
        "AI Movie Dubbing Studio cannot start its desktop interface because PySide6 "
        "is unavailable. Install the project's desktop dependencies (or run "
        "`python -m pip install PySide6`) and start the application again."
    )
    if _PYSIDE6_IMPORT_ERROR is not None:
        message += f"\nDetected dependency error: {_PYSIDE6_IMPORT_ERROR}"
    return message


def require_pyside6() -> None:
    if not PYSIDE6_AVAILABLE:
        raise DesktopDependencyError(desktop_dependency_message()) from _PYSIDE6_IMPORT_ERROR
