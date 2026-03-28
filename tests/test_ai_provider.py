"""Tests for the unified AI provider abstraction."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace


def test_generate_routes_to_gemini_provider(monkeypatch):
    import ai_provider

    captured = {}
    fake_module = types.ModuleType("gemini_client")

    class FakeGeminiClient:
        def __init__(self, api_key=None, model=None, user_id=None, allow_fallback=True):
            captured["api_key"] = api_key
            captured["model"] = model
            captured["user_id"] = user_id
            captured["allow_fallback"] = allow_fallback

        def generate(self, prompt, max_tokens=2048, temperature=0.7):
            captured["prompt"] = prompt
            captured["max_tokens"] = max_tokens
            captured["temperature"] = temperature
            return "gemini-ok"

    fake_module.GeminiClient = FakeGeminiClient
    monkeypatch.setitem(sys.modules, "gemini_client", fake_module)

    user_config = SimpleNamespace(
        ai_provider="gemini",
        ai_model="gemini-2.5-pro",
        ai_api_key="gem-key",
        gemini_api_key="",
    )

    result = ai_provider.generate("hello", user_config, max_tokens=99, temperature=0.2)

    assert result == "gemini-ok"
    assert captured == {
        "api_key": "gem-key",
        "model": "gemini-2.5-pro",
        "user_id": None,
        "allow_fallback": False,
        "prompt": "hello",
        "max_tokens": 99,
        "temperature": 0.2,
    }


def test_claude_provider_uses_anthropic_messages_api(monkeypatch):
    import ai_provider

    captured = {}
    fake_module = types.ModuleType("anthropic")

    class FakeMessages:
        def create(self, **kwargs):
            captured["payload"] = kwargs
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="claude-ok")]
            )

    class FakeAnthropic:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    fake_module.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    provider = ai_provider.get_provider(
        name="claude",
        api_key="claude-key",
        model="claude-sonnet-4-6",
    )
    result = provider.generate("hello claude", max_tokens=55, temperature=0.1)

    assert result == "claude-ok"
    assert captured["api_key"] == "claude-key"
    assert captured["payload"]["model"] == "claude-sonnet-4-6"
    assert captured["payload"]["max_tokens"] == 55
    assert captured["payload"]["temperature"] == 0.1
    assert captured["payload"]["messages"][0]["content"][0]["text"] == "hello claude"


def test_openai_provider_uses_chat_completions(monkeypatch):
    import ai_provider

    captured = {}
    fake_module = types.ModuleType("openai")

    class FakeCompletions:
        def create(self, **kwargs):
            captured["payload"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="openai-ok"))]
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.chat = FakeChat()

    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    provider = ai_provider.get_provider(
        name="openai",
        api_key="openai-key",
        model="gpt-4o-mini",
    )
    result = provider.generate("hello openai", max_tokens=21, temperature=0.4)

    assert result == "openai-ok"
    assert captured["api_key"] == "openai-key"
    assert captured["payload"]["model"] == "gpt-4o-mini"
    assert captured["payload"]["max_tokens"] == 21
    assert captured["payload"]["temperature"] == 0.4


def test_openai_provider_uses_max_completion_tokens_for_o1(monkeypatch):
    import ai_provider

    captured = {}
    fake_module = types.ModuleType("openai")

    class FakeCompletions:
        def create(self, **kwargs):
            captured["payload"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="o1-ok"))]
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key):
            self.chat = FakeChat()

    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    provider = ai_provider.get_provider(
        name="openai",
        api_key="openai-key",
        model="o1-mini",
    )
    result = provider.generate("reason", max_tokens=7, temperature=0.9)

    assert result == "o1-ok"
    assert captured["payload"]["max_completion_tokens"] == 7
    assert "max_tokens" not in captured["payload"]
    assert "temperature" not in captured["payload"]


def test_openrouter_provider_uses_required_headers(monkeypatch):
    import ai_provider

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "openrouter-ok",
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(ai_provider.requests, "post", fake_post)

    provider = ai_provider.get_provider(
        name="openrouter",
        api_key="or-key",
        model="deepseek/deepseek-r1",
    )
    result = provider.generate("hello router", max_tokens=13, temperature=0.5)

    assert result == "openrouter-ok"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer or-key"
    assert "HTTP-Referer" in captured["headers"]
    assert "X-Title" in captured["headers"]
    assert captured["json"]["model"] == "deepseek/deepseek-r1"


def test_alias_provider_routes_through_openrouter(monkeypatch):
    import ai_provider

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "grok-ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(ai_provider.requests, "post", fake_post)

    provider = ai_provider.get_provider(name="grok", api_key="or-key", model="x-ai/grok-4")
    result = provider.generate("hello")

    assert result == "grok-ok"
    assert captured["headers"]["Authorization"] == "Bearer or-key"
    assert captured["json"]["model"] == "x-ai/grok-4"


def test_list_providers_returns_rich_catalog():
    import ai_provider

    providers = ai_provider.list_providers()
    claude = next(item for item in providers if item["id"] == "claude")
    deepseek = next(item for item in providers if item["id"] == "deepseek")

    assert claude["default_model"] == "claude-sonnet-4-6"
    assert any(model["recommended"] for model in claude["models"])
    assert deepseek["status"] == "via_openrouter"


def test_test_ai_key_returns_missing_key_error():
    import ai_provider

    payload = ai_provider.test_ai_key("openai", "", "gpt-4o-mini")

    assert payload == {
        "valid": False,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "error": "No API key was provided.",
    }


def test_generate_uses_fallback_provider_after_primary_failure(monkeypatch):
    import ai_provider

    calls = []

    def fake_generate_with_retry(provider_name, api_key, model, prompt, max_tokens, temperature, retries=3):
        calls.append((provider_name, model, api_key))
        if provider_name == "claude":
            raise ai_provider.AIProviderError("claude", model, "Anthropic Claude could not complete the request.")
        return "fallback-ok"

    monkeypatch.setattr(ai_provider, "_generate_with_retry", fake_generate_with_retry)

    user_config = SimpleNamespace(
        ai_provider="claude",
        provider_fallback="openrouter",
        ai_model="claude-sonnet-4-6",
        ai_api_key="primary-key",
        gemini_api_key="",
    )

    result = ai_provider.generate("hello", user_config)

    assert result == "fallback-ok"
    assert calls[0][0] == "claude"
    assert calls[1][0] == "openrouter"
