"""DeepSeek LLM adapter (Official DeepSeek API + Unofficial endpoints).

Supports:
  - deepseek-chat     (DeepSeek-V3 — fast, cheap, highly accurate translation)
  - deepseek-reasoner (DeepSeek-R1 — reasoning model with chain-of-thought)

DeepSeek uses the OpenAI API format, so we use the ``openai`` SDK pointed
at ``https://api.deepseek.com`` (or a custom base_url for unofficial proxies).

https://platform.deepseek.com/docs
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aidub.providers.router import (
    LlmProviderError,
    LlmProviderKind,
    LlmRequest,
    LlmResponse,
)

logger = logging.getLogger(__name__)

OFFICIAL_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekAdapter:
    """
    LLM adapter for DeepSeek models (official API or unofficial proxy).

    Args:
        api_key:       DeepSeek API key (``sk-…``).
        model:         Model name (``deepseek-chat`` or ``deepseek-reasoner``).
        base_url:      API base URL. Defaults to official DeepSeek endpoint.
                       Can be overridden for unofficial proxies.
        timeout_s:     HTTP timeout in seconds.
        extra_headers: Custom HTTP headers if needed for proxy auth.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        base_url: str = OFFICIAL_BASE_URL,
        timeout_s: float = 120.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._extra_headers = extra_headers or {}
        self._client: Any | None = None  # lazy-init

    # ── LlmAdapter protocol ───────────────────────────────────────────────────

    @property
    def provider_kind(self) -> LlmProviderKind:
        return LlmProviderKind.DEEPSEEK

    def complete(self, request: LlmRequest) -> LlmResponse:
        """Send a chat completion request to DeepSeek."""
        client = self._get_client()
        messages = _build_messages(request)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "timeout": self._timeout_s,
        }

        # DeepSeek supports json_object format for chat model
        if request.json_mode and self._model == "deepseek-chat":
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.monotonic()
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LlmProviderError(
                "deepseek", f"API error: {exc}", retryable=_is_retryable(exc)
            ) from exc

        latency_ms = (time.monotonic() - t0) * 1_000
        content = (resp.choices[0].message.content or "").strip()

        if not content:
            raise LlmProviderError("deepseek", "empty response content", retryable=True)

        logger.debug(
            "deepseek: model=%s tokens=%s/%s latency=%.0fms",
            self._model,
            resp.usage.prompt_tokens if resp.usage else "?",
            resp.usage.completion_tokens if resp.usage else "?",
            latency_ms,
        )

        return LlmResponse(
            request_id=request.request_id,
            provider_kind=LlmProviderKind.DEEPSEEK,
            model_name=self._model,
            content=content,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            latency_ms=round(latency_ms, 1),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LlmProviderError(
                    "deepseek",
                    "openai package not installed — run: pip install openai",
                    retryable=False,
                ) from exc
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                default_headers=self._extra_headers,
            )
        return self._client


# ── Module helpers ────────────────────────────────────────────────────────────


def _build_messages(request: LlmRequest) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if request.system_prompt:
        msgs.append({"role": "system", "content": request.system_prompt})
    msgs.append({"role": "user", "content": request.user_prompt})
    return msgs


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(k in msg for k in ("401", "403", "invalid_api_key", "balance")):
        return False
    if any(k in msg for k in ("429", "rate limit", "503", "timeout", "busy")):
        return True
    return True


__all__ = ["DEFAULT_MODEL", "OFFICIAL_BASE_URL", "DeepSeekAdapter"]
