"""Pydantic v2 JSON response validation and automated LLM repair-loop."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from aidub.contracts.base import Identifier
from aidub.providers.router import LlmAdapter, LlmProviderError, LlmRequest

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_REPAIR_ATTEMPTS = 3


class ValidationRepairError(RuntimeError):
    """Raised when LLM response cannot be repaired into valid schema after all attempts."""


class LlmResponseValidator:
    """
    Validates and auto-repairs LLM JSON responses against Pydantic v2 schemas.

    If the initial response is malformed or missing required fields, a targeted
    repair prompt is sent to the LLM. Up to MAX_REPAIR_ATTEMPTS are made before
    raising ValidationRepairError.
    """

    def __init__(self, adapter: LlmAdapter) -> None:
        self._adapter = adapter

    def validate_or_repair(
        self,
        raw_content: str,
        schema: type[T],
        *,
        request_id: Identifier,
        repair_context: str = "",
    ) -> T:
        """Parse raw LLM JSON content into schema, triggering repair loop if needed."""

        for attempt in range(MAX_REPAIR_ATTEMPTS):
            try:
                parsed_json = _extract_json(raw_content)
                return schema.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as exc:
                if attempt == MAX_REPAIR_ATTEMPTS - 1:
                    raise ValidationRepairError(
                        f"failed to validate {schema.__name__} after {MAX_REPAIR_ATTEMPTS} attempts: {exc}"
                    ) from exc

                logger.warning(
                    "llm response validation failed (attempt %d/%d): %s — triggering repair",
                    attempt + 1,
                    MAX_REPAIR_ATTEMPTS,
                    exc,
                )

                repair_prompt = _build_repair_prompt(
                    raw_content=raw_content,
                    schema_name=schema.__name__,
                    schema_fields=list(schema.model_fields.keys()),
                    error_message=str(exc),
                    context=repair_context,
                )
                repair_request = LlmRequest(
                    request_id=Identifier(f"{request_id}_repair_{attempt}"),
                    user_prompt=repair_prompt,
                    json_mode=True,
                    temperature=0.1,
                    max_tokens=2_048,
                )
                try:
                    repair_response = self._adapter.complete(repair_request)
                    raw_content = repair_response.content
                except LlmProviderError:
                    continue

        raise ValidationRepairError(f"repair loop exhausted for {schema.__name__}")


def _extract_json(text: str) -> Any:
    """Extract JSON from raw text, stripping markdown code fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        inner = "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
        return json.loads(inner)
    return json.loads(stripped)


def _build_repair_prompt(
    *,
    raw_content: str,
    schema_name: str,
    schema_fields: list[str],
    error_message: str,
    context: str,
) -> str:
    fields_str = ", ".join(f'"{f}"' for f in schema_fields)
    return (
        f"The previous response was invalid JSON or missing required fields.\n"
        f"Schema: {schema_name}\n"
        f"Required fields: [{fields_str}]\n"
        f"Validation error: {error_message}\n"
        f"Context: {context}\n\n"
        f"Previous response:\n{raw_content}\n\n"
        f"Please return ONLY a valid JSON object with all required fields. "
        f"Do not include explanations or markdown formatting."
    )


__all__ = ["LlmResponseValidator", "ValidationRepairError"]
