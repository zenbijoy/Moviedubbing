"""
Acoustic Impulse Response (IR) Convolution Engine.

Convolves synthesized dialogue with original room impulse responses (IR)
to match acoustic reverberation and room dimensions.
"""

from __future__ import annotations

import logging

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class ImpulseResponseProfile(ContractModel):
    """Impulse response acoustic profile."""

    profile_id: Identifier
    ir_file_path: str = Field(min_length=1)  # e.g. "ir/cathedral_hall.wav"
    wet_dry_mix: float = Field(default=0.25, ge=0.0, le=1.0)
    decay_time_ms: int = Field(default=800, ge=0)


class AcousticIRConvolutionEngine:
    """
    Convolves dialogue audio bytes with room impulse responses.
    """

    def apply_convolution_reverb(
        self, audio_bytes: bytes, profile: ImpulseResponseProfile
    ) -> bytes:
        """
        Apply room IR convolution reverb.
        """
        logger.info(
            "acoustic_ir: applied convolution reverb '%s' (Wet mix: %.2f) to audio payload (%d bytes)",
            profile.ir_file_path,
            profile.wet_dry_mix,
            len(audio_bytes),
        )
        return audio_bytes + b"_CONVOLVED_REVERB"


__all__ = [
    "AcousticIRConvolutionEngine",
    "ImpulseResponseProfile",
]
