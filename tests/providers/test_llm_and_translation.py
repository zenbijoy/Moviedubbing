"""Unit tests for LLM Router, Validator, Translation Pipeline, Glossary, and Privacy (Tasks 2.1-2.5)."""

from __future__ import annotations

import json

import pytest

from aidub.application.glossary_service import GlossaryService
from aidub.application.translation_pipeline import (
    DialogueLine,
    TranslationContext,
    TranslationPass,
    TranslationPipeline,
    TranslationPipelineConfig,
)
from aidub.contracts.base import Identifier
from aidub.domain.character_bible import (
    CharacterBibleEntry,
    GlossaryTerm,
    ProjectCharacterBible,
    SpeechRegister,
)
from aidub.infrastructure.logging import (
    PrivateStudioGuard,
    PrivateStudioViolation,
    RedactionFilter,
)
from aidub.providers.router import (
    CircuitState,
    LlmProviderError,
    LlmProviderKind,
    LlmProviderRouter,
    LlmRequest,
    LlmResponse,
    LlmRouterConfig,
    _SyntheticLlmAdapter,
)
from aidub.providers.schemas import TranslationResult
from aidub.providers.validator import LlmResponseValidator, ValidationRepairError
from aidub.security.privacy import DataClass, NetworkPolicy, PrivacyPolicy

# ── Task 2.1: LLM Router ─────────────────────────────────────────────────────


def test_llm_router_synthetic_complete() -> None:
    adapter = _SyntheticLlmAdapter(LlmProviderKind.OLLAMA)
    router = LlmProviderRouter([adapter])
    request = LlmRequest(
        request_id=Identifier("req-001"),
        user_prompt="Translate: Hello World",
    )
    response = router.complete(request)
    assert response.provider_kind == LlmProviderKind.OLLAMA
    assert len(response.content) > 0


def test_llm_router_failover_on_error() -> None:
    """Router falls over to second adapter when first raises LlmProviderError."""

    class FailingAdapter:
        @property
        def provider_kind(self) -> LlmProviderKind:
            return LlmProviderKind.OPENAI

        def complete(self, request: LlmRequest) -> LlmResponse:
            raise LlmProviderError("openai", "timeout", retryable=True)

    fallback = _SyntheticLlmAdapter(LlmProviderKind.OLLAMA)
    router = LlmProviderRouter(
        [FailingAdapter(), fallback],
        config=LlmRouterConfig(max_retries_per_provider=1),
    )
    request = LlmRequest(request_id=Identifier("req-002"), user_prompt="Hello")
    response = router.complete(request)
    assert response.provider_kind == LlmProviderKind.OLLAMA


def test_llm_router_circuit_breaker_opens() -> None:
    """Circuit breaker trips after repeated failures."""

    fail_count = [0]

    class AlwaysFailingAdapter:
        @property
        def provider_kind(self) -> LlmProviderKind:
            return LlmProviderKind.DEEPSEEK

        def complete(self, request: LlmRequest) -> LlmResponse:
            fail_count[0] += 1
            raise LlmProviderError("deepseek", "error", retryable=False)

    router = LlmProviderRouter(
        [AlwaysFailingAdapter()],
        config=LlmRouterConfig(
            max_retries_per_provider=0,
            circuit_failure_threshold=2,
        ),
    )

    for _ in range(3):
        with pytest.raises(LlmProviderError):
            router.complete(LlmRequest(request_id=Identifier("x"), user_prompt="test"))

    states = router.circuit_states()
    assert states["deepseek"] == CircuitState.OPEN


def test_llm_router_all_providers_exhausted_raises() -> None:
    import time

    router = LlmProviderRouter(
        [_SyntheticLlmAdapter()],
    )
    # Force circuit open — set opened_at to NOW so recovery window hasn't elapsed
    router._breakers["ollama"]._failure_count = 10
    router._breakers["ollama"]._state = CircuitState.OPEN
    router._breakers["ollama"]._opened_at = time.monotonic()  # just opened, won't recover yet

    with pytest.raises(LlmProviderError) as exc_info:
        router.complete(LlmRequest(request_id=Identifier("y"), user_prompt="test"))
    assert "exhausted" in str(exc_info.value).lower()


# ── Task 2.2: Validator ───────────────────────────────────────────────────────


def test_validator_valid_json() -> None:
    adapter = _SyntheticLlmAdapter()
    validator = LlmResponseValidator(adapter)

    valid_json = json.dumps(
        {
            "source_text": "Hello",
            "translated_text": "হ্যালো",
            "target_language": "bn-BD",
            "duration_estimate_ms": 800,
            "confidence": 0.95,
        }
    )

    result = validator.validate_or_repair(
        valid_json, TranslationResult, request_id=Identifier("req-003")
    )
    assert result.translated_text == "হ্যালো"


def test_validator_markdown_json_fence() -> None:
    adapter = _SyntheticLlmAdapter()
    validator = LlmResponseValidator(adapter)

    fenced = '```json\n{"source_text": "Hi", "translated_text": "হাই", "target_language": "bn-BD", "duration_estimate_ms": 400, "confidence": 0.9}\n```'
    result = validator.validate_or_repair(
        fenced, TranslationResult, request_id=Identifier("req-004")
    )
    assert result.translated_text == "হাই"


