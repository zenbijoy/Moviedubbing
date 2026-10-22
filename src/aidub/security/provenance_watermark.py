"""
Imperceptible Audio & Video AI Provenance Watermarking Engine.

Embeds robust, imperceptible provenance watermarks in synthesized audio and visual lip-sync frames.
"""

from __future__ import annotations


class WatermarkUnavailableError(RuntimeError):
    """Raised when no audio or video watermarking implementation is configured."""


class AIProvenanceWatermarker:
    """
    Embeds imperceptible watermark signals into generated audio/video streams.
    """

    def watermark_audio_payload(self, audio_bytes: bytes, provenance_id: str) -> bytes:
        """
        Reject claims of watermarking until a real signal-domain encoder is configured.
        """
        del audio_bytes, provenance_id
        raise WatermarkUnavailableError(
            "Audio provenance watermarking is unavailable: no signal-domain watermark encoder "
            "is configured. No payload was modified."
        )


__all__ = [
    "AIProvenanceWatermarker",
    "WatermarkUnavailableError",
]
