from __future__ import annotations

import pytest

from aidub.ui.commands import (
    Command,
    CommandRegistry,
    DisabledCommandError,
    DuplicateCommandError,
    UnknownCommandError,
)


def test_register_and_execute_command() -> None:
    registry = CommandRegistry()
    calls: list[str] = []
    registry.register(Command("workspace.home", "command.home", calls.append))

    registry.execute("workspace.home", "opened")

    assert calls == ["opened"]
    assert "workspace.home" in registry


def test_registration_batch_is_atomic_on_duplicate() -> None:
    registry = CommandRegistry()
    registry.register(Command("workspace.home", "command.home", lambda: None))

    with pytest.raises(DuplicateCommandError):
        registry.register_many(
            (
                Command("workspace.projects", "command.projects", lambda: None),
                Command("workspace.home", "command.home", lambda: None),
            )
        )

    assert "workspace.projects" not in registry
    assert len(registry) == 1


def test_disabled_and_unknown_commands_fail_explicitly() -> None:
    registry = CommandRegistry()
    registry.register(Command("job.cancel", "command.cancel", lambda: None, enabled=False))

    with pytest.raises(DisabledCommandError):
        registry.execute("job.cancel")
    with pytest.raises(UnknownCommandError):
        registry.execute("job.missing")


def test_search_uses_translated_title_keywords_and_stable_order() -> None:
    registry = CommandRegistry()
    registry.register_many(
        (
            Command(
                "workspace.projects",
                "command.projects",
                lambda: None,
                keywords=("library", "media"),
                category="workspace",
                order=20,
            ),
            Command(
                "workspace.home",
                "command.home",
                lambda: None,
                category="workspace",
                order=10,
            ),
        )
    )
    translations = {"command.projects": "परियोजनाएँ", "command.home": "होम"}

    translated_matches = registry.search("परि", translator=translations.__getitem__)
    keyword_matches = registry.search("media", translator=translations.__getitem__)
    all_commands = registry.search("", translator=translations.__getitem__)

    assert [item.command_id for item in translated_matches] == ["workspace.projects"]
    assert [item.command_id for item in keyword_matches] == ["workspace.projects"]
    assert [item.command_id for item in all_commands] == [
        "workspace.home",
        "workspace.projects",
    ]


def test_registry_subscription_reports_lifecycle() -> None:
    registry = CommandRegistry()
    events: list[tuple[str, str]] = []
    unsubscribe = registry.subscribe(
        lambda event, command: events.append((event, command.command_id))
    )
    registry.register(Command("workspace.home", "command.home", lambda: None))
    registry.unregister("workspace.home")
    unsubscribe()

    assert events == [
        ("registered", "workspace.home"),
        ("unregistered", "workspace.home"),
    ]


@pytest.mark.parametrize("command_id", ("", "Workspace.Home", "two words", ".home"))
def test_command_identifier_is_strict(command_id: str) -> None:
    with pytest.raises(ValueError):
        Command(command_id, "command.home", lambda: None)
