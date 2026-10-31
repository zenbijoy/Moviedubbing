from aidub.security.redaction import Redactor


def test_redacts_nested_secrets() -> None:
    value = {
        "api_key": "very-secret",
        "nested": {"authorization": "Bearer abc.def.ghi"},
        "safe": "visible",
    }
    redacted = Redactor.value(value)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert redacted["safe"] == "visible"


def test_redacts_bearer_and_common_keys_in_text() -> None:
    text = Redactor.text("authorization=Bearer abc.def key-abcd1234")
    assert "abc.def" not in text
    assert "key-abcd1234" not in text