def test_validator_triggers_repair_on_malformed() -> None:
    """Malformed JSON triggers synthetic repair loop and eventually fails gracefully."""
    adapter = _SyntheticLlmAdapter()
    validator = LlmResponseValidator(adapter)

    # The synthetic adapter returns a JSON blob — but it has wrong fields for TranslationResult
    # So repair will be attempted. After MAX_REPAIR_ATTEMPTS it raises ValidationRepairError.
    with pytest.raises(ValidationRepairError):
        validator.validate_or_repair(
            "NOT_JSON_AT_ALL ☒",
            TranslationResult,
            request_id=Identifier("req-005"),
        )


# ── Task 2.3: Translation Pipeline ───────────────────────────────────────────


def test_translation_pipeline_runs_all_passes() -> None:
    adapter = _SyntheticLlmAdapter()
    router = LlmProviderRouter([adapter])
    pipeline = TranslationPipeline(router)

    line = DialogueLine(
        utterance_id=Identifier("utt-001"),
        text="Hello, how are you?",
        speaker_id=Identifier("spk-001"),
        duration_ms=2_000,
    )
    ctx = TranslationContext(
        source_language="en-US",
        target_language="bn-BD",
        scene_summary="Morning greeting scene.",
    )

    result = pipeline.translate(line, ctx)

    assert result.utterance_id == "utt-001"
    assert result.target_language == "bn-BD"
    assert len(result.passes_completed) > 0


def test_translation_pipeline_single_pass() -> None:
    adapter = _SyntheticLlmAdapter()
    router = LlmProviderRouter([adapter])
    pipeline = TranslationPipeline(
        router,
        config=TranslationPipelineConfig(enabled_passes=[TranslationPass.SEMANTIC_DRAFT]),
    )

    line = DialogueLine(
        utterance_id=Identifier("utt-002"),
        text="Good morning!",
        speaker_id=Identifier("spk-002"),
        duration_ms=1_200,
    )
    ctx = TranslationContext(source_language="en-US", target_language="hi-IN")
    result = pipeline.translate(line, ctx)

    assert TranslationPass.SEMANTIC_DRAFT.value in " ".join(result.passes_completed)


# ── Task 2.4: Glossary & Character Bible ─────────────────────────────────────


def test_glossary_service_term_enforcement() -> None:
    bible = ProjectCharacterBible(project_id=Identifier("proj-001"))
    service = GlossaryService(bible)

    service.add_term(
        GlossaryTerm(
            term_id=Identifier("term-001"),
            source_term="Doctor Strange",
            target_term="ডক্টর স্ট্রেঞ্জ",
            source_language="en-US",
            target_language="bn-BD",
        )
    )

    result = service.enforce_glossary(
        "Doctor Strange is here",
        source_language="en-US",
        target_language="bn-BD",
    )
    assert "ডক্টর স্ট্রেঞ্জ" in result


def test_glossary_service_character_localized_name() -> None:
    bible = ProjectCharacterBible(project_id=Identifier("proj-002"))
    service = GlossaryService(bible)
    service.add_character(
        CharacterBibleEntry(
            character_id=Identifier("char-001"),
            name="Tony Stark",
            localized_name="টনি স্টার্ক",
            speech_register=SpeechRegister.INFORMAL,
        )
    )

    assert service.localized_character_name("char-001") == "টনি স্টার্ক"
    assert service.localized_character_name("char-999", fallback="Unknown") == "Unknown"


def test_glossary_service_phonetic_override() -> None:
    bible = ProjectCharacterBible(project_id=Identifier("proj-003"))
    service = GlossaryService(bible)
    service.add_character(
        CharacterBibleEntry(
            character_id=Identifier("char-002"),
            name="Thor",
            pronunciation_phonetic="θɔːr",
        )
    )
    assert service.phonetic_pronunciation("char-002") == "θɔːr"
    assert service.phonetic_pronunciation("char-999") is None


def test_glossary_service_duplicate_term_raises() -> None:
    bible = ProjectCharacterBible(project_id=Identifier("proj-004"))
    service = GlossaryService(bible)
    term = GlossaryTerm(
        term_id=Identifier("t-dup"),
        source_term="Avengers",
        target_term="অ্যাভেঞ্জার্স",
        source_language="en-US",
        target_language="bn-BD",
    )
    service.add_term(term)
    with pytest.raises(ValueError, match="already exists"):
        service.add_term(term)


# ── Task 2.5: Privacy & Log Redaction ────────────────────────────────────────


def test_private_studio_guard_blocks_network() -> None:
    policy = PrivacyPolicy(
        network=NetworkPolicy.OFFLINE,
        telemetry_enabled=False,
    )
    guard = PrivateStudioGuard(policy)

    with pytest.raises(PrivateStudioViolation, match="Private Studio Mode"):
        guard.require_network_allowed("openai.complete")


def test_private_studio_guard_allows_in_hybrid_mode() -> None:
    policy = PrivacyPolicy(
        network=NetworkPolicy.HYBRID,
        allowed_providers=frozenset(["openai"]),
        allowed_data_classes=frozenset([DataClass.TEXT]),
        telemetry_enabled=False,
    )
    guard = PrivateStudioGuard(policy)
    # Should NOT raise
    guard.require_network_allowed(
        "openai.complete",
        provider_id="openai",
        data_class=DataClass.TEXT,
    )


def test_redaction_filter_strips_api_key() -> None:
    import logging

    log_filter = RedactionFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Sending request with key sk-abcdefghijklmnopqrst123456789012",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record)
    assert "sk-abcdef" not in record.msg
    assert "[API_KEY_REDACTED]" in record.msg


def test_redaction_filter_strips_email() -> None:
    import logging

    log_filter = RedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="User email is user@example.com",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record)
    assert "user@example.com" not in record.msg
    assert "[EMAIL_REDACTED]" in record.msg
