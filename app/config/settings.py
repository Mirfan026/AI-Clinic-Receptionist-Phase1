import os
from functools import lru_cache


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _get_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def _get_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


class Settings:
    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///./storage/clinic.db")

    @property
    def llm_enabled(self) -> bool:
        return _get_bool("LLM_ENABLED", False)

    @property
    def llm_provider(self) -> str:
        return os.getenv("LLM_PROVIDER", "groq").strip().lower()

    @property
    def groq_api_key(self) -> str:
        return os.getenv("GROQ_API_KEY", "").strip()

    @property
    def groq_model(self) -> str:
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

    @property
    def llm_temperature(self) -> float:
        return _get_float("LLM_TEMPERATURE", 0.1, minimum=0.0, maximum=2.0)

    @property
    def llm_max_tokens(self) -> int:
        return _get_int("LLM_MAX_TOKENS", 400, minimum=1)

    @property
    def llm_timeout_seconds(self) -> float:
        return _get_float("LLM_TIMEOUT_SECONDS", 15.0, minimum=0.1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
