"""Multi-provider LLM router with circuit breaker, exponential backoff, and failover."""

from __future__ import annotations

import logging
import time
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class LlmProviderKind(StrEnum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"  # 100+ models via single OpenAI-compatible endpoint
    CUSTOM = "custom"  # any unofficial / custom base-URL provider
    OLLAMA = "ollama"
    LOCAL_LLAMACPP = "local_llamacpp"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class LlmRequest(ContractModel):
    """Validated LLM request payload."""

    request_id: Identifier
    provider_kind: LlmProviderKind | None = None
    model_name: str = Field(default="", max_length=128)
    system_prompt: str = Field(default="", max_length=32_000)
    user_prompt: str = Field(min_length=1, max_length=128_000)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4_096, ge=1, le=32_768)
    json_mode: bool = True


class LlmResponse(ContractModel):
    """Validated response returned by an LLM provider adapter."""

    request_id: Identifier
    provider_kind: LlmProviderKind
    model_name: str
    content: str = Field(min_length=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)


class LlmProviderError(RuntimeError):
    """Raised by an LLM adapter when the provider returns an error."""

    def __init__(self, provider: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.retryable = retryable


@runtime_checkable
class LlmAdapter(Protocol):
    """Protocol for a single LLM provider adapter."""

    @property
    def provider_kind(self) -> LlmProviderKind: ...

    def complete(self, request: LlmRequest) -> LlmResponse: ...


class CircuitBreaker:
    """Simple half-open circuit breaker per provider."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._opened_at and time.monotonic() - self._opened_at >= self._recovery_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def is_available(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


class ExponentialBackoff:
    """Exponential backoff with jitter for retry scheduling."""

    def __init__(
        self,
        base_delay_ms: float = 200.0,
        max_delay_ms: float = 5_000.0,
        multiplier: float = 2.0,
    ) -> None:
        self._base = base_delay_ms
        self._max = max_delay_ms
        self._multiplier = multiplier

    def delay_seconds(self, attempt: int) -> float:
        delay_ms = min(self._max, self._base * (self._multiplier**attempt))
        return delay_ms / 1_000.0


class LlmRouterConfig(ContractModel):
    """Configuration for the multi-provider LLM router."""

    max_retries_per_provider: int = Field(default=2, ge=0, le=5)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=10)
    circuit_recovery_seconds: float = Field(default=30.0, ge=1.0, le=300.0)


class LlmProviderRouter:
    """
    Multi-provider LLM router with circuit breaker and automatic failover.

    Adapters are tried in registration order. If a provider circuit is OPEN
    or all retries are exhausted, the router falls over to the next adapter.
    """

    def __init__(
        self,
        adapters: list[LlmAdapter],
        config: LlmRouterConfig | None = None,
    ) -> None:
        if not adapters:
            raise ValueError("at least one LLM adapter is required")
        self._adapters = adapters
        self._config = config or LlmRouterConfig()
        self._breakers: dict[str, CircuitBreaker] = {
            str(a.provider_kind): CircuitBreaker(
                failure_threshold=self._config.circuit_failure_threshold,
                recovery_seconds=self._config.circuit_recovery_seconds,
            )
            for a in adapters
        }
        self._backoff = ExponentialBackoff()

    def complete(self, request: LlmRequest) -> LlmResponse:
        """Route request through available providers with circuit breaker failover."""

        errors: list[str] = []

        for adapter in self._adapters:
            key = str(adapter.provider_kind)
            breaker = self._breakers[key]

            if not breaker.is_available():
                errors.append(f"{key}: circuit OPEN")
                continue

            for attempt in range(self._config.max_retries_per_provider + 1):
                try:
                    if attempt > 0:
                        delay = self._backoff.delay_seconds(attempt - 1)
                        time.sleep(delay)

                    response = adapter.complete(request)
                    breaker.record_success()
                    return response

                except LlmProviderError as exc:
                    breaker.record_failure()
                    errors.append(f"{key} attempt {attempt}: {exc}")
                    if not exc.retryable:
                        break
                except Exception as exc:
                    breaker.record_failure()
                    errors.append(f"{key} attempt {attempt}: unexpected: {exc}")

        raise LlmProviderError(
            "router",
            f"all providers exhausted. errors: {'; '.join(errors)}",
            retryable=False,
        )

    def circuit_states(self) -> dict[str, CircuitState]:
        return {k: b.state for k, b in self._breakers.items()}


class _SyntheticLlmAdapter:
    """Deterministic synthetic adapter for test environments without real LLM credentials."""

    def __init__(self, provider_kind: LlmProviderKind = LlmProviderKind.OLLAMA) -> None:
        self._provider_kind = provider_kind

    @property
    def provider_kind(self) -> LlmProviderKind:
        return self._provider_kind

    def complete(self, request: LlmRequest) -> LlmResponse:
        return LlmResponse(
            request_id=request.request_id,
            provider_kind=self._provider_kind,
            model_name="synthetic-llm-v1",
            content='{"translated": "Hello World (translated)", "duration_estimate_ms": 1200}',
            input_tokens=len(request.user_prompt.split()),
            output_tokens=10,
            latency_ms=50.0,
        )


__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "LlmAdapter",
    "LlmProviderError",
    "LlmProviderKind",
    "LlmProviderRouter",
    "LlmRequest",
    "LlmResponse",
    "LlmRouterConfig",
    "_SyntheticLlmAdapter",
]
