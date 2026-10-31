from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from aidub.i18n import (
    CatalogError,
    CatalogRepository,
    LocaleService,
    locale_fallback_chain,
    normalize_locale,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_catalog(directory: Path, locale_name: str, strings: dict[str, str]) -> None:
    payload = {
        "meta": {
            "locale": locale_name,
            "display_name": locale_name,
            "native_name": locale_name,
            "direction": "ltr",
            "version": 1,
        },
        "strings": strings,
    }
    (directory / f"{locale_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en_US.UTF-8", "en-US"),
        ("BN_bd", "bn-BD"),
        ("hi-in@devanagari", "hi-IN"),
        ("zh_hant_tw", "zh-Hant-TW"),
        ("C", "en"),
        ("not a locale", "en"),
        (None, "en"),
    ],
)
def test_normalize_locale_handles_operating_system_forms(raw: str | None, expected: str) -> None:
    assert normalize_locale(raw) == expected


def test_fallback_chain_resolves_language_and_regional_catalogs() -> None:
    available = ("en", "bn-BD", "hi-IN")

    assert locale_fallback_chain("bn", available) == ("bn-BD", "en")
    assert locale_fallback_chain("en-GB", available) == ("en",)
    assert locale_fallback_chain("hi-NP", available) == ("hi-IN", "en")
    assert locale_fallback_chain("fr-FR", available) == ("en",)


def test_shipped_catalogs_are_complete_and_have_native_names() -> None:
    repository = CatalogRepository()
    assert repository.available_locales() == ("en", "bn-BD", "hi-IN")

    catalogs = repository.available_locales()
    baseline = set(repository.load("en").strings)
    assert baseline
    for locale_name in catalogs:
        catalog = repository.load(locale_name)
        assert catalog.native_name
        assert catalog.direction == "ltr"
        assert set(catalog.strings) == baseline


def test_locale_service_resolves_region_and_falls_back_per_string(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "en", {"hello": "Hello {name}", "fallback": "English only"})
    _write_catalog(tmp_path, "bn-BD", {"hello": "স্বাগতম {name}"})
    service = LocaleService("bn", repository=CatalogRepository(tmp_path))

    assert service.locale == "bn-BD"
    assert service("hello", name="রিমা") == "স্বাগতম রিমা"
    assert service("fallback") == "English only"
    assert service("missing.key") == "missing.key"
    assert service("missing.key", "Safe default") == "Safe default"


def test_locale_change_notifies_once_and_can_unsubscribe(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "en", {"hello": "Hello"})
    _write_catalog(tmp_path, "hi-IN", {"hello": "नमस्ते"})
    service = LocaleService("en", repository=CatalogRepository(tmp_path))
    observed: list[str] = []
    unsubscribe = service.subscribe(observed.append)

    assert service.set_locale("hi") == "hi-IN"
    service.set_locale("hi-IN")
    unsubscribe()
    service.set_locale("en")

    assert observed == ["hi-IN"]


def test_catalog_validation_rejects_invalid_translation_values(tmp_path: Path) -> None:
    path = tmp_path / "en.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"locale": "en", "direction": "ltr", "version": 1},
                "strings": {"valid": "text", "invalid": 7},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="non-text"):
        CatalogRepository(tmp_path).load("en")


def test_catalog_strings_are_immutable() -> None:
    catalog = CatalogRepository().load("en")

    with pytest.raises(TypeError):
        catalog.strings["new.key"] = "value"  # type: ignore[index]
