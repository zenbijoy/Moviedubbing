from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from aidub.benchmarks.models import (
    BenchmarkLanguage,
    ConsentStatus,
    DatasetEvidence,
    EngineModelIdentity,
    MachineFingerprint,
    MetricApplicability,
    ModelBenchmarkEvidence,
    ModelTask,
    PerformanceThresholds,
    QualityMetric,
    QualityMetricName,
    RouteDecision,
    VerificationStatus,
    unmeasured_quality_metrics,
)

HASH = "a" * 64
NOW = datetime(2026, 8, 14, tzinfo=UTC)


def dataset(
    *,
    license_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    license_identifier: str | None = None,
    license_evidence_reference: str | None = None,
    commercial_use_allowed: bool | None = None,
    consent_status: ConsentStatus = ConsentStatus.UNVERIFIED,
    consent_evidence_reference: str | None = None,
) -> DatasetEvidence:
    return DatasetEvidence(
        dataset_id="internal-golden-dialogue",
        dataset_version="fixture-v1",
        manifest_sha256=HASH,
        license_status=license_status,
        license_identifier=license_identifier,
        license_evidence_reference=license_evidence_reference,
        commercial_use_allowed=commercial_use_allowed,
        consent_status=consent_status,
        consent_evidence_reference=consent_evidence_reference,
        territories=("BD", "IN", "US"),
    )


def engine_model() -> EngineModelIdentity:
    return EngineModelIdentity(
        engine_id="synthetic-test-engine",
        engine_version="1.2.3",
        model_id="synthetic-test-model",
        model_version="fixture-v1",
        weight_sha256="b" * 64,
    )


def benchmark_machine() -> MachineFingerprint:
    return MachineFingerprint(
        system="SyntheticOS",
        release="fixture",
        machine="x86_64",
        processor="Synthetic Test CPU",
        pointer_bits=64,
        python_implementation="CPython",
        python_version="3.12.10",
        logical_cpu_count=8,
    )


def test_machine_fingerprint_is_stable_and_excludes_direct_device_identifiers() -> None:
    left = MachineFingerprint(
        system="Windows",
        release="11",
        machine="AMD64",
        processor="Example CPU",
        pointer_bits=64,
        python_implementation="CPython",
        python_version="3.12.10",
        logical_cpu_count=16,
    )
    right = MachineFingerprint(
        logical_cpu_count=16,
        python_version="3.12.10",
        python_implementation="CPython",
        pointer_bits=64,
        processor="Example CPU",
        machine="AMD64",
        release="11",
        system="Windows",
    )

    assert left.fingerprint_sha256 == right.fingerprint_sha256
    assert len(left.fingerprint_sha256) == 64
    assert "hostname" not in left.to_dict()
    assert "username" not in left.to_dict()
    assert "mac_address" not in left.to_dict()


def test_thresholds_require_explicit_consistent_positive_gate_values() -> None:
    with pytest.raises(ValueError, match="at least one"):
        PerformanceThresholds()
    with pytest.raises(ValueError, match="positive"):
        PerformanceThresholds(max_median_ms=0)
    with pytest.raises(ValueError, match="cannot be lower"):
        PerformanceThresholds(max_median_ms=10, max_p95_ms=5)


def test_unmeasured_evidence_captures_all_metrics_and_invents_no_values() -> None:
    metrics = unmeasured_quality_metrics("Benchmark execution is pending")
    evidence = ModelBenchmarkEvidence(
        evidence_id="evidence_asr_bn_pending",
        task=ModelTask.ASR,
        language=BenchmarkLanguage.BENGALI_BANGLADESH,
        dataset=dataset(),
        engine_model=engine_model(),
        metrics=metrics,
    )

    assert {metric.name for metric in metrics} == set(QualityMetricName)
    assert all(metric.value is None for metric in metrics)
    assert not evidence.production_eligible
    payload = json.loads(evidence.to_json())
    assert payload["language"] == "bn-BD"
    assert payload["decision"] == "unverified"
    assert payload["dataset"]["production_eligible"] is False
    assert all(metric["value"] is None for metric in payload["metrics"])


