"""Lazy Groq text provider. No routing, clinic policy, RAG, or database access."""

from math import isfinite
from threading import Lock
from typing import Any, Callable, Sequence

from app.config.settings import Settings, get_settings
from .base import (
    ChatMessage, LLMAuthenticationError, LLMConfigurationError,
    LLMConnectionError, LLMError, LLMProviderError, LLMRateLimitError,
    LLMResponseError, LLMTimeoutError,
)


class GroqLLMClient:
    """Explicit generate() calls opt in to API use; construction is offline.

    LLM_ENABLED belongs to the future application wiring, not this provider:
    the optional manual smoke test can use it before agent integration.
    client_factory permits offline tests without changing application code.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: Callable[..., Any] | None = None,
    ):
        self.settings = settings if settings is not None else get_settings()
        self._client_factory = client_factory
        self._client = None
        self._lock = Lock()

    def _configuration(self):
        try:
            if self.settings.llm_provider != "groq":
                raise ValueError
            model = self.settings.groq_model
            temperature = self.settings.llm_temperature
            max_tokens = self.settings.llm_max_tokens
            timeout = self.settings.llm_timeout_seconds
            if (not model or not isfinite(temperature) or not 0 <= temperature <= 2
                    or not isfinite(timeout) or timeout < 0.1 or max_tokens < 1):
                raise ValueError
            return model, temperature, max_tokens, timeout
        except (ValueError, TypeError):
            raise LLMConfigurationError("LLM configuration is invalid.") from None

    def _get_client(self, sdk, timeout):
        with self._lock:
            if self._client is None:
                key = self.settings.groq_api_key
                if not key:
                    raise LLMConfigurationError("GROQ_API_KEY is not configured.")
                factory = self._client_factory or sdk.Groq
                self._client = factory(
                    api_key=key,
                    timeout=timeout,
                    max_retries=0,
                )
            return self._client

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Generate bounded text or raise a sanitized, provider-neutral error.

        No retries are performed. Policy and deterministic fallback remain the
        responsibility of the application layer added in a later step.
        """
        if not isinstance(messages, Sequence) or not messages or any(
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or not isinstance(message["role"], str)
            or message["role"] not in {"system", "user", "assistant"}
            or not isinstance(message["content"], str)
            or not message["content"].strip()
            for message in messages
        ):
            raise LLMConfigurationError("LLM messages are invalid.")

        model, temperature, max_tokens, timeout = self._configuration()
        try:
            import groq
        except ImportError:
            raise LLMConfigurationError("The Groq SDK is not installed.") from None

        try:
            client = self._get_client(groq, timeout)
            response = client.chat.completions.create(
                messages=[dict(message) for message in messages],
                model=model,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                timeout=timeout,
                stream=False,
            )
        except LLMError:
            raise
        except (groq.AuthenticationError, groq.PermissionDeniedError):
            raise LLMAuthenticationError("LLM provider authentication failed.") from None
        except groq.RateLimitError:
            raise LLMRateLimitError("LLM provider rate limit reached.") from None
        except groq.APITimeoutError:
            raise LLMTimeoutError("LLM provider request timed out.") from None
        except groq.APIConnectionError:
            raise LLMConnectionError("LLM provider is unavailable.") from None
        except Exception:
            # SDK response parsing and unexpected provider errors may contain
            # credentials, request bodies, or internals. Never pass them on.
            raise LLMProviderError("LLM provider request failed.") from None

        try:
            choice = response.choices[0]
            message = choice.message
            text = message.content
            if (message.role != "assistant" or choice.finish_reason != "stop"
                    or message.tool_calls or getattr(message, "function_call", None)
                    or not isinstance(text, str) or not text.strip()):
                raise ValueError
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            raise LLMResponseError("LLM provider returned no usable text.") from None
        return text.strip()

    def close(self) -> None:
        """Release an initialized SDK client; closing an unused client is offline."""
        with self._lock:
            if self._client is not None:
                client, self._client = self._client, None
                try:
                    client.close()
                except Exception:
                    raise LLMProviderError("LLM provider cleanup failed.") from None
