"""
ai_provider — Multi-provider AI client stub.
Routes to gemini_client or openrouter_client based on configuration.
"""
import os
from typing import Dict, List
import config

logger = config.get_logger("ai_provider")


class _Provider:
    def __init__(self, name: str, available: bool, reason: str = ""):
        self.name = name
        self.available = available
        self.reason = reason

    def test_connection(self) -> Dict:
        if not self.available:
            return {"ok": False, "provider": self.name, "error": self.reason}
        try:
            from gemini_client import get_ai_client
            client = get_ai_client()
            resp = client.generate("Say 'ok'", max_tokens=10)
            return {"ok": bool(resp), "provider": self.name}
        except Exception as e:
            return {"ok": False, "provider": self.name, "error": str(e)}


def list_providers() -> List[Dict]:
    return [
        {"id": "gemini", "name": "Google Gemini", "available": bool(os.getenv("GEMINI_API_KEY")), "description": "Fast, free tier available"},
        {"id": "openrouter", "name": "OpenRouter", "available": bool(os.getenv("OPENROUTER_API_KEY")), "description": "Multi-model access"},
    ]


def get_provider(name: str = "gemini") -> _Provider:
    providers = {p["id"]: p for p in list_providers()}
    info = providers.get(name, {"id": name, "available": False})
    return _Provider(name=name, available=info.get("available", False), reason="API key not set" if not info.get("available") else "")
