from pathlib import Path

import pytest
from pydantic import ValidationError

from aidub.infrastructure.config.repository import SettingsRepository
from aidub.infrastructure.config.settings import (
    ApplicationSettings,
    StorageSettings,
)
from aidub.security.privacy import NetworkPolicy


def storage(tmp_path: Path) -> StorageSettings:
    return StorageSettings(
        projects=tmp_path / "projects",
        cache=tmp_path / "cache",
        models=tmp_path / "models",
        temporary=tmp_path / "temporary",
        logs=tmp_path / "logs",
    )


def test_settings_round_trip_atomically(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    settings = ApplicationSettings(
        locale="bn-BD",
        network_policy=NetworkPolicy.OFFLINE,
        storage=storage(tmp_path),
    )
    repository.save(settings)
    assert repository.load() == settings
    assert not list(tmp_path.glob("*.tmp"))


def test_storage_paths_must_be_absolute() -> None:
    with pytest.raises(ValidationError):
        StorageSettings(projects=Path("relative"))


def test_storage_directories_are_created(tmp_path: Path) -> None:
    value = storage(tmp_path)
    value.ensure_directories()
    assert all(
        path.is_dir()
        for path in (
            value.projects,
            value.cache,
            value.models,
            value.temporary,
            value.logs,
        )
    )
