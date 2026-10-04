import pytest

from app.config.settings import Settings, get_settings


LLM_ENV_VARS = (
    "LLM_ENABLED",
    "LLM_PROVIDER",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_TIMEOUT_SECONDS",
)


def _clear_llm_env(monkeypatch):
    for name in LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


def test_llm_defaults_do_not_require_api_key(monkeypatch):
    _clear_llm_env(monkeypatch)
    settings = Settings()

    assert settings.llm_enabled is False
    assert settings.llm_provider == "groq"
    assert settings.groq_api_key == ""
    assert settings.groq_model == "openai/gpt-oss-20b"
    assert settings.llm_temperature == 0.1
    assert settings.llm_max_tokens == 400
    assert settings.llm_timeout_seconds == 15.0


def test_llm_environment_overrides(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "GROQ")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "custom-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.25")
    monkeypatch.setenv("LLM_MAX_TOKENS", "512")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "20")

    settings = Settings()

    assert settings.llm_enabled is True
    assert settings.llm_provider == "groq"
    assert settings.groq_api_key == "test-key"
    assert settings.groq_model == "custom-model"
    assert settings.llm_temperature == 0.25
    assert settings.llm_max_tokens == 512
    assert settings.llm_timeout_seconds == 20.0


@pytest.mark.parametrize("value", ["maybe", "enabled", "2"])
def test_invalid_llm_enabled_raises(monkeypatch, value):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", value)

    with pytest.raises(ValueError, match="LLM_ENABLED"):
        _ = Settings().llm_enabled


@pytest.mark.parametrize(
    ("name", "value", "attribute"),
    [
        ("LLM_TEMPERATURE", "not-a-number", "llm_temperature"),
        ("LLM_TEMPERATURE", "-0.1", "llm_temperature"),
        ("LLM_TEMPERATURE", "2.1", "llm_temperature"),
        ("LLM_MAX_TOKENS", "0", "llm_max_tokens"),
        ("LLM_MAX_TOKENS", "abc", "llm_max_tokens"),
        ("LLM_TIMEOUT_SECONDS", "0", "llm_timeout_seconds"),
        ("LLM_TIMEOUT_SECONDS", "abc", "llm_timeout_seconds"),
    ],
)
def test_invalid_numeric_llm_settings_raise(monkeypatch, name, value, attribute):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        getattr(Settings(), attribute)
