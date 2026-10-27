"""Unit tests for VoiceEngineRegistry, hardware inspection, and fallback resolution."""

from __future__ import annotations

from aidub.adapters.voice.engine_registry import (
    VoiceEngineRegistry,
    get_disk_free_gb,
    get_gpu_info,
    get_system_ram_gb,
    get_voice_engine_registry,
)
from aidub.adapters.voice_base import (
    EngineCapability,
    SyntheticVoiceEngine,
    VoiceEngineKind,
)


def test_registry_singleton_initialization() -> None:
    reg1 = get_voice_engine_registry()
    reg2 = get_voice_engine_registry()
    assert reg1 is reg2
    assert len(reg1.list_registered_engines()) >= 8


def test_registry_engine_instantiation_and_metadata() -> None:
    registry = VoiceEngineRegistry()
    engines = registry.list_registered_engines()

    assert VoiceEngineKind.SYNTHETIC in engines
    assert VoiceEngineKind.EDGE_TTS in engines
    assert VoiceEngineKind.GEMINI_TTS in engines
    assert VoiceEngineKind.ELEVENLABS in engines
    assert VoiceEngineKind.F5_TTS in engines
    assert VoiceEngineKind.COSYVOICE in engines
    assert VoiceEngineKind.OPENVOICE in engines
    assert VoiceEngineKind.QWEN3_TTS in engines

    synth = registry.get_engine(VoiceEngineKind.SYNTHETIC)
    assert isinstance(synth, SyntheticVoiceEngine)
    assert synth.metadata.license_info == "MIT"
    assert synth.metadata.commercial_use_allowed is True
    assert EngineCapability.TEXT_TO_SPEECH in synth.metadata.capabilities


def test_registry_hardware_inspection() -> None:
    total_ram, avail_ram = get_system_ram_gb()
    assert total_ram > 0.0
    assert avail_ram > 0.0

    gpu_info = get_gpu_info()
    assert "cuda_available" in gpu_info
    assert "device_name" in gpu_info

    disk_free = get_disk_free_gb()
    assert disk_free > 0.0

    registry = VoiceEngineRegistry()
    hw = registry.inspect_hardware()
    assert hw["ram_total_gb"] == total_ram
    assert hw["disk_free_gb"] == disk_free


def test_registry_unload_engine() -> None:
    registry = VoiceEngineRegistry()
    # Instantiate engine
    _ = registry.get_engine(VoiceEngineKind.SYNTHETIC)
    hw = registry.inspect_hardware()
    assert "synthetic" in hw["active_models_loaded"]

    registry.unload_engine(VoiceEngineKind.SYNTHETIC)
    hw_after = registry.inspect_hardware()
    assert "synthetic" not in hw_after["active_models_loaded"]


def test_registry_fallback_resolution_for_tts() -> None:
    registry = VoiceEngineRegistry()
    # When requesting an unavailable engine (e.g. Qwen3-TTS without local endpoint),
    # it must fall back gracefully to ready TTS (Edge-TTS or Synthetic) with warnings
    resolved_engine, warnings = registry.resolve_effective_engine(
        VoiceEngineKind.QWEN3_TTS,
        required_capabilities={EngineCapability.TEXT_TO_SPEECH},
    )
    assert resolved_engine is not None
    assert resolved_engine.engine_kind in {VoiceEngineKind.EDGE_TTS, VoiceEngineKind.SYNTHETIC}
    assert len(warnings) > 0


def test_registry_fallback_resolution_for_voice_cloning() -> None:
    registry = VoiceEngineRegistry()
    # When reference audio cloning is required, it routes to ElevenLabs (if configured)
    # or Synthetic engine
    resolved_engine, warnings = registry.resolve_effective_engine(
        VoiceEngineKind.COSYVOICE,
        required_capabilities={EngineCapability.REFERENCE_AUDIO_CLONING},
    )
    assert resolved_engine is not None
    assert resolved_engine.engine_kind in {VoiceEngineKind.ELEVENLABS, VoiceEngineKind.SYNTHETIC}
    assert len(warnings) > 0
