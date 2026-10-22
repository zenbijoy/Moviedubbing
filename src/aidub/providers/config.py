"""Configuration schema and .env loader for LLM providers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from aidub.contracts.base import ContractModel


@dataclass
class UnofficialConfig:
    """Configuration for an unofficial / custom OpenAI-compatible API endpoint."""

    name: str = "custom"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


class ProviderConfig(ContractModel):
    """
    Multi-provider LLM system configuration.

    Loads configuration from environment variables or a `.env` file automatically.
    """

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_api_keys: list[str] = field(default_factory=list)
    openrouter_model: str = "minimax/minimax-m3.1-flash:free"
    openrouter_site_url: str = ""
    openrouter_app_name: str = "aidub"

    # Google Gemini
    gemini_api_key: str = ""
    gemini_api_keys: list[str] = field(default_factory=list)
    gemini_model: str = "gemini-3.8-flash"

    # OpenAI / ChatGPT
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    # Unofficial / Custom endpoints
    unofficial_configs: list[UnofficialConfig] = field(default_factory=list)

    # Provider priority list (tried in this order)
    provider_priority: list[str] = field(
        default_factory=lambda: ["openrouter", "gemini", "openai", "deepseek", "unofficial"]
    )

    # Agent Loop parameters
    use_agent_loop: bool = True
    agent_max_iterations: int = 20
    agent_quality_threshold: float = 0.80

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> ProviderConfig:
        """Create ProviderConfig by reading environment variables (and optional .env file)."""
        if env_file:
            _load_dotenv(Path(env_file))
        else:
            # Check cwd and parent locations for .env and keys.json
            env_candidates = [
                Path(".env"),
                Path(__file__).resolve().parents[3] / ".env",
                Path.home() / ".aidub" / ".env",
            ]
            for p in env_candidates:
                if p.exists():
                    _load_dotenv(p)
                    break

            json_candidates = [
                Path("keys.json"),
                Path(".keys.json"),
                Path(__file__).resolve().parents[3] / "keys.json",
                Path(__file__).resolve().parents[3] / ".keys.json",
            ]
            for jp in json_candidates:
                if jp.exists():
                    _load_keys_json(jp)
                    break

        unofficial_list: list[UnofficialConfig] = []
        # Check for UNOFFICIAL_1_URL, UNOFFICIAL_2_URL, etc.
        idx = 1
        while True:
            prefix = f"UNOFFICIAL_{idx}_"
            url = os.getenv(f"{prefix}URL")
            if not url:
                break
            key = os.getenv(f"{prefix}KEY", "")
            model = os.getenv(f"{prefix}MODEL", "default")
            name = os.getenv(f"{prefix}NAME", f"unofficial_{idx}")
            unofficial_list.append(
                UnofficialConfig(name=name, api_key=key, base_url=url, model=model)
            )
            idx += 1

        priority_str = os.getenv("PROVIDER_PRIORITY")
        priority = (
            [p.strip().lower() for p in priority_str.split(",")]
            if priority_str
            else ["openrouter", "gemini", "openai", "deepseek", "unofficial"]
        )

        def _parse_keys(env_var: str, single_val: str) -> tuple[str, list[str]]:
            raw = os.getenv(env_var, "").strip()
            keys: list[str] = []
            if raw:
                if raw.startswith("[") and raw.endswith("]"):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            keys = [
                                key.strip()
                                for key in parsed
                                if isinstance(key, str) and key.strip()
                            ]
                    except json.JSONDecodeError:
                        pass
                if not keys:
                    keys = [
                        key.strip().strip("'\"")
                        for key in raw.replace(";", ",").replace("\n", ",").split(",")
                        if key.strip().strip("'\"")
                    ]
            keys = list(dict.fromkeys(keys))
            primary = single_val.strip()
            if not primary and keys:
                primary = keys[0]
            if primary and primary not in keys:
                keys.insert(0, primary)
            return primary, keys

        or_key, or_keys = _parse_keys("OPENROUTER_API_KEYS", os.getenv("OPENROUTER_API_KEY", ""))
        gem_key, gem_keys = _parse_keys("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))

        return cls(
            openrouter_api_key=or_key,
            openrouter_api_keys=or_keys,
            openrouter_model=os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3.1-flash:free"),
            openrouter_site_url=os.getenv("OPENROUTER_SITE_URL", ""),
            gemini_api_key=gem_key,
            gemini_api_keys=gem_keys,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            unofficial_configs=unofficial_list,
            provider_priority=priority,
        )


def _load_dotenv(path: Path) -> None:
    """Simple .env file parser."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and not os.getenv(k):
                os.environ[k] = v
    except Exception:
        pass


def _load_keys_json(path: Path) -> None:
    """Parse a keys.json file and populate environment if unset."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        mapping = {
            "gemini_api_key": "GEMINI_API_KEY",
            "openrouter_api_key": "OPENROUTER_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "deepseek_api_key": "DEEPSEEK_API_KEY",
        }
        for json_key, env_var in mapping.items():
            val = data.get(json_key)
            if val and isinstance(val, str) and not os.getenv(env_var):
                os.environ[env_var] = val.strip()

        # Array keys
        for key_name, env_var in [
            ("gemini_api_keys", "GEMINI_API_KEYS"),
            ("openrouter_api_keys", "OPENROUTER_API_KEYS"),
        ]:
            arr = data.get(key_name)
            if isinstance(arr, list) and arr and not os.getenv(env_var):
                os.environ[env_var] = ",".join(str(k).strip() for k in arr if str(k).strip())
    except Exception:
        pass


__all__ = ["ProviderConfig", "UnofficialConfig"]
