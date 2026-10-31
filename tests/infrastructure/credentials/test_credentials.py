from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aidub.infrastructure.credentials.base import MemorySecretStore
from aidub.infrastructure.credentials.dpapi import DpapiFileSecretStore


def test_memory_store_lifecycle() -> None:
    store = MemorySecretStore()
    store.set("provider.openai", "secret")
    assert store.get("provider.openai") == "secret"
    assert store.delete("provider.openai")
    assert store.get("provider.openai") is None


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows DPAPI")
def test_dpapi_store_round_trip_and_plaintext_is_not_persisted(tmp_path: Path) -> None:
    store = DpapiFileSecretStore(tmp_path)
    secret = "high-value-secret-123"
    store.set("provider.openai", secret)
    files = list(tmp_path.glob("*.credential"))
    assert len(files) == 1
    assert secret.encode() not in files[0].read_bytes()
    assert store.get("provider.openai") == secret
    assert store.delete("provider.openai")
    assert store.get("provider.openai") is None


def test_invalid_credential_names_are_rejected(tmp_path: Path) -> None:
    store = MemorySecretStore()
    with pytest.raises(ValueError):
        store.set("", "secret")
