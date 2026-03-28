"""Unified multi-provider AI interface for generation, validation, and fallback."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any, Dict, List, Optional

import requests

import config

logger = config.get_logger("ai_provider")


OPENROUTER_ALIAS_PROVIDERS = {
    "grok",
    "groq",
    "deepseek",
    "minimax",
    "glm",
    "nvidia",
}

PROVIDER_CATALOG = {
    "gemini": {
        "id": "gemini",
        "display_name": "Google Gemini",
        "models": [
            {"id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "recommended": True, "tier": "balanced"},
            {"id": "gemini-2.5-flash-lite", "display_name": "Gemini 2.5 Flash-Lite", "recommended": False, "tier": "fast"},
            {"id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "recommended": False, "tier": "powerful"},
        ],
        "default_model": "gemini-2.5-flash",
        "get_key_url": "https://aistudio.google.com",
        "key_format_hint": "AIza...",
        "status": "available",
    },
    "claude": {
        "id": "claude",
        "display_name": "Anthropic Claude",
        "models": [
            {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "recommended": True, "tier": "balanced"},
            {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "recommended": False, "tier": "powerful"},
            {"id": "claude-haiku-4-5-20251001", "display_name": "Claude Haiku 4.5", "recommended": False, "tier": "fast"},
        ],
        "default_model": "claude-sonnet-4-6",
        "get_key_url": "https://console.anthropic.com",
        "key_format_hint": "sk-ant-...",
        "status": "available",
    },
    "openai": {
        "id": "openai",
        "display_name": "OpenAI",
        "models": [
            {"id": "gpt-4o-mini", "display_name": "GPT-4o mini", "recommended": True, "tier": "balanced"},
            {"id": "gpt-4o", "display_name": "GPT-4o", "recommended": False, "tier": "powerful"},
            {"id": "o1-mini", "display_name": "o1-mini", "recommended": False, "tier": "reasoning"},
        ],
        "default_model": "gpt-4o-mini",
        "get_key_url": "https://platform.openai.com/api-keys",
        "key_format_hint": "sk-...",
        "status": "available",
    },
    "openrouter": {
        "id": "openrouter",
        "display_name": "OpenRouter",
        "models": [
            {"id": "openai/gpt-4o-mini", "display_name": "GPT-4o mini via OpenRouter", "recommended": True, "tier": "balanced"},
            {"id": "anthropic/claude-3.7-sonnet", "display_name": "Claude Sonnet via OpenRouter", "recommended": False, "tier": "powerful"},
            {"id": "deepseek/deepseek-r1", "display_name": "DeepSeek R1 via OpenRouter", "recommended": False, "tier": "reasoning"},
        ],
        "default_model": config.OPENROUTER_MODEL or "openai/gpt-4o-mini",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "available",
    },
    "grok": {
        "id": "grok",
        "display_name": "xAI Grok (via OpenRouter)",
        "models": [
            {"id": "x-ai/grok-4", "display_name": "Grok 4 via OpenRouter", "recommended": True, "tier": "balanced"},
        ],
        "default_model": "x-ai/grok-4",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
    "groq": {
        "id": "groq",
        "display_name": "Groq (via OpenRouter)",
        "models": [
            {"id": "groq/llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B via OpenRouter", "recommended": True, "tier": "fast"},
        ],
        "default_model": "groq/llama-3.3-70b-versatile",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
    "deepseek": {
        "id": "deepseek",
        "display_name": "DeepSeek (via OpenRouter)",
        "models": [
            {"id": "deepseek/deepseek-chat-v3-0324", "display_name": "DeepSeek V3 via OpenRouter", "recommended": True, "tier": "balanced"},
            {"id": "deepseek/deepseek-r1", "display_name": "DeepSeek R1 via OpenRouter", "recommended": False, "tier": "powerful"},
        ],
        "default_model": "deepseek/deepseek-chat-v3-0324",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
    "minimax": {
        "id": "minimax",
        "display_name": "MiniMax (via OpenRouter)",
        "models": [
            {"id": "minimax/minimax-m1", "display_name": "MiniMax M1 via OpenRouter", "recommended": True, "tier": "balanced"},
        ],
        "default_model": "minimax/minimax-m1",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
    "glm": {
        "id": "glm",
        "display_name": "GLM (via OpenRouter)",
        "models": [
            {"id": "zhipuai/glm-4.5", "display_name": "GLM 4.5 via OpenRouter", "recommended": True, "tier": "balanced"},
        ],
        "default_model": "zhipuai/glm-4.5",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
    "nvidia": {
        "id": "nvidia",
        "display_name": "NVIDIA NIM (via OpenRouter)",
        "models": [
            {"id": "nvidia/llama-3.1-nemotron-ultra-253b-v1", "display_name": "Nemotron Ultra via OpenRouter", "recommended": True, "tier": "powerful"},
        ],
        "default_model": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "get_key_url": "https://openrouter.ai/keys",
        "key_format_hint": "sk-or-...",
        "status": "via_openrouter",
    },
}

OPENROUTER_REFERER = "https://content-factory.local"
OPENROUTER_TITLE = "Content Factory"


class AIProviderError(RuntimeError):
    """Raised when generation fails after retries and optional fallback."""

    def __init__(
        self,
        provider: str,
        model: str,
        message: str,
        fallback_provider: str = "",
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.fallback_provider = fallback_provider
        self.user_message = message


def _normalize_provider_name(name: Optional[str]) -> str:
    provider = (name or "gemini").strip().lower()
    return provider if provider in PROVIDER_CATALOG else "gemini"


def _runtime_provider_name(provider_name: str) -> str:
    return "openrouter" if provider_name in OPENROUTER_ALIAS_PROVIDERS else provider_name


def _get_user_config_value(user_config: Any, field: str, default: Any = "") -> Any:
    if user_config is None:
        return default
    if isinstance(user_config, dict):
        return user_config.get(field, default)
    return getattr(user_config, field, default)


def _resolve_provider_name(user_config: Any) -> str:
    return _normalize_provider_name(_get_user_config_value(user_config, "ai_provider", "gemini"))


def _resolve_fallback_provider_name(user_config: Any) -> str:
    fallback = _normalize_provider_name(_get_user_config_value(user_config, "provider_fallback", ""))
    primary = _resolve_provider_name(user_config)
    if not fallback or fallback == primary:
        return ""
    return fallback


def _resolve_model(user_config: Any, provider_name: str) -> str:
    explicit_model = str(_get_user_config_value(user_config, "ai_model", "") or "").strip()
    if explicit_model:
        return explicit_model
    return PROVIDER_CATALOG[provider_name]["default_model"]


def _env_key_for_provider(provider_name: str) -> str:
    runtime_provider = _runtime_provider_name(provider_name)
    env_map = {
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_name = env_map.get(runtime_provider, "")
    if env_name:
        value = config.get_env(env_name, "") or ""
        if value:
            return value
    if runtime_provider == "openrouter":
        for env_name in ("OPENROUTER_API_KEY_1", "OPENROUTER_API_KEY_2", "OPENROUTER_API_KEY_3"):
            value = config.get_env(env_name, "") or ""
            if value:
                return value
    return ""


def _resolve_api_key(user_config: Any, provider_name: str) -> str:
    requested_provider = _resolve_provider_name(user_config)
    ai_key = str(_get_user_config_value(user_config, "ai_api_key", "") or "").strip()
    provider_specific_key = str(_get_user_config_value(user_config, "gemini_api_key", "") or "").strip()

    if provider_name == requested_provider:
        if provider_name == "gemini":
            return ai_key or provider_specific_key or _env_key_for_provider(provider_name)
        return ai_key or _env_key_for_provider(provider_name)

    if provider_name in OPENROUTER_ALIAS_PROVIDERS or provider_name == "openrouter":
        return ai_key or _env_key_for_provider(provider_name)

    return _env_key_for_provider(provider_name)


def _extract_openai_like_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(item["text"])
            elif hasattr(item, "type") and getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", ""))
        return "\n".join(part for part in parts if part)
    return ""


def _extract_http_error(response: requests.Response) -> tuple[int, str]:
    try:
        payload = response.json()
    except Exception:
        return response.status_code, response.text[:500]

    for path in (
        ("error", "message"),
        ("error",),
        ("message",),
        ("detail",),
    ):
        current = payload
        found = True
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current:
            return response.status_code, str(current)
    return response.status_code, str(payload)[:500]


def _friendly_error_message(
    provider_name: str,
    model: str,
    status_code: Optional[int] = None,
    raw_message: str = "",
) -> str:
    provider_label = PROVIDER_CATALOG[provider_name]["display_name"]
    key_url = PROVIDER_CATALOG[provider_name]["get_key_url"]
    message = (raw_message or "").lower()

    if status_code == 401 or "invalid api key" in message or "incorrect api key" in message or "authentication" in message:
        return f"Your API key is invalid — check it at {key_url}"
    if status_code == 403 or "permission" in message or "forbidden" in message:
        return f"Your {provider_label} key does not have permission to use this model."
    if status_code == 404 or "model" in message and ("not found" in message or "does not exist" in message):
        default_model = PROVIDER_CATALOG[provider_name]["default_model"]
        return f"This model does not exist — try {default_model} instead."
    if status_code == 429 or "rate limit" in message or "too many requests" in message:
        return "You have exceeded your rate limit — wait a few minutes and try again."
    if "quota" in message or "billing" in message or "insufficient" in message:
        return f"Your {provider_label} account does not have enough quota for this request."
    if "timeout" in message or "timed out" in message or "deadline" in message:
        return f"{provider_label} is taking too long to respond — try again in a moment."
    if "api key" in message and "missing" in message:
        return f"No API key was provided for {provider_label}."
    if "connection" in message or "network" in message or "dns" in message:
        return f"{provider_label} is not reachable right now — please try again."
    return f"{provider_label} could not complete the request. {raw_message or 'Please try again.'}".strip()


def _log_validation_latency(provider_name: str, model: str, started_at: float) -> None:
    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "AI key validation provider=%s model=%s latency_ms=%d",
        provider_name,
        model,
        latency_ms,
    )


@dataclass
class BaseAIProvider:
    """Base provider contract."""

    provider_name: str
    api_key: str
    model: str

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        raise NotImplementedError

    def test_connection(self) -> Dict:
        raise NotImplementedError

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(f"No API key configured for provider '{self.provider_name}'.")

    def _validation_success(self) -> Dict:
        return {
            "valid": True,
            "provider": self.provider_name,
            "model": self.model,
            "error": None,
        }

    def _validation_failure(self, raw_message: str, status_code: Optional[int] = None) -> Dict:
        return {
            "valid": False,
            "provider": self.provider_name,
            "model": self.model,
            "error": _friendly_error_message(
                self.provider_name,
                self.model,
                status_code=status_code,
                raw_message=raw_message,
            ),
        }


class GeminiProvider(BaseAIProvider):
    """Wrapper around the internal Gemini implementation."""

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        self._require_api_key()
        from gemini_client import GeminiClient

        client = GeminiClient(api_key=self.api_key, model=self.model, allow_fallback=False)
        return client.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def test_connection(self) -> Dict:
        self._require_api_key()
        started_at = perf_counter()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": "Reply with OK"}]}],
            "generationConfig": {"maxOutputTokens": 1, "temperature": 0},
        }
        try:
            response = requests.post(
                url,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                _log_validation_latency(self.provider_name, self.model, started_at)
                return self._validation_success()
            status_code, error_message = _extract_http_error(response)
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(error_message, status_code=status_code)
        except requests.RequestException as exc:
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(str(exc))


class ClaudeProvider(BaseAIProvider):
    """Direct Anthropic SDK provider."""

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        self._require_api_key()
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        )

        content = _extract_openai_like_content(getattr(response, "content", []))
        if not content:
            raise RuntimeError("Claude returned empty content.")
        return content

    def test_connection(self) -> Dict:
        self._require_api_key()
        started_at = perf_counter()
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=self.api_key)
            client.messages.create(
                model=self.model,
                max_tokens=1,
                temperature=0,
                messages=[{"role": "user", "content": [{"type": "text", "text": "OK"}]}],
            )
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_success()
        except Exception as exc:
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(str(exc))


class OpenAIProvider(BaseAIProvider):
    """Direct OpenAI SDK provider."""

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        self._require_api_key()
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.model.startswith("o1"):
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature

        response = client.chat.completions.create(**payload)
        message = response.choices[0].message if response.choices else None
        content = _extract_openai_like_content(getattr(message, "content", ""))
        if not content:
            raise RuntimeError("OpenAI returned empty content.")
        return content

    def test_connection(self) -> Dict:
        self._require_api_key()
        started_at = perf_counter()
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": "OK"}],
            }
            if self.model.startswith("o1"):
                payload["max_completion_tokens"] = 1
            else:
                payload["max_tokens"] = 1
                payload["temperature"] = 0
            client.chat.completions.create(**payload)
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_success()
        except Exception as exc:
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(str(exc))


class OpenRouterProvider(BaseAIProvider):
    """Direct OpenRouter REST provider."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_REFERER,
            "X-Title": OPENROUTER_TITLE,
        }

    def _post(self, payload: Dict[str, Any]) -> requests.Response:
        return requests.post(
            self.BASE_URL,
            headers=self._headers(),
            json=payload,
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        self._require_api_key()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            response = self._post(payload)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(_friendly_error_message(self.provider_name, self.model, raw_message=str(exc))) from exc

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter returned no choices.")
        content = _extract_openai_like_content(
            choices[0].get("message", {}).get("content", "")
        )
        if not content:
            raise RuntimeError("OpenRouter returned empty content.")
        return content

    def test_connection(self) -> Dict:
        self._require_api_key()
        started_at = perf_counter()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "OK"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        try:
            response = self._post(payload)
            if response.status_code == 200:
                _log_validation_latency(self.provider_name, self.model, started_at)
                return self._validation_success()
            status_code, error_message = _extract_http_error(response)
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(error_message, status_code=status_code)
        except requests.RequestException as exc:
            _log_validation_latency(self.provider_name, self.model, started_at)
            return self._validation_failure(str(exc))


PROVIDER_CLASS_MAP = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "grok": OpenRouterProvider,
    "groq": OpenRouterProvider,
    "deepseek": OpenRouterProvider,
    "minimax": OpenRouterProvider,
    "glm": OpenRouterProvider,
    "nvidia": OpenRouterProvider,
}


