"""5-pass context-aware and duration-constrained translation pipeline."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import LanguageTag
from aidub.providers.router import LlmProviderRouter, LlmRequest
from aidub.providers.schemas import TranslationResult
from aidub.providers.validator import LlmResponseValidator

logger = logging.getLogger(__name__)


class TranslationPass(StrEnum):
    SEMANTIC_DRAFT = "semantic_draft"
    CHARACTER_PERSONALITY = "character_personality"
    CULTURAL_LOCALIZATION = "cultural_localization"
    DURATION_BUDGETING = "duration_budgeting"
    TERMINOLOGY_CHECK = "terminology_check"


class DialogueLine(ContractModel):
    """A single source dialogue line submitted for translation."""

    utterance_id: Identifier
    text: str = Field(min_length=1, max_length=4_000)
    speaker_id: Identifier
    duration_ms: int = Field(ge=0)


class TranslationContext(ContractModel):
    """Contextual data injected into translation prompts."""

    source_language: LanguageTag
    target_language: LanguageTag
    preceding_lines: list[str] = Field(default_factory=list, max_length=5)
    following_lines: list[str] = Field(default_factory=list, max_length=5)
    scene_summary: str = Field(default="", max_length=2_000)
    character_notes: str = Field(default="", max_length=2_000)
    glossary_terms: dict[str, str] = Field(default_factory=dict)
    duration_tolerance_pct: float = Field(default=0.08, ge=0.0, le=0.5)


class TranslationPipelineConfig(ContractModel):
    """Configuration for the 5-pass translation pipeline."""

    enabled_passes: list[TranslationPass] = Field(default_factory=lambda: list(TranslationPass))
    max_duration_delta_pct: float = Field(default=0.08, ge=0.0, le=0.5)


class TranslatedLine(ContractModel):
    """Result of a successfully translated dialogue line."""

    utterance_id: Identifier
    source_text: str
    translated_text: str
    target_language: LanguageTag
    estimated_duration_ms: int = Field(ge=0)
    duration_delta_pct: float
    passes_completed: list[str] = Field(default_factory=list)
    within_tolerance: bool


class TranslationPipeline:
    """
    5-pass context-aware translation pipeline.

    Passes:
      1. Semantic Draft — accurate meaning transfer.
      2. Character Personality Adaptation — tone & register alignment.
      3. Cultural Localization — idioms, references, cultural adaptation.
      4. Spoken Duration Budgeting — estimate spoken duration, trim if needed.
      5. Terminology Check — enforce glossary and character name consistency.
    """

    def __init__(
        self,
        router: LlmProviderRouter,
        config: TranslationPipelineConfig | None = None,
    ) -> None:
        self._router = router
        self._config = config or TranslationPipelineConfig()

    def translate(
        self,
        line: DialogueLine,
        context: TranslationContext,
    ) -> TranslatedLine:
        """Run the multi-pass translation pipeline on a single dialogue line."""

        current_text = line.text
        passes_done: list[str] = []

        for pass_kind in self._config.enabled_passes:
            prompt = self._build_prompt(pass_kind, current_text, line, context)
            request = LlmRequest(
                request_id=Identifier(f"{line.utterance_id}_{pass_kind.value}"),
                user_prompt=prompt,
                json_mode=True,
                temperature=_pass_temperature(pass_kind),
                max_tokens=2_048,
            )

            try:
                response = self._router.complete(request)
                validator = LlmResponseValidator(self._router._adapters[0])
                result = validator.validate_or_repair(
                    response.content,
                    TranslationResult,
                    request_id=Identifier(f"{line.utterance_id}_{pass_kind.value}"),
                    repair_context=f"Pass: {pass_kind.value}, Target: {context.target_language}",
                )
                current_text = result.translated_text
                passes_done.append(pass_kind.value)
            except Exception as exc:
                logger.warning(
                    "translation pass %s failed: %s — using previous text", pass_kind.value, exc
                )
                passes_done.append(f"{pass_kind.value}(failed)")

        # Estimate spoken duration (rough 200ms/word heuristic)
        word_count = len(current_text.split())
        estimated_ms = word_count * 200
        delta_pct = abs(estimated_ms - line.duration_ms) / max(line.duration_ms, 1)
        within_tolerance = delta_pct <= self._config.max_duration_delta_pct

        return TranslatedLine(
            utterance_id=line.utterance_id,
            source_text=line.text,
            translated_text=current_text,
            target_language=context.target_language,
            estimated_duration_ms=estimated_ms,
            duration_delta_pct=round(delta_pct, 4),
            passes_completed=passes_done,
            within_tolerance=within_tolerance,
        )

    def translate_batch(
        self,
        lines: list[DialogueLine],
        context: TranslationContext,
        chunk_size: int = 40,
    ) -> list[TranslatedLine]:
        """
        Translate a batch of dialogue lines in 40-line chunked LLM calls.

        Translates dialogue lines maintaining full conversational context across turns,
        making it significantly faster than per-line calls while preserving scene coherence.
        """
        results: list[TranslatedLine] = []

        for i in range(0, len(lines), chunk_size):
            chunk = lines[i : i + chunk_size]
            numbered = "\n".join(
                f"{j + 1}. [Duration: {line.duration_ms}ms, Budget: {max(2, round(line.duration_ms / 1000.0 * 5.4))} syllables] {line.text}"
                for j, line in enumerate(chunk)
            )

            prompt = (
                f"You are an expert Hollywood ADR dubbing translator localizing film dialogue from {context.source_language} to natural cinematic {context.target_language}.\n"
                f"CRITICAL LIP-SYNC DUBBING RULE: Each translated dialogue line MUST fit the exact spoken duration of the original actor's visual mouth movement.\n"
                f"Match the indicated syllable budget closely so speech starts when the mouth opens and finishes when the mouth closes.\n"
                f"Use natural, emotional, idiomatic spoken dialogue (Dhaka/modern standard for Bengali), never stiff or bookish phrasing.\n\n"
                f"Numbered lines:\n{numbered}\n\n"
                f'Return JSON only: {{"translations": ["line 1 translation", "line 2 translation", ...]}}'
            )

            request = LlmRequest(
                request_id=Identifier(f"batch_trans_{i}"),
                user_prompt=prompt,
                json_mode=True,
                temperature=0.3,
                max_tokens=4_096,
            )

            try:
                response = self._router.complete(request)
                import json

                data = json.loads(response.content)
                translated_texts = data.get("translations", [])

                for j, line in enumerate(chunk):
                    txt = translated_texts[j] if j < len(translated_texts) else line.text
                    # Estimate duration based on Bengali phonetic syllable rate (~185ms/syl)
                    from aidub.media.syllable_alignment import SyllableAlignmentEngine
                    syl_count = SyllableAlignmentEngine.count_syllables(txt, context.target_language)
                    est_ms = round(syl_count * 185)
                    delta_pct = abs(est_ms - line.duration_ms) / max(line.duration_ms, 1)

                    results.append(
                        TranslatedLine(
                            utterance_id=line.utterance_id,
                            source_text=line.text,
                            translated_text=txt,
                            target_language=context.target_language,
                            estimated_duration_ms=est_ms,
                            duration_delta_pct=round(delta_pct, 4),
                            passes_completed=["batch_translation"],
                            within_tolerance=delta_pct <= self._config.max_duration_delta_pct,
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "Batch translation chunk %d failed: %s — falling back to per-line", i, exc
                )
                for line in chunk:
                    results.append(self.translate(line, context))

        return results

    def _build_prompt(
        self,
        pass_kind: TranslationPass,
        current_text: str,
        line: DialogueLine,
        ctx: TranslationContext,
    ) -> str:
        context_block = ""
        if ctx.preceding_lines:
            context_block += "Preceding lines:\n" + "\n".join(ctx.preceding_lines) + "\n\n"
        if ctx.following_lines:
            context_block += "Following lines:\n" + "\n".join(ctx.following_lines) + "\n\n"
        if ctx.scene_summary:
            context_block += f"Scene: {ctx.scene_summary}\n\n"
        if ctx.character_notes:
            context_block += f"Character notes: {ctx.character_notes}\n\n"
        if ctx.glossary_terms:
            glossary = ", ".join(f"{k}={v}" for k, v in ctx.glossary_terms.items())
            context_block += f"Glossary: {glossary}\n\n"

        response_contract = (
            'Return JSON only with this exact shape: {"source_text": "<current text>", '
            '"translated_text": "<localized dialogue>", '
            f'"target_language": "{ctx.target_language}", '
            '"duration_estimate_ms": <integer>, "confidence": <0..1>, '
            '"adaptation_notes": "<brief note>"}'
        )

        pass_instructions = {
            TranslationPass.SEMANTIC_DRAFT: (
                f"Translate the following dialogue from {ctx.source_language} to {ctx.target_language}. "
                f"Prioritize semantic accuracy.\n\n{context_block}"
                f"{response_contract}"
            ),
            TranslationPass.CHARACTER_PERSONALITY: (
                f"Adapt the following translation to match the character voice and register.\n\n{context_block}"
                f"{response_contract}"
            ),
            TranslationPass.CULTURAL_LOCALIZATION: (
                f"Localize idioms and cultural references for {ctx.target_language} audience.\n\n{context_block}"
                f"{response_contract}"
            ),
            TranslationPass.DURATION_BUDGETING: (
                f"The original speech duration is {line.duration_ms}ms. "
                f"Adjust the translation to fit within {ctx.duration_tolerance_pct * 100:.0f}% of this duration.\n\n"
                f"{context_block}"
                f"{response_contract}"
            ),
            TranslationPass.TERMINOLOGY_CHECK: (
                f"Verify glossary consistency. Enforce term substitutions.\n\n{context_block}"
                f"{response_contract}"
            ),
        }

        base = pass_instructions[pass_kind]
        return f"{base}\n\nCurrent text:\n{current_text}"


def _pass_temperature(pass_kind: TranslationPass) -> float:
    temps = {
        TranslationPass.SEMANTIC_DRAFT: 0.2,
        TranslationPass.CHARACTER_PERSONALITY: 0.5,
        TranslationPass.CULTURAL_LOCALIZATION: 0.4,
        TranslationPass.DURATION_BUDGETING: 0.1,
        TranslationPass.TERMINOLOGY_CHECK: 0.0,
    }
    return temps.get(pass_kind, 0.3)


__all__ = [
    "DialogueLine",
    "TranslatedLine",
    "TranslationContext",
    "TranslationPass",
    "TranslationPipeline",
    "TranslationPipelineConfig",
]
