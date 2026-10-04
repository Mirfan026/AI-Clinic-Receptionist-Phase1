"""Provider-neutral text generation contract and safe failure types."""

from typing import Literal, Protocol, Sequence, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(Protocol):
    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return text or raise LLMError so the caller can use its fallback."""
        ...


class LLMError(Exception):
    """Base for safe application errors, without raw provider details."""


class LLMConfigurationError(LLMError):
    """Missing credentials, unsupported provider, or invalid settings."""


class LLMAuthenticationError(LLMError):
    """Provider rejected credentials or access permissions."""


class LLMRateLimitError(LLMError):
    """Provider rate limit reached."""


class LLMTimeoutError(LLMError):
    """Provider request timed out."""


class LLMConnectionError(LLMError):
    """Provider could not be reached."""


class LLMProviderError(LLMError):
    """Other provider or SDK failure."""


class LLMResponseError(LLMError):
    """Empty, malformed, or incomplete text completion."""