def list_providers() -> List[Dict]:
    """Return the provider catalog for settings UIs."""
    return [
        {
            "id": provider_id,
            "display_name": meta["display_name"],
            "models": [dict(model) for model in meta["models"]],
            "default_model": meta["default_model"],
            "get_key_url": meta["get_key_url"],
            "key_format_hint": meta["key_format_hint"],
            "status": meta["status"],
        }
        for provider_id, meta in PROVIDER_CATALOG.items()
    ]


def get_provider(
    name: str = "gemini",
    api_key: str = "",
    model: str = "",
) -> BaseAIProvider:
    """Return an instantiated provider client for the requested provider."""
    provider_name = _normalize_provider_name(name)
    provider_cls = PROVIDER_CLASS_MAP[provider_name]
    resolved_model = model or PROVIDER_CATALOG[provider_name]["default_model"]
    return provider_cls(
        provider_name=provider_name,
        api_key=api_key,
        model=resolved_model,
    )


def test_ai_key(provider: str, api_key: str, model: str = "") -> Dict:
    """Validate a provider key with a real minimal API call."""
    provider_name = _normalize_provider_name(provider)
    resolved_model = model or PROVIDER_CATALOG[provider_name]["default_model"]
    if not api_key.strip():
        return {
            "valid": False,
            "provider": provider_name,
            "model": resolved_model,
            "error": "No API key was provided.",
        }
    client = get_provider(
        name=provider_name,
        api_key=api_key.strip(),
        model=resolved_model,
    )
    return client.test_connection()


