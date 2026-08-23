"""Searchable keyboard command palette."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from .qt_support import PYSIDE6_AVAILABLE, DesktopDependencyError, desktop_dependency_message

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QWidget

    from aidub.i18n import LocaleService

    from .commands import CommandRegistry


if PYSIDE6_AVAILABLE:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QDialog,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except Exception as _caught_qt_error:  # noqa: BLE001 - catches native Qt load errors.
        _QT_WIDGETS_AVAILABLE = False
        _QT_WIDGETS_IMPORT_ERROR: Exception | None = _caught_qt_error
    else:
        _QT_WIDGETS_AVAILABLE = True
        _QT_WIDGETS_IMPORT_ERROR = None
else:
    _QT_WIDGETS_AVAILABLE = False
    _QT_WIDGETS_IMPORT_ERROR = None


if _QT_WIDGETS_AVAILABLE:

    class CommandPaletteDialog(QDialog):  # type: ignore[misc]
        """Modal palette projected from a :class:`CommandRegistry`."""

        def __init__(
            self,
            registry: CommandRegistry,
            locale_service: LocaleService,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._registry = registry
            self._locale = locale_service
            self.setObjectName("CommandPalette")
            self.setModal(True)
            self.setMinimumSize(560, 390)
            self.setWindowTitle(self._locale("command.palette"))

            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 14, 14, 14)
            self._query = QLineEdit(self)
            self._query.setAccessibleName(self._locale("command.palette"))
            self._query.setPlaceholderText(self._locale("command.palette.hint"))
            self._results = QListWidget(self)
            self._results.setObjectName("CommandResults")
            self._results.setAccessibleName(self._locale("command.palette"))
            layout.addWidget(self._query)
            layout.addWidget(self._results, 1)

            self._query.textChanged.connect(self._refresh_results)
            self._query.returnPressed.connect(self._execute_current)
            self._results.itemActivated.connect(lambda _item: self._execute_current())
            self._refresh_results("")

        @override
        def showEvent(self, event: object) -> None:
            super().showEvent(event)
            self._query.clear()
            self._query.setFocus(Qt.FocusReason.PopupFocusReason)

        @override
        def keyPressEvent(self, event: QKeyEvent) -> None:
            if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down} and self._query.hasFocus():
                row = self._results.currentRow()
                delta = -1 if event.key() == Qt.Key.Key_Up else 1
                self._results.setCurrentRow(max(0, min(self._results.count() - 1, row + delta)))
                return
            super().keyPressEvent(event)

        def _refresh_results(self, query: str) -> None:
            self._results.clear()
            commands = self._registry.search(query, translator=self._locale.translate)
            for command in commands:
                shortcut = f"    {command.shortcuts[0]}" if command.shortcuts else ""
                item = QListWidgetItem(f"{self._locale(command.title_key)}{shortcut}")
                item.setData(Qt.ItemDataRole.UserRole, command.command_id)
                if command.description_key:
                    item.setToolTip(self._locale(command.description_key))
                self._results.addItem(item)
            if self._results.count():
                self._results.setCurrentRow(0)

        def _execute_current(self) -> None:
            item = self._results.currentItem()
            if item is None:
                return
            command_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            self._registry.execute(str(command_id))

else:

    class CommandPaletteDialog:  # type: ignore[no-redef]  # pragma: no cover
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            detail = (
                f"\nQt Widgets error: {_QT_WIDGETS_IMPORT_ERROR}"
                if _QT_WIDGETS_IMPORT_ERROR
                else ""
            )
            raise DesktopDependencyError(desktop_dependency_message() + detail)

        def exec(self) -> int:
            return 0
