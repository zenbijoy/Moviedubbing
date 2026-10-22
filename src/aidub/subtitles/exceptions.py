"""Subtitle exceptions hierarchy."""

from __future__ import annotations


class SubtitleError(Exception):
    """Base exception for all subtitle operations."""


class SubtitleImportError(SubtitleError):
    """Raised when subtitle file cannot be imported."""


class SubtitleEncodingError(SubtitleImportError):
    """Raised when subtitle encoding cannot be decoded safely."""


class SubtitleParseError(SubtitleImportError):
    """Raised when subtitle format parsing encounters fatal structure errors."""


class SubtitleValidationError(SubtitleError):
    """Raised when subtitle validation fails critical threshold constraints."""


__all__ = [
    "SubtitleEncodingError",
    "SubtitleError",
    "SubtitleImportError",
    "SubtitleParseError",
    "SubtitleValidationError",
]
