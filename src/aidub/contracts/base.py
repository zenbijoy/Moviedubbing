"""Strict contract primitives.

Contract objects cross process and provider boundaries, so permissive parsing is
dangerous. Unknown fields are rejected and instances are immutable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema


class Identifier(str):
    """Identifier primitive with length and regex constraints."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(
                min_length=1,
                max_length=160,
                pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
            ),
        )


class Sha256(str):
    """Sha256 hash string primitive."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=r"^[a-f0-9]{64}$"),
        )


class LocaleCode(str):
    """BCP47 locale code primitive."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(
                pattern=r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-[A-Z]{2}|-[0-9]{3})?$"
            ),
        )


def utc_now() -> datetime:
    return datetime.now(UTC)


class ContractModel(BaseModel):
    """Base class for serialized, versioned process contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class HealthState(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
