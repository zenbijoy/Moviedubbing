import re

import pytest
from pydantic import ValidationError

from aidub.domain.identifiers import new_id
from aidub.domain.project import Project, ProjectSettings
from aidub.domain.time import RationalRate, RationalTime


def test_new_id_uses_approved_prefix_and_random_payload() -> None:
    first = new_id("prj")
    second = new_id("prj")

    assert re.fullmatch(r"prj_[0-9a-f]{32}", first)
    assert first != second
    with pytest.raises(ValueError, match="unsupported"):
        new_id("unknown")


def test_prefixed_identifier_constraint_is_emitted_to_json_schema() -> None:
    schema = Project.model_json_schema()

    assert schema["properties"]["project_id"]["pattern"].startswith("^prj_")


def test_domain_models_do_not_coerce_strings_to_numbers() -> None:
    with pytest.raises(ValidationError):
        RationalRate(numerator="24")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        RationalTime.model_validate({"ticks": "1", "rate": {"numerator": 24, "denominator": 1}})


def test_project_settings_schema_keeps_exact_rate_components() -> None:
    schema = ProjectSettings.model_json_schema()

    assert "RationalRate" in schema["$defs"]
    rate_properties = schema["$defs"]["RationalRate"]["properties"]
    assert set(rate_properties) == {"numerator", "denominator"}
