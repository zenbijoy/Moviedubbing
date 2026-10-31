"""Common imports and shared utilities for the Studio window modules."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction, QBrush, QCloseEvent, QColor, QDesktopServices, QDragEnterEvent,
    QDropEvent, QKeyEvent, QKeySequence,
)
from PySide6.QtWidgets import QApplication

_QT = None
logger = None

import logging
logger = logging.getLogger(__name__)

from ._studio_window import AIDubStudioWindow  # noqa: F401
__all__ = ["_QT", "UTC", "datetime", "Path", "Any", "Qt", "QThread", "QTimer",
           "QUrl", "Signal", "QAction", "QBrush", "QCloseEvent", "QColor",
           "QDesktopServices", "QDragEnterEvent", "QDropEvent", "QKeyEvent",
           "QKeySequence", "QApplication", "AIDubStudioWindow", "logger"]