def test_metric_applicability_requires_value_or_explanation() -> None:
    with pytest.raises(ValueError, match="requires value"):
        QualityMetric(
            name=QualityMetricName.WER,
            applicability=MetricApplicability.APPLICABLE,
        )
    with pytest.raises(ValueError, match="cannot carry"):
        QualityMetric(
            name=QualityMetricName.WER,
            applicability=MetricApplicability.NOT_APPLICABLE,
            value=0.1,
            sample_count=10,
            notes="Not an ASR route",
        )
    with pytest.raises(ValueError, match="MOS"):
        QualityMetric(
            name=QualityMetricName.MOS,
            applicability=MetricApplicability.APPLICABLE,
            value=5.1,
            sample_count=20,
        )


def test_evidence_requires_exactly_one_applicability_record_per_metric() -> None:
    metrics = unmeasured_quality_metrics("Pending")
    with pytest.raises(ValueError, match="every quality metric"):
        ModelBenchmarkEvidence(
            evidence_id="evidence_incomplete",
            task=ModelTask.VOICE,
            language=BenchmarkLanguage.HINDI_INDIA,
            dataset=dataset(),
            engine_model=engine_model(),
            metrics=metrics[:-1],
        )
    with pytest.raises(ValueError, match="unique"):
        ModelBenchmarkEvidence(
            evidence_id="evidence_duplicate",
            task=ModelTask.VOICE,
            language=BenchmarkLanguage.HINDI_INDIA,
            dataset=dataset(),
            engine_model=engine_model(),
            metrics=(*metrics[:-1], metrics[0]),
        )


def test_approval_requires_verified_rights_measured_evidence_and_approver() -> None:
    metrics = tuple(
        QualityMetric(
            name=name,
            applicability=(
                MetricApplicability.APPLICABLE
                if name is QualityMetricName.WER
                else MetricApplicability.NOT_APPLICABLE
            ),
            value=0.12 if name is QualityMetricName.WER else None,
            sample_count=100 if name is QualityMetricName.WER else None,
            notes="Synthetic unit-test evidence" if name is not QualityMetricName.WER else "",
        )
        for name in QualityMetricName
    )

    with pytest.raises(ValueError, match="machine fingerprint"):
        ModelBenchmarkEvidence(
            evidence_id="evidence_missing_machine",
            task=ModelTask.ASR,
            language=BenchmarkLanguage.ENGLISH,
            dataset=dataset(),
            engine_model=engine_model(),
            metrics=metrics,
            measured_at=NOW,
        )

    with pytest.raises(ValueError, match="production-eligible dataset rights"):
        ModelBenchmarkEvidence(
            evidence_id="evidence_blocked_rights",
            task=ModelTask.ASR,
            language=BenchmarkLanguage.ENGLISH,
            dataset=dataset(),
            engine_model=engine_model(),
            metrics=metrics,
            machine=benchmark_machine(),
            measured_at=NOW,
            decision=RouteDecision.APPROVED,
            decision_reason="Synthetic approval path test",
            approved_by="model-governance@example.test",
            approved_at=NOW,
        )

    verified_dataset = dataset(
        license_status=VerificationStatus.VERIFIED,
        license_identifier="LicenseRef-Internal-Test",
        license_evidence_reference="rights/dataset-license-review.json",
        commercial_use_allowed=True,
        consent_status=ConsentStatus.VERIFIED,
        consent_evidence_reference="rights/participant-consent-ledger.json",
    )
    approved = ModelBenchmarkEvidence(
        evidence_id="evidence_synthetic_approved",
        task=ModelTask.ASR,
        language=BenchmarkLanguage.ENGLISH,
        dataset=verified_dataset,
        engine_model=engine_model(),
        metrics=metrics,
        machine=benchmark_machine(),
        measured_at=NOW,
        decision=RouteDecision.APPROVED,
        decision_reason="Synthetic unit-test approval; not a product result",
        approved_by="model-governance@example.test",
        approved_at=NOW,
    )

    assert approved.production_eligible


def test_verified_license_and_consent_require_evidence() -> None:
    with pytest.raises(ValueError, match="identifier and evidence"):
        dataset(license_status=VerificationStatus.VERIFIED, commercial_use_allowed=True)
    with pytest.raises(ValueError, match="consent requires evidence"):
        dataset(consent_status=ConsentStatus.VERIFIED)
