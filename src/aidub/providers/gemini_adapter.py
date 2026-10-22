"""Google Gemini API adapter (official google-generativeai SDK).

Supports:
  - gemini-2.0-flash        (recommended — fast, cheap, great Bengali)
  - gemini-2.0-flash-thinking (reasoning mode)
  - gemini-1.5-pro          (largest context window)
  - gemini-1.5-flash        (cheapest)

Multimodal support: pass video keyframes + audio clips for
context-aware translation (ctx_translate pipeline stage).

https://ai.google.dev/api/python/google/generativeai
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from aidub.providers.router import (
    LlmProviderError,
    LlmProviderKind,
    LlmRequest,
    LlmResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"

# Gemini safety settings — permissive for film dialogue content
_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


class GeminiAdapter:
    """
    LLM adapter for the official Google Gemini API.

    Uses the ``google-generativeai`` SDK.  Falls back gracefully if the
    package is not installed — raises a clear ``LlmProviderError``.

    Args:
        api_key:    Google AI Studio API key (``AIza…``).
        model:      Gemini model name (e.g. ``gemini-2.0-flash``).
        timeout_s:  Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        api_keys: list[str] | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self._api_keys: list[str] = list(api_keys) if api_keys else ([api_key] if api_key else [])
        self._key_index = 0
        self._api_key = self._api_keys[0] if self._api_keys else api_key
        self._model_name = model
        self._timeout_s = timeout_s
        self._model: Any | None = None  # lazy-init

    def _rotate_key(self) -> bool:
        if len(self._api_keys) <= 1:
            return False
        self._key_index = (self._key_index + 1) % len(self._api_keys)
        self._api_key = self._api_keys[self._key_index]
        self._model = None
        logger.info("Gemini: Rotated to key %d of %d", self._key_index + 1, len(self._api_keys))
        return True

    # ── LlmAdapter protocol ───────────────────────────────────────────────────

    @property
    def provider_kind(self) -> LlmProviderKind:
        return LlmProviderKind.GEMINI

    def complete(self, request: LlmRequest) -> LlmResponse:
        """Send a text chat-completion request to Gemini with automatic key pool rotation."""
        max_attempts = max(1, len(self._api_keys))
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            model = self._get_model()
            contents = _build_contents(request)
            generation_config = _generation_config(request)
            t0 = time.monotonic()
            try:
                response = model.generate_content(
                    contents,
                    generation_config=generation_config,
                    safety_settings=_SAFETY_SETTINGS,
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts - 1 and self._rotate_key():
                    logger.warning(
                        "Gemini attempt %d failed (%s), rotating to next API key...",
                        attempt + 1,
                        exc,
                    )
                    continue
                raise LlmProviderError(
                    "gemini", f"API error: {exc}", retryable=_is_retryable(exc)
                ) from exc
        else:
            raise LlmProviderError("gemini", f"All API keys failed: {last_exc}", retryable=True)

        latency_ms = (time.monotonic() - t0) * 1_000
        content = _extract_text(response)

        if not content:
            raise LlmProviderError("gemini", "empty response", retryable=True)

        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0

        logger.debug(
            "gemini: model=%s tokens=%s/%s latency=%.0fms",
            self._model_name,
            in_tok,
            out_tok,
            latency_ms,
        )

        return LlmResponse(
            request_id=request.request_id,
            provider_kind=LlmProviderKind.GEMINI,
            model_name=self._model_name,
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=round(latency_ms, 1),
        )

    def complete_multimodal(
        self,
        request: LlmRequest,
        *,
        frames: list[Path] | None = None,
        audio_path: Path | None = None,
    ) -> LlmResponse:
        """
        Multimodal Gemini call: combine image frames + audio + text.

        Used by the context-aware translation stage (ctx_translate) to
        give the LLM visual scene context and vocal tone before translating.

        Args:
            request:    Standard LlmRequest (user_prompt = text instructions).
            frames:     List of JPEG/PNG keyframe paths sampled from the video.
            audio_path: Path to a ≤28s audio clip (WAV/MP3) for tone context.
        """
        try:
            import google.generativeai as _genai

            genai: Any = _genai
        except ImportError as exc:
            raise LlmProviderError(
                "gemini",
                "google-generativeai not installed — run: pip install google-generativeai",
                retryable=False,
            ) from exc

        parts: list[Any] = []

        # System instruction embedded as first text part (Gemini doesn't have
        # a separate system role in the multimodal API)
        if request.system_prompt:
            parts.append(request.system_prompt + "\n\n")

        # Attach video keyframes
        for frame_path in frames or []:
            if frame_path.exists():
                img = genai.upload_file(str(frame_path), mime_type="image/jpeg")
                parts.append(img)

        # Attach audio clip
        if audio_path and audio_path.exists():
            suffix = audio_path.suffix.lower()
            mime = {"wav": "audio/wav", "mp3": "audio/mpeg"}.get(suffix[1:], "audio/wav")
            aud = genai.upload_file(str(audio_path), mime_type=mime)
            parts.append(aud)

        # Text instruction last
        parts.append(request.user_prompt)

        model = self._get_model()
        t0 = time.monotonic()
        try:
            response = model.generate_content(
                parts,
                generation_config=_generation_config(request),
                safety_settings=_SAFETY_SETTINGS,
            )
        except Exception as exc:
            raise LlmProviderError(
                "gemini", f"multimodal API error: {exc}", retryable=_is_retryable(exc)
            ) from exc

        latency_ms = (time.monotonic() - t0) * 1_000
        content = _extract_text(response)

        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0

        return LlmResponse(
            request_id=request.request_id,
            provider_kind=LlmProviderKind.GEMINI,
            model_name=self._model_name,
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=round(latency_ms, 1),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                import google.generativeai as _genai

                genai: Any = _genai
            except ImportError as exc:
                raise LlmProviderError(
                    "gemini",
                    "google-generativeai not installed — run: pip install google-generativeai",
                    retryable=False,
                ) from exc
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
        return self._model


# ── Module helpers ────────────────────────────────────────────────────────────


def _build_contents(request: LlmRequest) -> list[dict[str, Any]]:
    """
    Gemini uses a different message format than OpenAI.
    System messages are embedded as the first user turn, followed by a
    model ACK, then the real user message.  This prevents the system
    prompt from being ignored in some Gemini versions.
    """
    parts: list[dict[str, Any]] = []
    if request.system_prompt:
        # Gemini: system role goes in GenerativeModel(system_instruction=…)
        # but for backward compat we add it as first user content
        parts.append({"role": "user", "parts": [request.system_prompt]})
        parts.append({"role": "model", "parts": ["Understood. I will follow those instructions."]})
    parts.append({"role": "user", "parts": [request.user_prompt]})
    return parts


def _generation_config(request: LlmRequest) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "temperature": request.temperature,
        "max_output_tokens": request.max_tokens,
    }
    if request.json_mode:
        cfg["response_mime_type"] = "application/json"
    return cfg


def _extract_text(response: Any) -> str:
    try:
        return str(response.text.strip())
    except Exception:
        # Blocked or empty candidate
        try:
            return str(response.candidates[0].content.parts[0].text.strip())
        except Exception:
            return ""


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(k in msg for k in ("429", "quota", "resource_exhausted", "deadline")):
        return True
    return not any(k in msg for k in ("api_key", "permission", "401", "403"))


__all__ = ["DEFAULT_MODEL", "GeminiAdapter"]
