"""User settings and application preferences persistence.

Provides:
  - UserPreferences: typed Pydantic configuration model
  - load_user_preferences(): loads from platformdirs user config dir with fallback
  - save_user_preferences(): writes configuration atomically to avoid corruption
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

import platformdirs
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ThemeOption = Literal[
    "studio_dark",
    "broadcast_gray",
    "cyber_dark",
    "high_contrast",
    "light_studio",
]

HardwareOption = Literal["auto", "cpu", "cuda", "directml"]
PrivacyOption = Literal["online", "offline"]


class UserPreferences(BaseModel):
    """User-configurable settings persisted across desktop sessions."""

    theme: ThemeOption = "studio_dark"
    default_target_language: str = Field(default="bn-BD", min_length=2, max_length=16)
    default_tts_engine: str = Field(default="edge-tts", min_length=1, max_length=64)
    auto_save_interval_minutes: int = Field(default=3, ge=0, le=60)
    hardware_acceleration: HardwareOption = "auto"
    privacy_mode: PrivacyOption = "online"
    recent_projects_limit: int = Field(default=10, ge=1, le=50)


def get_default_preferences_path() -> Path:
    """Return default writable path for user preferences JSON."""
    config_dir = Path(platformdirs.user_config_dir("aidub", "AIDubStudio"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "preferences.json"


def load_user_preferences(path: Path | None = None) -> UserPreferences:
    """Load user preferences from JSON file with safe defaults fallback."""
    cfg_path = path or get_default_preferences_path()
    if not cfg_path.is_file():
        return UserPreferences()

    try:
        raw_text = cfg_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        return UserPreferences.model_validate(data)
    except Exception as exc:
        logger.warning("Could not read preferences from %s: %s (using defaults)", cfg_path, exc)
        return UserPreferences()


def save_user_preferences(prefs: UserPreferences, path: Path | None = None) -> bool:
    """Save user preferences atomically to disk."""
    cfg_path = path or get_default_preferences_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = cfg_path.with_suffix(".tmp")
    try:
        payload = prefs.model_dump_json(indent=2)
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(cfg_path)
        logger.info("Saved user preferences to %s", cfg_path)
        return True
    except Exception as exc:
        logger.error("Failed to save preferences to %s: %s", cfg_path, exc)
        tmp_path.unlink(missing_ok=True)
        return False


__all__ = [
    "HardwareOption",
    "PrivacyOption",
    "ThemeOption",
    "UserPreferences",
    "get_default_preferences_path",
    "load_user_preferences",
    "save_user_preferences",
]
