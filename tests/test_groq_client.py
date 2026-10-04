import builtins
import json
import runpy
import socket
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

import groq
import httpx
import pytest

from app.config.settings import Settings
from app.llm.base import (
    LLMAuthenticationError, LLMConfigurationError, LLMConnectionError,
    LLMProviderError, LLMRateLimitError, LLMResponseError, LLMTimeoutError,
)
from app.llm.groq_client import GroqLLMClient


MESSAGES = [
    {"role": "system", "content": "Use supplied facts only."},
    {"role": "user", "content": "Hello"},
]
TEST_KEY = "test-credential-not-real"


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    for name in (
        "LLM_ENABLED", "LLM_PROVIDER", "GROQ_MODEL", "LLM_TEMPERATURE",
        "LLM_MAX_TOKENS", "LLM_TIMEOUT_SECONDS", "GROQ_LOG",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", TEST_KEY)

    def deny_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in these tests")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)


def completion(content=" Hello! ", **overrides):
    message = SimpleNamespace(
        role=overrides.get("role", "assistant"), content=content,
        tool_calls=overrides.get("tool_calls"),
        function_call=overrides.get("function_call"),
    )
    return SimpleNamespace(choices=[SimpleNamespace(
        message=message, finish_reason=overrides.get("finish_reason", "stop"),
    )])


def fake_client(response=None):
    sdk = Mock()
    sdk.chat.completions.create.return_value = (
        completion() if response is None else response
    )
    factory = Mock(return_value=sdk)
    return GroqLLMClient(Settings(), client_factory=factory), sdk, factory


def test_lazy_initialization_and_default_parameters():
    provider, sdk, factory = fake_client()
    factory.assert_not_called()
    assert provider.generate(MESSAGES) == "Hello!"
    factory.assert_called_once_with(api_key=TEST_KEY, timeout=15.0, max_retries=0)
    sdk.chat.completions.create.assert_called_once_with(
        messages=MESSAGES, model="openai/gpt-oss-20b", temperature=0.1,
        max_completion_tokens=400, timeout=15.0, stream=False,
    )


def test_environment_settings_control_request(monkeypatch):
    for name, value in {
        "GROQ_MODEL": "custom-model", "LLM_TEMPERATURE": "0.25",
        "LLM_MAX_TOKENS": "512", "LLM_TIMEOUT_SECONDS": "7",
    }.items():
        monkeypatch.setenv(name, value)
    provider, sdk, factory = fake_client()
    provider.generate(MESSAGES)
    factory.assert_called_once_with(api_key=TEST_KEY, timeout=7.0, max_retries=0)
    request = sdk.chat.completions.create.call_args.kwargs
    assert (request["model"], request["temperature"],
            request["max_completion_tokens"], request["timeout"]) == (
                "custom-model", 0.25, 512, 7.0,
            )


def test_client_reuse_and_close():
    provider, sdk, factory = fake_client()
    provider.close()
    factory.assert_not_called()
    provider.generate(MESSAGES)
    provider.generate(MESSAGES)
    factory.assert_called_once()
    provider.close()
    provider.close()
    sdk.close.assert_called_once()


def test_missing_key_is_safe_and_does_not_initialize(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    provider, sdk, factory = fake_client()
    with pytest.raises(LLMConfigurationError, match="not configured"):
        provider.generate(MESSAGES)
    factory.assert_not_called()
    sdk.chat.completions.create.assert_not_called()


@pytest.mark.parametrize("status,expected", [
    (401, LLMAuthenticationError), (403, LLMAuthenticationError),
    (429, LLMRateLimitError), (500, LLMProviderError),
    (503, LLMProviderError), (400, LLMProviderError),
])
def test_real_sdk_http_errors_are_sanitized_without_retries(status, expected, capsys, caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": TEST_KEY}})

    sdk = groq.Groq(api_key=TEST_KEY, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider = GroqLLMClient(Settings(), client_factory=Mock(return_value=sdk))
    try:
        with pytest.raises(expected) as caught:
            provider.generate(MESSAGES)
        assert len(requests) == 1
        assert TEST_KEY not in "".join(traceback.format_exception(caught.value))
        assert caught.value.__cause__ is None
        assert TEST_KEY not in caplog.text
        assert TEST_KEY not in capsys.readouterr().out
    finally:
        provider.close()


@pytest.mark.parametrize("failure,expected", [
    (httpx.ReadTimeout, LLMTimeoutError),
    (httpx.ConnectError, LLMConnectionError),
])
def test_real_sdk_network_failures_are_sanitized_without_retries(failure, expected):
    calls = []

    def handler(request):
        calls.append(request)
        raise failure(TEST_KEY, request=request)

    sdk = groq.Groq(api_key=TEST_KEY, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider = GroqLLMClient(Settings(), client_factory=Mock(return_value=sdk))
    try:
        with pytest.raises(expected) as caught:
            provider.generate(MESSAGES)
        assert len(calls) == 1
        assert TEST_KEY not in "".join(traceback.format_exception(caught.value))
    finally:
        provider.close()


def test_default_factory_uses_sdk_and_serializes_request(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "completion-test", "created": 0, "object": "chat.completion",
            "model": "openai/gpt-oss-20b", "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello!"},
            }],
        })

    real_factory = groq.Groq
    factory = Mock(side_effect=lambda **kwargs: real_factory(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ))
    monkeypatch.setattr(groq, "Groq", factory)
    provider = GroqLLMClient(Settings())
    try:
        assert provider.generate(MESSAGES) == "Hello!"
        factory.assert_called_once_with(api_key=TEST_KEY, timeout=15.0, max_retries=0)
        body = json.loads(requests[0].content)
        assert body["messages"] == MESSAGES
        assert body["max_completion_tokens"] == 400
        assert requests[0].extensions["timeout"]["read"] == 15.0
    finally:
        provider.close()


@pytest.mark.parametrize("response", [
    SimpleNamespace(choices=[]), SimpleNamespace(),
    SimpleNamespace(choices=None), SimpleNamespace(choices=[None]),
    SimpleNamespace(choices={}),
    completion(None), completion(""), completion("  "), completion(42),
    completion(finish_reason="length"), completion(finish_reason="tool_calls"),
    completion(tool_calls=[{"name": "book_appointment"}]),
    completion(function_call={"name": "book_appointment"}),
    completion(role="user"),
])
def test_empty_malformed_incomplete_or_tool_response_is_rejected(response):
    provider, sdk, _ = fake_client(response)
    with pytest.raises(LLMResponseError):
        provider.generate(MESSAGES)
    sdk.chat.completions.create.assert_called_once()


@pytest.mark.parametrize("name,value", [
    ("LLM_PROVIDER", "unknown"), ("GROQ_MODEL", " "),
    ("LLM_TEMPERATURE", "nan"), ("LLM_TEMPERATURE", "inf"),
    ("LLM_TIMEOUT_SECONDS", "nan"), ("LLM_TIMEOUT_SECONDS", "inf"),
    ("LLM_MAX_TOKENS", "0"), ("LLM_TIMEOUT_SECONDS", "abc"),
])
def test_invalid_configuration_does_not_initialize(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    provider, sdk, factory = fake_client()
    with pytest.raises(LLMConfigurationError):
        provider.generate(MESSAGES)
    factory.assert_not_called()
    sdk.chat.completions.create.assert_not_called()


@pytest.mark.parametrize("messages", [
    [], [{"role": "tool", "content": "x"}],
    [{"role": "user", "content": None}], [{"role": "user", "content": " "}],
    [{"role": "user", "content": "x", "tools": []}], [None],
    [{"role": [], "content": "x"}], 42,
])
def test_invalid_messages_are_rejected_before_api_use(messages):
    provider, _, factory = fake_client()
    with pytest.raises(LLMConfigurationError):
        provider.generate(messages)
    factory.assert_not_called()


def test_unexpected_request_error_is_sanitized():
    provider, sdk, _ = fake_client()
    sdk.chat.completions.create.side_effect = RuntimeError(TEST_KEY)
    with pytest.raises(LLMProviderError) as caught:
        provider.generate(MESSAGES)
    assert TEST_KEY not in "".join(traceback.format_exception(caught.value))


def test_initialization_error_is_sanitized():
    provider = GroqLLMClient(Settings(), client_factory=Mock(side_effect=RuntimeError(TEST_KEY)))
    with pytest.raises(LLMProviderError) as caught:
        provider.generate(MESSAGES)
    assert TEST_KEY not in "".join(traceback.format_exception(caught.value))


def test_missing_sdk_is_safe_and_import_is_lazy(monkeypatch):
    original_import = builtins.__import__

    def without_sdk(name, *args, **kwargs):
        if name == "groq":
            raise ImportError(TEST_KEY)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_sdk)
    provider, _, factory = fake_client()
    with pytest.raises(LLMConfigurationError, match="SDK is not installed") as caught:
        provider.generate(MESSAGES)
    factory.assert_not_called()
    assert TEST_KEY not in "".join(traceback.format_exception(caught.value))


def test_smoke_script_import_does_not_call_provider(monkeypatch):
    generate = Mock(side_effect=AssertionError("Smoke test must be explicit"))
    monkeypatch.setattr(GroqLLMClient, "generate", generate)
    runpy.run_path("scripts/test_groq_connection.py", run_name="smoke_module")
    generate.assert_not_called()


def test_smoke_script_missing_key_makes_no_request(monkeypatch, capsys):
    from scripts.test_groq_connection import main
    monkeypatch.delenv("GROQ_API_KEY")
    generate = Mock()
    monkeypatch.setattr(GroqLLMClient, "generate", generate)
    assert main() == 1
    generate.assert_not_called()
    assert "FAILURE" in capsys.readouterr().out


def test_smoke_script_redacts_known_key(monkeypatch, capsys):
    from scripts.test_groq_connection import main
    monkeypatch.setattr(GroqLLMClient, "generate", Mock(return_value=f"Hello {TEST_KEY}"))
    assert main() == 0
    output = capsys.readouterr().out
    assert "SUCCESS" in output and "Model: openai/gpt-oss-20b" in output
    assert TEST_KEY not in output and "[redacted]" in output


def test_smoke_script_failure_has_no_raw_details(monkeypatch, capsys):
    from scripts.test_groq_connection import main
    monkeypatch.setattr(GroqLLMClient, "generate", Mock(side_effect=LLMTimeoutError("LLM provider request timed out.")))
    assert main() == 1
    output = capsys.readouterr().out
    assert "FAILURE" in output and "timed out" in output and TEST_KEY not in output
