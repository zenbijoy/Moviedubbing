"""
Autonomous Character Voice LoRA Fine-Tuning Pipeline.

Automates LoRA adapter fine-tuning for recurring movie franchise characters when mined audio reference banks
exceed duration and quality thresholds. Evaluates loss curves and speaker verification scores before deployment.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile


class FineTuningUnavailableError(RuntimeError):
    """Raised when no real voice-model training backend is configured."""


class AdapterStatus(StrEnum):
    QUALIFIED = "qualified"  # Speaker similarity >= 0.88, Loss <= 0.15
    REJECTED = "rejected"  # Quality threshold not met


class FineTuningConfig(ContractModel):
    """Configuration hyper-parameters for LoRA adapter fine-tuning."""

    character_id: Identifier
    lora_rank: int = Field(default=16, gt=0)
    lora_alpha: int = Field(default=32, gt=0)
    learning_rate: float = Field(default=1e-4, gt=0.0)
    max_epochs: int = Field(default=10, gt=0)


class FineTuningReport(ContractModel):
    """Evaluation report for a completed LoRA fine-tuning run."""

    job_id: Identifier
    character_id: Identifier
    final_loss: float = Field(ge=0.0)
    speaker_similarity_score: float = Field(ge=0.0, le=1.0)
    adapter_model_path: str = Field(min_length=1)
    status: AdapterStatus = AdapterStatus.QUALIFIED


class VoiceAdapterFineTuner:
    """
    Automates LoRA adapter training loops for character voice conditioning.
    """

    def execute_fine_tuning_job(
        self, job_id: str, profile: CharacterVoiceProfile, config: FineTuningConfig
    ) -> FineTuningReport:
        """Require consent, then fail closed until a real LoRA trainer is configured."""
        if not profile.consent_authorized:
            raise PermissionError(
                f"Cannot fine-tune voice model for profile '{profile.display_name}': authorization consent is missing"
            )

        raise FineTuningUnavailableError(
            "Voice fine-tuning is unavailable: no LoRA training backend is configured. "
            "No adapter was trained or saved."
        )


__all__ = [
    "AdapterStatus",
    "FineTuningConfig",
    "FineTuningReport",
    "FineTuningUnavailableError",
    "VoiceAdapterFineTuner",
]
