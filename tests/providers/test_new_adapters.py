"""Unit tests for OpenRouter, Gemini, OpenAI, DeepSeek, Custom URL adapters, and DubbingAgent."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aidub.contracts.base import Identifier
from aidub.providers.agent_state import AgentState, SegmentState
from aidub.providers.agent_tools import AgentTool, DubbingAgentToolRegistry
from aidub.providers.config import ProviderConfig
from aidub.providers.custom_adapter import CustomUrlAdapter
from aidub.providers.deepseek_adapter import DeepSeekAdapter
from aidub.providers.factory import build_router_from_config
from aidub.providers.gemini_adapter import GeminiAdapter
from aidub.providers.openai_adapter import OpenAIAdapter
from aidub.providers.openrouter_adapter import OpenRouterAdapter
from aidub.providers.router import LlmProviderError, LlmProviderKind


def test_provider_kinds_enum() -> None:
    assert LlmProviderKind.OPENROUTER == "openrouter"
    assert LlmProviderKind.CUSTOM == "custom"
    assert LlmProviderKind.GEMINI == "gemini"
    assert LlmProviderKind.DEEPSEEK == "deepseek"


def test_openrouter_adapter_properties() -> None:
    adapter = OpenRouterAdapter("sk-or-test-key", model="google/gemini-2.0-flash-001")
    assert adapter.provider_kind == LlmProviderKind.OPENROUTER
    assert adapter._model == "google/gemini-2.0-flash-001"


def test_gemini_adapter_properties() -> None:
    adapter = GeminiAdapter("AIzaTestKey", model="gemini-2.0-flash")
    assert adapter.provider_kind == LlmProviderKind.GEMINI
    assert adapter._model_name == "gemini-2.0-flash"


def test_openai_adapter_properties() -> None:
    adapter = OpenAIAdapter("sk-test-key", model="gpt-4o-mini")
    assert adapter.provider_kind == LlmProviderKind.OPENAI
    assert adapter._model == "gpt-4o-mini"


def test_deepseek_adapter_properties() -> None:
    adapter = DeepSeekAdapter("sk-deepseek-key", model="deepseek-chat")
    assert adapter.provider_kind == LlmProviderKind.DEEPSEEK
    assert adapter._model == "deepseek-chat"


def test_custom_adapter_properties() -> None:
    adapter = CustomUrlAdapter(
        api_key="custom-key",
        model="my-custom-model",
        base_url="https://proxy.example.com/v1",
        name="unofficial_deepseek",
    )
    assert adapter.provider_kind == LlmProviderKind.CUSTOM
    assert adapter.name == "unofficial_deepseek"
    assert adapter._base_url == "https://proxy.example.com/v1"


def test_provider_config_env_parser(monkeypatch: os.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env-123")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaEnv123")
    monkeypatch.setenv("OPENROUTER_API_KEYS", "")
    monkeypatch.setenv("GEMINI_API_KEYS", "")
    monkeypatch.setenv("UNOFFICIAL_1_URL", "https://proxy.test/v1")
    monkeypatch.setenv("UNOFFICIAL_1_KEY", "test-key")
    monkeypatch.setenv("UNOFFICIAL_1_MODEL", "test-model")

    cfg = ProviderConfig.from_env(env_file=tmp_path / "absent.env")
    assert cfg.openrouter_api_key == "sk-or-env-123"
    assert cfg.gemini_api_key == "AIzaEnv123"
    assert len(cfg.unofficial_configs) == 1
    assert cfg.unofficial_configs[0].base_url == "https://proxy.test/v1"


def test_provider_config_reads_json_and_delimited_key_pools(
    monkeypatch: os.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-a")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-a")
    monkeypatch.setenv("OPENROUTER_API_KEYS", '["router-a", "router-b", "router-a"]')
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-a, gemini-b\ngemini-c")

    config = ProviderConfig.from_env(env_file=tmp_path / "absent.env")

    assert config.openrouter_api_keys == ["router-a", "router-b"]
    assert config.openrouter_api_key == "router-a"
    assert config.gemini_api_keys == ["gemini-a", "gemini-b", "gemini-c"]
    assert config.gemini_api_key == "gemini-a"


def test_factory_passes_provider_key_pools_to_adapters() -> None:
    config = ProviderConfig(
        provider_priority=["openrouter", "gemini"],
        openrouter_api_keys=["router-a", "router-b"],
        gemini_api_keys=["gemini-a", "gemini-b"],
    )

    router = build_router_from_config(config)

    assert len(router._adapters) == 2
    assert router._adapters[0]._api_keys == ["router-a", "router-b"]
    assert router._adapters[1]._api_keys == ["gemini-a", "gemini-b"]


def test_factory_requires_a_configured_provider() -> None:
    cfg = ProviderConfig()  # No keys set
    with pytest.raises(LlmProviderError, match="no LLM provider is configured"):
        build_router_from_config(cfg)


def test_agent_tool_registry() -> None:
    reg = DubbingAgentToolRegistry()
    tool = AgentTool(
        name="test_tool",
        description="A dummy test tool",
        fn=lambda x: f"result: {x}",
        parameters_schema={"type": "object", "properties": {"x": {"type": "string"}}},
    )
    reg.register(tool)
    schema = reg.get_tools_schema_openai()
    assert len(schema) == 1
    assert schema[0]["function"]["name"] == "test_tool"

    res = reg.execute("test_tool", {"x": "hello"})
    assert res == "result: hello"


def test_agent_state_metrics() -> None:
    segs = [
        SegmentState(
            utterance_id=Identifier("seg_1"),
            speaker_id=Identifier("spk_0"),
            source_text="One",
            start_ms=0,
            end_ms=1000,
            duration_ms=1000,
            passed_qc=True,
        ),
        SegmentState(
            utterance_id=Identifier("seg_2"),
            speaker_id=Identifier("spk_0"),
            source_text="Two",
            start_ms=1000,
            end_ms=2000,
            duration_ms=1000,
            passed_qc=False,
        ),
    ]
    state = AgentState(segments=segs)
    assert state.total_segments == 2
    assert state.passed_count == 1
    assert state.pass_rate == 0.5
    assert state.all_segments_pass(0.80) is False

    state.update_segment_qc("seg_2", quality_score=0.9, passed_qc=True)
    assert state.pass_rate == 1.0
    assert state.all_segments_pass(0.80) is True
