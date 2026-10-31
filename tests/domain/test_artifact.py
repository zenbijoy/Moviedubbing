from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aidub.domain.artifact import (
    Artifact,
    ArtifactProvenance,
    ArtifactStatus,
    ArtifactType,
    ReproducibilityLevel,
)

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)
SOURCE_HASH = "a" * 64
OUTPUT_HASH = "b" * 64
WEIGHT_HASH = "c" * 64


def provenance(**updates: object) -> ArtifactProvenance:
    values: dict[str, object] = {
        "source_artifact_hashes": (SOURCE_HASH,),
        "engine_id": "faster-whisper-adapter",
        "engine_version": "1.2.3",
        "engine_abi": "asr.v1",
        "model_id": "whisper-large-v3",
        "model_version": "2026-06-01",
        "weight_sha256": WEIGHT_HASH,
        "code_version": "git:0123456789abcdef",
        "normalized_settings": {"beam_size": 5, "language": "en"},
        "seed": 42,
        "hardware": "NVIDIA RTX 4090",
        "precision": "float16",
        "reproducibility": ReproducibilityLevel.EXACT,
    }
    values.update(updates)
    return ArtifactProvenance.model_validate(values)


def artifact(**updates: object) -> Artifact:
    values: dict[str, object] = {
        "artifact_id": "art_transcript_01",
        "project_id": "prj_feature_film",
        "artifact_type": ArtifactType.TRANSCRIPT,
        "relative_path": f"artifacts/sha256/bb/{OUTPUT_HASH}.json",
        "sha256": OUTPUT_HASH,
        "byte_length": 1_024,
        "provenance": provenance(),
        "created_at": NOW,
    }
    values.update(updates)
    return Artifact.model_validate(values)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.bin",
        "artifacts/../outside.bin",
        "/absolute/file.bin",
        "C:/absolute/file.bin",
        r"artifacts\windows\file.bin",
        "./artifacts/file.bin",
    ],
)
def test_artifact_path_must_be_normalized_project_relative_posix(path: str) -> None:
    with pytest.raises(ValidationError, match="artifact path"):
        artifact(relative_path=path)


def test_artifact_cannot_depend_on_itself_or_duplicate_inputs() -> None:
    with pytest.raises(ValidationError, match="depend on itself"):
        artifact(source_artifact_ids=("art_transcript_01",))
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        artifact(source_artifact_ids=("art_source_001", "art_source_001"))


def test_artifact_publication_requires_ordered_verification_and_publication() -> None:
    verified = NOW + timedelta(seconds=1)
    published = NOW + timedelta(seconds=2)
    completed = artifact(
        status=ArtifactStatus.PUBLISHED,
        verified_at=verified,
        published_at=published,
    )

    assert completed.status is ArtifactStatus.PUBLISHED

    with pytest.raises(ValidationError, match="requires verification"):
        artifact(status=ArtifactStatus.PUBLISHED, published_at=published)
    with pytest.raises(ValidationError, match="cannot precede verification"):
        artifact(
            status=ArtifactStatus.PUBLISHED,
            verified_at=published,
            published_at=verified,
        )


def test_exact_engine_provenance_requires_versioned_abi() -> None:
    with pytest.raises(ValidationError, match="version and ABI"):
        provenance(engine_version=None, engine_abi=None)


def test_cache_key_is_canonical_and_excludes_hardware_and_quality_observations() -> None:
    left = provenance(
        normalized_settings={"language": "en", "beam_size": 5},
        hardware="GPU-A",
        quality_metrics={"wer": 0.03},
    )
    right = provenance(
        normalized_settings={"beam_size": 5, "language": "en"},
        hardware="GPU-B",
        quality_metrics={"wer": 0.99},
    )

    assert left.cache_key() == right.cache_key()
    assert len(left.cache_key()) == 64
    assert left.cache_key() != provenance(seed=43).cache_key()
    with pytest.raises(TypeError, match="immutable"):
        left.normalized_settings["beam_size"] = 10


def test_hashes_must_be_lowercase_sha256() -> None:
    with pytest.raises(ValidationError):
        artifact(sha256="B" * 64)
    with pytest.raises(ValidationError):
        artifact(sha256="b" * 63)
