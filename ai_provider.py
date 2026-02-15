"""
AI Provider Factory - Unified client for multiple AI providers.

Supports: Gemini, OpenRouter, Claude, DeepSeek, Grok, Kimi K2, Ollama (local)

Usage:
    from ai_provider import get_provider, list_providers
    client = get_provider()          # Uses AI_PROVIDER env var
    client = get_provider("claude")  # Specific provider
    response = client.generate("Your prompt here")
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import requests

import config

logger = config.get_logger("ai_provider")

# ── Provider Registry ───────────────────────────────────
PROVIDERS: Dict[str, Dict] = {
    "gemini": {
        "name": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "free": True,
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "default_model": "gemini-2.0-flash",
        "help_url": "https://aistudio.google.com/app/apikey",
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "free": False,
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "meta-llama/llama-3-70b-instruct",
        "help_url": "https://openrouter.ai/keys",
    },
    "claude": {
        "name": "Anthropic Claude",
        "env_key": "CLAUDE_API_KEY",
        "free": False,
        "url": "https://api.anthropic.com/v1/messages",
        "default_model": "claude-sonnet-4-20250514",
        "help_url": "https://console.anthropic.com/settings/keys",
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "free": False,
        "url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "help_url": "https://platform.deepseek.com/api_keys",
    },
    "grok": {
        "name": "xAI Grok",
        "env_key": "GROK_API_KEY",
        "free": False,
        "url": "https://api.x.ai/v1/chat/completions",
        "default_model": "grok-3",
        "help_url": "https://console.x.ai",
    },
    "kimi": {
        "name": "Kimi K2",
        "env_key": "KIMI_API_KEY",
        "free": False,
        "url": "https://api.moonshot.cn/v1/chat/completions",
        "default_model": "kimi-k2",
        "help_url": "https://platform.moonshot.cn/console/api-keys",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "env_key": "",
        "free": True,
        "url": "http://localhost:11434/api/generate",
        "default_model": "llama3",
        "help_url": "https://ollama.ai/download",
    },
}


class AIClient:
    """Unified AI client with .generate() interface."""

    def __init__(self, provider: str, api_key: str = "", model: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.info = PROVIDERS.get(provider, {})
        self.model = model or self.info.get("default_model", "")
        self.base_url = os.getenv(
            f"{provider.upper()}_API_URL", self.info.get("url", "")
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate content using the configured provider."""
        method = getattr(self, f"_call_{self.provider}", None)
        if method is None:
            raise RuntimeError(f"Unknown provider: {self.provider}")
        return method(prompt, max_tokens, temperature)

    # ── Gemini ───────────────────────────────────────────
    def _call_gemini(self, prompt: str, max_tokens: int, temperature: float) -> str:
        url = self.base_url.format(model=self.model) + f"?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    # ── OpenAI-compatible (OpenRouter, DeepSeek, Grok, Kimi) ──
    def _call_openai_compat(self, prompt: str, max_tokens: int, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = requests.post(self.base_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_openrouter(self, prompt, max_tokens, temperature):
        return self._call_openai_compat(prompt, max_tokens, temperature)

    def _call_deepseek(self, prompt, max_tokens, temperature):
        return self._call_openai_compat(prompt, max_tokens, temperature)

    def _call_grok(self, prompt, max_tokens, temperature):
        return self._call_openai_compat(prompt, max_tokens, temperature)

    def _call_kimi(self, prompt, max_tokens, temperature):
        return self._call_openai_compat(prompt, max_tokens, temperature)

    # ── Claude (Anthropic) ───────────────────────────────
    def _call_claude(self, prompt: str, max_tokens: int, temperature: float) -> str:
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        resp = requests.post(self.base_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    # ── Ollama (Local) ───────────────────────────────────
    def _call_ollama(self, prompt: str, max_tokens: int, temperature: float) -> str:
        url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def test_connection(self) -> Dict:
        """Quick health check — generate a test response."""
        try:
            result = self.generate("Say 'OK' in one word.", max_tokens=10, temperature=0)
            return {"ok": True, "provider": self.provider, "response": result.strip()[:50]}
        except Exception as e:
            return {"ok": False, "provider": self.provider, "error": str(e)}


# ── Factory ──────────────────────────────────────────────

def get_provider(provider: Optional[str] = None) -> AIClient:
    """
    Get an AI client for the specified provider.

    Falls back to AI_PROVIDER env var, then tries Gemini → OpenRouter.
    """
    provider = (provider or os.getenv("AI_PROVIDER", "")).strip().lower()

    if provider and provider in PROVIDERS:
        info = PROVIDERS[provider]
        key = os.getenv(info["env_key"], "") if info["env_key"] else ""
        return AIClient(provider, api_key=key)

    # Auto-detect: try providers in order
    for name in ["gemini", "openrouter", "claude", "deepseek", "grok", "kimi", "ollama"]:
        info = PROVIDERS[name]
        if name == "ollama":
            # Check if Ollama is running
            try:
                requests.get("http://localhost:11434/api/tags", timeout=2)
                logger.info("Auto-detected Ollama (local)")
                return AIClient("ollama")
            except Exception:
                continue
        key = os.getenv(info["env_key"], "")
        if key:
            logger.info("Auto-detected provider: %s", info["name"])
            return AIClient(name, api_key=key)

    raise RuntimeError(
        "No AI provider configured. Set AI_PROVIDER and the corresponding API key in .env"
    )


def list_providers() -> List[Dict]:
    """List all available providers with configuration status."""
    result = []
    for name, info in PROVIDERS.items():
        configured = False
        if name == "ollama":
            try:
                requests.get("http://localhost:11434/api/tags", timeout=1)
                configured = True
            except Exception:
                pass
        else:
            configured = bool(os.getenv(info["env_key"], ""))
        result.append({
            "id": name,
            "name": info["name"],
            "configured": configured,
            "free": info["free"],
            "help_url": info["help_url"],
        })
    return result


if __name__ == "__main__":
    print("🤖 AI Provider Factory\n")
    for p in list_providers():
        status = "✅ Configured" if p["configured"] else "❌ Not set"
        free = " (FREE)" if p["free"] else ""
        print(f"  {p['name']}{free}: {status}")

    try:
        client = get_provider()
        print(f"\n🔌 Active provider: {client.provider}")
        result = client.test_connection()
        if result["ok"]:
            print(f"✅ Connection OK: {result['response']}")
        else:
            print(f"❌ Connection failed: {result['error']}")
    except RuntimeError as e:
        print(f"\n⚠️ {e}")
