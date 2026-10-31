from __future__ import annotations

from typing import Any, cast

import pytest

from aidub.ui.models import Connectivity, PrivacyMode, ShellState, ShellStatus


def test_shell_defaults_are_offline_and_local_only() -> None:
    status = ShellStatus()

    assert status.connectivity is Connectivity.OFFLINE
    assert status.privacy_mode is PrivacyMode.LOCAL_ONLY
    assert status.ready is True


def test_shell_state_emits_changed_snapshots_only() -> None:
    state = ShellState()
    observed: list[ShellStatus] = []
    unsubscribe = state.subscribe(observed.append, emit_current=True)
    state.replace(state.status)
    changed = state.update(connectivity=Connectivity.ONLINE, privacy_mode=PrivacyMode.HYBRID)
    unsubscribe()
    state.update(active_project_name="Ignored after unsubscribe")

    assert observed == [ShellStatus(), changed]


def test_shell_state_rejects_unknown_fields() -> None:
    state = ShellState()

    with pytest.raises(TypeError):
        cast("Any", state.update)(not_a_field=True)
