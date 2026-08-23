"""Provider Factory — Builds LlmProviderRouter from ProviderConfig."""

from __future__ import annotations

import logging

from aidub.providers.config import ProviderConfig
from aidub.providers.custom_adapter import CustomUrlAdapter
from aidub.providers.deepseek_adapter import DeepSeekAdapter
from aidub.providers.gemini_adapter import GeminiAdapter
from aidub.providers.openai_adapter import OpenAIAdapter
from aidub.providers.openrouter_adapter import OpenRouterAdapter
from aidub.providers.router import (
    LlmAdapter,
    LlmProviderError,
    LlmProviderRouter,
    LlmRouterConfig,
)

logger = logging.getLogger(__name__)


def build_router_from_config(
    config: ProviderConfig | None = None,
    router_config: LlmRouterConfig | None = None,
) -> LlmProviderRouter:
    """
    Constructs an LlmProviderRouter with active LLM adapters based on configuration.
    
    Adapters are instantiated and ordered according to ``config.provider_priority``.
    A configured, real provider is mandatory.  Missing credentials are surfaced
    as a configuration error instead of returning fabricated translations.
    """
    cfg = config or ProviderConfig.from_env()
    adapters: list[LlmAdapter] = []

    for name in cfg.provider_priority:
        name_lower = name.lower().strip()
        
        if name_lower == "openrouter" and cfg.openrouter_api_key:
            adapters.append(OpenRouterAdapter(
                api_key=cfg.openrouter_api_key,
                model=cfg.openrouter_model,
                site_url=cfg.openrouter_site_url,
                app_name=cfg.openrouter_app_name,
            ))
            logger.info("LLM Router: Registered OpenRouter (%s)", cfg.openrouter_model)

        elif name_lower == "gemini" and cfg.gemini_api_key:
            adapters.append(GeminiAdapter(
                api_key=cfg.gemini_api_key,
                model=cfg.gemini_model,
            ))
            logger.info("LLM Router: Registered Gemini API (%s)", cfg.gemini_model)

        elif name_lower == "openai" and cfg.openai_api_key:
            adapters.append(OpenAIAdapter(
                api_key=cfg.openai_api_key,
                model=cfg.openai_model,
                base_url=cfg.openai_base_url,
            ))
            logger.info("LLM Router: Registered OpenAI API (%s)", cfg.openai_model)

        elif name_lower == "deepseek" and cfg.deepseek_api_key:
            adapters.append(DeepSeekAdapter(
                api_key=cfg.deepseek_api_key,
                model=cfg.deepseek_model,
                base_url=cfg.deepseek_base_url,
            ))
            logger.info("LLM Router: Registered DeepSeek API (%s)", cfg.deepseek_model)

        elif name_lower == "unofficial" and cfg.unofficial_configs:
            for uc in cfg.unofficial_configs:
                if uc.base_url:
                    adapters.append(CustomUrlAdapter(
                        api_key=uc.api_key,
                        model=uc.model,
                        base_url=uc.base_url,
                        extra_headers=uc.extra_headers,
                        name=uc.name,
                    ))
                    logger.info("LLM Router: Registered Custom API '%s' (%s at %s)", uc.name, uc.model, uc.base_url)

    if not adapters:
        raise LlmProviderError(
            "configuration",
            "no LLM provider is configured; add an OpenRouter, Gemini, OpenAI, "
            "DeepSeek, or custom endpoint credential",
            retryable=False,
        )

    return LlmProviderRouter(adapters=adapters, config=router_config)


__all__ = ["build_router_from_config"]
