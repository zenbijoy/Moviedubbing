"""Universal Custom / Unofficial API Adapter.

Connects to any OpenAI-compatible API endpoint provided by the user,
including custom gateways, unofficial proxy APIs, local LLM wrappers,
and custom model deployments.
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


class CustomUrlAdapter:
    """
    Universal LLM adapter for custom or unofficial OpenAI-compatible APIs.

    Args:
        api_key:       Auth token or API key for the custom gateway.
        model:         Target model identifier expected by the proxy.
        base_url:      Full API base URL (e.g. ``https://my-proxy.example.com/v1``).
        timeout_s:     HTTP timeout in seconds.
        extra_headers: Custom HTTP headers required by the proxy.
        name:          Optional label/name for logging (e.g. "unofficial_gemini").
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        *,
        timeout_s: float = 120.0,
        extra_headers: dict[str, str] | None = None,
        name: str = "custom",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._extra_headers = extra_headers or {}
        self.name = name
        self._client: Any | None = None  # lazy-init

    # ── LlmAdapter protocol ───────────────────────────────────────────────────

    @property
    def provider_kind(self) -> LlmProviderKind:
        return LlmProviderKind.CUSTOM

    def complete(self, request: LlmRequest) -> LlmResponse:
        """Send a completion request to the custom API endpoint."""
        client = self._get_client()
        messages = _build_messages(request)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "timeout": self._timeout_s,
        }

        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.monotonic()
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LlmProviderError(
                self.name,
                f"Custom API error ({self._base_url}): {exc}",
                retryable=_is_retryable(exc),
            ) from exc

        latency_ms = (time.monotonic() - t0) * 1_000
        content = (resp.choices[0].message.content or "").strip()

        if not content:
            raise LlmProviderError(self.name, "empty response content", retryable=True)

        logger.debug(
            "custom_adapter[%s]: model=%s tokens=%s/%s latency=%.0fms",
            self.name,
            self._model,
            resp.usage.prompt_tokens if resp.usage else "?",
            resp.usage.completion_tokens if resp.usage else "?",
            latency_ms,
        )

        return LlmResponse(
            request_id=request.request_id,
            provider_kind=LlmProviderKind.CUSTOM,
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
                from openai import OpenAI  # type: ignore[import-not-found]
            except ImportError as exc:
                raise LlmProviderError(
                    self.name,
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
    if any(k in msg for k in ("401", "403", "unauthorized", "forbidden")):
        return False
    if any(k in msg for k in ("429", "rate limit", "503", "timeout", "overloaded")):
        return True
    return True


__all__ = ["CustomUrlAdapter"]
