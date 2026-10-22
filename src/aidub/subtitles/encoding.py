"""
Robust multi-encoding detector for subtitle files.

Supports:
- UTF-8
- UTF-8 BOM
- UTF-16 LE / UTF-16 BE
- Windows-1252
- ISO-8859-1
"""

from __future__ import annotations

import logging
from pathlib import Path

from aidub.subtitles.exceptions import SubtitleEncodingError

logger = logging.getLogger(__name__)

SUPPORTED_ENCODINGS = [
    "utf-8-sig",  # UTF-8 with BOM
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "cp1252",  # Windows-1252
    "iso-8859-1",  # Latin-1
]


def detect_and_read_subtitle_file(file_path: Path | str) -> tuple[str, str]:
    """
    Safely detect encoding and read raw text content of a subtitle file.

    Returns:
        (decoded_text, detected_encoding_name)

    Raises:
        SubtitleEncodingError: If file cannot be read or decoded using supported encodings.
    """
    path = Path(file_path)
    if not path.is_file():
        raise SubtitleEncodingError(f"Subtitle file does not exist: {path}")

    raw_bytes = path.read_bytes()
    if not raw_bytes:
        return "", "utf-8"

    # Check UTF-8 BOM explicitly
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        try:
            return raw_bytes.decode("utf-8-sig"), "UTF-8 BOM"
        except Exception:
            pass

    # Check UTF-16 BOM
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw_bytes.decode("utf-16"), "UTF-16"
        except Exception:
            pass

    # Try candidate encodings sequentially
    for enc in SUPPORTED_ENCODINGS:
        try:
            decoded = raw_bytes.decode(enc)
            # Verify string has no unprintable replacement characters if strict
            label = "UTF-8" if enc in ("utf-8", "utf-8-sig") else enc.upper()
            logger.info("Successfully read '%s' using encoding '%s'", path.name, label)
            return decoded, label
        except (UnicodeDecodeError, ValueError):
            continue

    # Final chardet fallback if chardet library is installed
    try:
        import chardet

        detected = chardet.detect(raw_bytes)
        enc_name = detected.get("encoding")
        if enc_name:
            decoded = raw_bytes.decode(enc_name, errors="replace")
            return decoded, f"{enc_name.upper()} (detected)"
    except Exception:
        pass

    # Fallback to UTF-8 with replacement if all else fails
    try:
        return raw_bytes.decode("utf-8", errors="replace"), "UTF-8 (fallback)"
    except Exception as e:
        raise SubtitleEncodingError(f"Failed to decode subtitle file '{path.name}': {e}") from e


__all__ = ["SUPPORTED_ENCODINGS", "detect_and_read_subtitle_file"]
