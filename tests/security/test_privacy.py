import pytest

from aidub.security.privacy import DataClass, NetworkPolicy, PrivacyPolicy


def test_offline_blocks_every_provider() -> None:
    policy = PrivacyPolicy(
        network=NetworkPolicy.OFFLINE,
        allowed_providers=frozenset({"openai"}),
        allowed_data_classes=frozenset({DataClass.TEXT}),
    )
    decision = policy.evaluate(provider_id="openai", data_class=DataClass.TEXT)
    assert not decision.allowed
    with pytest.raises(PermissionError, match="offline"):
        policy.require(provider_id="openai", data_class=DataClass.TEXT)


def test_hybrid_requires_provider_and_data_class() -> None:
    policy = PrivacyPolicy(
        network=NetworkPolicy.HYBRID,
        allowed_providers=frozenset({"openai"}),
        allowed_data_classes=frozenset({DataClass.TEXT}),
    )
    assert policy.evaluate(provider_id="openai", data_class=DataClass.TEXT).allowed
    assert not policy.evaluate(provider_id="openai", data_class=DataClass.VIDEO).allowed
    assert not policy.evaluate(provider_id="unknown", data_class=DataClass.TEXT).allowed
