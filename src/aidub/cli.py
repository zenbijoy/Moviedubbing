"""Typed command-line boundary for operators, automation, and headless CI (facade).

This module preserves the original import path ``aidub.cli``
by re-exporting all public symbols from sub-modules.
"""

from __future__ import annotations

from ._cli_common import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_RUNTIME_UNAVAILABLE,
    EXIT_USAGE,
    EXIT_VALIDATION_FAILED,
)  # noqa: F401

from ._cli import (
    CliDependencies,
    build_parser,
    main,
)  # noqa: F401

__all__ = [
    "EXIT_FAILURE",
    "EXIT_OK",
    "EXIT_RUNTIME_UNAVAILABLE",
    "EXIT_USAGE",
    "EXIT_VALIDATION_FAILED",
    "CliDependencies",
    "build_parser",
    "main",
]
