"""Unit tests for ModelManager and VramScheduler (Task 1.5)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aidub.infrastructure.models.manager import (
    ModelDescriptor,
    ModelIntegrityError,
    ModelKind,
    ModelManager,
    ModelStatus,
)
from aidub.orchestration.vram_scheduler import (
    GpuTier,
    VramBudgetExceededError,
    VramScheduler,
    VramSchedulerPolicy,
)


def _make_descriptor(
    model_id: str,
    cache_path: str,
    vram_mb: int = 2_048,
    priority: int = 10,
) -> ModelDescriptor:
    fake_sha = "a" * 64
    return ModelDescriptor(
        model_id=model_id,
        model_kind=ModelKind.ASR,
        version="1.0.0",
        weights_sha256=fake_sha,
        vram_mb=vram_mb,
        ram_mb=1_024,
        cache_path=cache_path,
        load_priority=priority,
    )


def test_model_manager_register_and_verify(tmp_path: Path) -> None:
    weight_file = tmp_path / "model.bin"
    weight_bytes = b"fake_model_weights"
    sha = hashlib.sha256(weight_bytes).hexdigest()
    weight_file.write_bytes(weight_bytes)

    descriptor = ModelDescriptor(
        model_id="asr-whisper-large",
        model_kind=ModelKind.ASR,
        version="1.0.0",
        weights_sha256=sha,
        vram_mb=4_096,
        ram_mb=2_048,
        cache_path=str(weight_file),
    )

    manager = ModelManager()
    manager.register(descriptor)
    assert manager.get_entry("asr-whisper-large") is not None

    verified = manager.verify("asr-whisper-large")
    assert verified is True
    entry = manager.get_entry("asr-whisper-large")
    assert entry is not None
    assert entry.verified is True
    assert entry.status == ModelStatus.CACHED


def test_model_manager_verify_wrong_hash(tmp_path: Path) -> None:
    weight_file = tmp_path / "model.bin"
    weight_file.write_bytes(b"wrong_data")

    descriptor = ModelDescriptor(
        model_id="bad-model",
        model_kind=ModelKind.TTS,
        version="1.0.0",
        weights_sha256="a" * 64,  # does NOT match file
        vram_mb=1_024,
        ram_mb=512,
        cache_path=str(weight_file),
    )

    manager = ModelManager()
    manager.register(descriptor)
    verified = manager.verify("bad-model")
    assert verified is False


def test_model_manager_load_requires_verify(tmp_path: Path) -> None:
    descriptor = _make_descriptor("mymodel", str(tmp_path / "model.bin"))
    manager = ModelManager()
    manager.register(descriptor)

    with pytest.raises(ModelIntegrityError):
        manager.load("mymodel")


def test_model_manager_load_and_unload(tmp_path: Path) -> None:
    weight_file = tmp_path / "model.bin"
    data = b"real_model_data"
    sha = hashlib.sha256(data).hexdigest()
    weight_file.write_bytes(data)

    descriptor = ModelDescriptor(
        model_id="tts-model",
        model_kind=ModelKind.TTS,
        version="2.0.0",
        weights_sha256=sha,
        vram_mb=3_000,
        ram_mb=1_500,
        cache_path=str(weight_file),
    )
    manager = ModelManager()
    manager.register(descriptor)
    manager.verify("tts-model")
    manager.load("tts-model")

    assert manager.registered_vram_mb() == 3_000
    assert len(manager.loaded_models()) == 1

    manager.unload("tts-model")
    assert manager.registered_vram_mb() == 0
    assert len(manager.loaded_models()) == 0


def test_vram_scheduler_can_load(tmp_path: Path) -> None:
    manager = ModelManager()
    policy = VramSchedulerPolicy(gpu_tier=GpuTier.TIER_8GB, safety_margin_mb=512)
    scheduler = VramScheduler(manager, policy)

    # Available = 8192 - 512 = 7680 MB
    assert scheduler.available_vram_mb() == 7_680

    descriptor = _make_descriptor("asr", str(tmp_path / "m.bin"), vram_mb=4_000)
    manager.register(descriptor)
    assert scheduler.can_load(descriptor) is True


def test_vram_scheduler_evict_lower_priority(tmp_path: Path) -> None:
    """Scheduler evicts low-priority loaded models to make room for higher-priority one."""
    import hashlib

    manager = ModelManager()
    policy = VramSchedulerPolicy(gpu_tier=GpuTier.TIER_8GB, safety_margin_mb=0)
    scheduler = VramScheduler(manager, policy)

    # Load a low-priority model (4GB)
    data_a = b"model_a"
    sha_a = hashlib.sha256(data_a).hexdigest()
    file_a = tmp_path / "model_a.bin"
    file_a.write_bytes(data_a)
    desc_a = ModelDescriptor(
        model_id="low-priority",
        model_kind=ModelKind.SEPARATION,
        version="1.0.0",
        weights_sha256=sha_a,
        vram_mb=4_096,
        ram_mb=0,
        cache_path=str(file_a),
        load_priority=5,
    )
    manager.register(desc_a)
    manager.verify("low-priority")
    manager.load("low-priority")
    assert manager.registered_vram_mb() == 4_096

    # Now schedule a high-priority model (6GB) — needs eviction of low-priority model
    data_b = b"model_b"
    sha_b = hashlib.sha256(data_b).hexdigest()
    file_b = tmp_path / "model_b.bin"
    file_b.write_bytes(data_b)
    desc_b = ModelDescriptor(
        model_id="high-priority",
        model_kind=ModelKind.ASR,
        version="1.0.0",
        weights_sha256=sha_b,
        vram_mb=6_000,
        ram_mb=0,
        cache_path=str(file_b),
        load_priority=90,
    )
    manager.register(desc_b)
    manager.verify("high-priority")
    result = scheduler.schedule_load("high-priority", evict_if_needed=True)

    assert result.model_id == "high-priority"
    assert manager.registered_vram_mb() == 6_000


def test_vram_scheduler_raises_when_budget_exceeded(tmp_path: Path) -> None:
    manager = ModelManager()
    policy = VramSchedulerPolicy(gpu_tier=GpuTier.TIER_8GB, safety_margin_mb=0)
    scheduler = VramScheduler(manager, policy)

    file = tmp_path / "huge.bin"
    data = b"huge_model"
    file.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()

    desc = ModelDescriptor(
        model_id="giant-model",
        model_kind=ModelKind.LIP_SYNC,
        version="1.0.0",
        weights_sha256=sha,
        vram_mb=12_000,  # exceeds 8GB budget
        ram_mb=0,
        cache_path=str(file),
        load_priority=50,
    )
    manager.register(desc)
    manager.verify("giant-model")

    with pytest.raises(VramBudgetExceededError):
        scheduler.schedule_load("giant-model", evict_if_needed=False)
