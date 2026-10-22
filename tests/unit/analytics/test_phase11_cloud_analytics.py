"""
Unit tests for Phase 11 — Enterprise Cloud Hybrid Sync, Autonomous Model Fine-Tuning & Multi-Tenant Studio Analytics:
  - Cloud Hybrid Differential Sync Hashing & Queueing
  - Autonomous LoRA Adapter Fine-Tuning Pipeline & Consent Enforcement
  - Studio Analytics Cost-per-Minute Calculations & Budget Alerts
  - Analytics Studio Presentation Controller
"""

from __future__ import annotations

import pytest

from aidub.ai.finetuning.finetune_pipeline import (
    FineTuningConfig,
    FineTuningUnavailableError,
    VoiceAdapterFineTuner,
)
from aidub.analytics.studio_analytics import (
    BudgetAlertStatus,
    StudioAnalyticsPlatform,
)
from aidub.cloud.hybrid_sync import CloudHybridSyncEngine, CloudSyncUnavailableError
from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import CharacterVoiceProfile
from aidub.ui.analytics.controller import AnalyticsStudioController


def test_cloud_hybrid_sync_engine_fails_closed_without_storage_adapter() -> None:
    engine = CloudHybridSyncEngine()
    with pytest.raises(CloudSyncUnavailableError, match="No upload was attempted"):
        engine.create_sync_manifest("proj_sync_01", local_version=2)


def test_voice_adapter_fine_tuner() -> None:
    tuner = VoiceAdapterFineTuner()
    cfg = FineTuningConfig(character_id=Identifier("HERO_01"))

    # Unauthorized profile fine-tuning attempt
    unauth_profile = CharacterVoiceProfile(
        profile_id=Identifier("p1"),
        character_id=Identifier("HERO_01"),
        display_name="Hero",
        consent_authorized=False,
    )
    with pytest.raises(PermissionError, match="authorization consent is missing"):
        tuner.execute_fine_tuning_job("job_ft_01", unauth_profile, cfg)

    # Consent is necessary, but cannot claim a model was trained without a backend.
    auth_profile = unauth_profile.model_copy(update={"consent_authorized": True})
    with pytest.raises(FineTuningUnavailableError, match="No adapter was trained or saved"):
        tuner.execute_fine_tuning_job("job_ft_01", auth_profile, cfg)


def test_studio_analytics_and_budget_alerts() -> None:
    platform = StudioAnalyticsPlatform()

    c1 = platform.compute_project_cost("p1", audio_minutes=100.0, gpu_hours=4.0)
    assert c1.cloud_api_cost_usd == 10.00
    assert c1.local_compute_cost_usd == 6.00
    assert c1.total_cost_usd == 16.00

    # Test Healthy status
    report_healthy = platform.generate_tenant_report("tenant_01", [c1], budget_limit_usd=100.0)
    assert report_healthy.alert_status == BudgetAlertStatus.HEALTHY

    # Test Warning status
    report_warning = platform.generate_tenant_report("tenant_01", [c1], budget_limit_usd=18.0)
    assert report_warning.alert_status == BudgetAlertStatus.WARNING

    # Test Exceeded status
    report_exceeded = platform.generate_tenant_report("tenant_01", [c1], budget_limit_usd=10.0)
    assert report_exceeded.alert_status == BudgetAlertStatus.EXCEEDED


def test_analytics_studio_controller() -> None:
    ctrl = AnalyticsStudioController()
    with pytest.raises(CloudSyncUnavailableError):
        ctrl.sync_project_to_cloud("proj_ctrl")

    profile = CharacterVoiceProfile(
        profile_id=Identifier("p_ctrl"),
        character_id=Identifier("HERO_01"),
        display_name="Hero",
        consent_authorized=True,
    )
    with pytest.raises(FineTuningUnavailableError):
        ctrl.fine_tune_character_voice("job_ctrl", profile)

    platform = StudioAnalyticsPlatform()
    measured_cost = platform.compute_project_cost("proj_ctrl", audio_minutes=12, gpu_hours=0.5)
    analytics_summary = ctrl.fetch_tenant_analytics_summary(
        "tenant_ctrl", [measured_cost], budget_limit_usd=100.0
    )
    assert analytics_summary.total_projects == 1
    assert analytics_summary.alert_status == BudgetAlertStatus.HEALTHY