def _generate_with_retry(
    provider_name: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    retries: int = 3,
) -> str:
    provider = get_provider(name=provider_name, api_key=api_key, model=model)
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            return provider.generate(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            last_error = _friendly_error_message(provider_name, model, raw_message=str(exc))
            logger.warning(
                "AI generation failed provider=%s model=%s attempt=%d/%d error=%s",
                provider_name,
                model,
                attempt,
                retries,
                last_error,
            )
            if attempt < retries:
                sleep(min(attempt, 2))
    raise AIProviderError(provider_name, model, last_error)


def generate(
    prompt: str,
    user_config: Any,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """
    Unified provider entry point used by the engine.

    Applies retries and optional provider fallback before surfacing a user-safe
    error back to the caller.
    """
    provider_name = _resolve_provider_name(user_config)
    model = _resolve_model(user_config, provider_name)
    api_key = _resolve_api_key(user_config, provider_name)

    primary_error: Optional[AIProviderError] = None
    try:
        return _generate_with_retry(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except AIProviderError as exc:
        primary_error = exc

    fallback_provider = _resolve_fallback_provider_name(user_config)
    if fallback_provider:
        fallback_model = PROVIDER_CATALOG[fallback_provider]["default_model"]
        fallback_key = _resolve_api_key(user_config, fallback_provider)
        try:
            logger.warning(
                "Primary AI provider failed; trying fallback provider=%s fallback=%s",
                provider_name,
                fallback_provider,
            )
            return _generate_with_retry(
                provider_name=fallback_provider,
                api_key=fallback_key,
                model=fallback_model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except AIProviderError as fallback_exc:
            message = (
                f"Your main AI provider failed ({primary_error.user_message}). "
                f"The backup provider also failed ({fallback_exc.user_message})."
            )
            raise AIProviderError(
                provider=provider_name,
                model=model,
                message=message,
                fallback_provider=fallback_provider,
            ) from fallback_exc

    if primary_error is not None:
        raise primary_error
    raise AIProviderError(provider_name, model, "The AI provider could not complete the request.")
