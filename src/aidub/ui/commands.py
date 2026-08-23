"""Framework-neutral command registry used by menus, shortcuts and palettes."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import RLock
from typing import Any

_COMMAND_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class CommandError(RuntimeError):
    """Base command registry error."""


class DuplicateCommandError(CommandError):
    """A command identifier is already registered."""


class UnknownCommandError(CommandError):
    """A requested command is not registered."""


class DisabledCommandError(CommandError):
    """A registered command is currently unavailable."""


EnabledPredicate = Callable[[], bool]
CommandHandler = Callable[..., Any]
CommandListener = Callable[[str, "Command"], None]
Translator = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class Command:
    """A user action independent of any particular UI control."""

    command_id: str
    title_key: str
    handler: CommandHandler
    description_key: str = ""
    shortcuts: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    category: str = "general"
    order: int = 100
    enabled: bool | EnabledPredicate = True

    def __post_init__(self) -> None:
        if not _COMMAND_ID.fullmatch(self.command_id):
            raise ValueError(
                "Command id must be lowercase namespaced text, for example 'workspace.home'."
            )
        if not self.title_key:
            raise ValueError("Command title key cannot be empty.")
        if not callable(self.handler):
            raise TypeError("Command handler must be callable.")
        object.__setattr__(self, "shortcuts", tuple(self.shortcuts))
        object.__setattr__(self, "keywords", tuple(self.keywords))

    def is_enabled(self) -> bool:
        res = self.enabled() if callable(self.enabled) else self.enabled
        return res if isinstance(res, bool) else bool(res)


class CommandRegistry:
    """Thread-safe source of truth for shell actions.

    Qt actions are projections of this registry, not the command source of
    truth.  The same commands can later be invoked by automation, accessibility
    adapters or a remappable shortcut service.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._listeners: list[CommandListener] = []
        self._lock = RLock()

    def register(self, command: Command) -> None:
        self.register_many((command,))

    def register_many(self, commands: Iterable[Command]) -> None:
        additions = tuple(commands)
        if not all(isinstance(item, Command) for item in additions):
            raise TypeError("Only Command instances can be registered.")
        identifiers = [item.command_id for item in additions]
        if len(set(identifiers)) != len(identifiers):
            raise DuplicateCommandError("A command batch contains duplicate identifiers.")
        with self._lock:
            conflict = next((item for item in identifiers if item in self._commands), None)
            if conflict:
                raise DuplicateCommandError(f"Command '{conflict}' is already registered.")
            for command in additions:
                self._commands[command.command_id] = command
            listeners = tuple(self._listeners)
        for command in additions:
            for listener in listeners:
                listener("registered", command)

    def unregister(self, command_id: str) -> Command:
        with self._lock:
            try:
                command = self._commands.pop(command_id)
            except KeyError as exc:
                raise UnknownCommandError(f"Unknown command '{command_id}'.") from exc
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener("unregistered", command)
        return command

    def get(self, command_id: str) -> Command:
        with self._lock:
            try:
                return self._commands[command_id]
            except KeyError as exc:
                raise UnknownCommandError(f"Unknown command '{command_id}'.") from exc

    def all(self) -> tuple[Command, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._commands.values(),
                    key=lambda item: (item.category, item.order, item.command_id),
                )
            )

    def execute(self, command_id: str, /, *args: object, **kwargs: object) -> Any:
        command = self.get(command_id)
        if not command.is_enabled():
            raise DisabledCommandError(f"Command '{command_id}' is disabled.")
        return command.handler(*args, **kwargs)

    def search(
        self,
        query: str,
        *,
        translator: Translator | None = None,
        include_disabled: bool = False,
        limit: int = 25,
    ) -> tuple[Command, ...]:
        """Find commands with stable, deterministic relevance ordering."""

        if limit < 1:
            return ()
        translate = translator or (lambda key: key)
        terms = tuple(part for part in query.casefold().split() if part)
        ranked: list[tuple[int, int, str, Command]] = []
        for command in self.all():
            if not include_disabled and not command.is_enabled():
                continue
            title = translate(command.title_key).casefold()
            searchable = " ".join(
                (title, command.command_id, command.category, *command.keywords)
            ).casefold()
            if terms and not all(term in searchable for term in terms):
                continue
            score = 0
            compact_query = " ".join(terms)
            if compact_query and title == compact_query:
                score = -30
            elif compact_query and title.startswith(compact_query):
                score = -20
            elif terms and command.command_id.startswith(terms[0]):
                score = -10
            ranked.append((score, command.order, title, command))
        ranked.sort(key=lambda item: item[:3])
        return tuple(item[3] for item in ranked[:limit])

    def subscribe(self, listener: CommandListener) -> Callable[[], None]:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def __contains__(self, command_id: object) -> bool:
        with self._lock:
            return command_id in self._commands

    def __len__(self) -> int:
        with self._lock:
            return len(self._commands)
