"""
Gemini AI Client - Default AI provider for Content Factory v2.0 Gumroad.

Features:
- Google Gemini API (free tier: 60 req/min, 1500/day)
- Automatic fallback to OpenRouter if Gemini fails
- Simple configuration: just GEMINI_API_KEY
- Image generation support via Imagen (experimental)

Usage:
    from gemini_client import get_ai_client
    client = get_ai_client()
    response = client.generate("Your prompt here")
"""

from __future__ import annotations

import json
import time
from typing import Optional

import requests

import config

logger = config.get_logger("gemini_client")


class GeminiClient:
    """
    Google Gemini AI client with automatic fallback.
    
    Priority:
    1. Gemini API (free, fast)
    2. OpenRouter (fallback if Gemini unavailable)
    """
    
    # Gemini API endpoints
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_MODEL = "gemini-1.5-flash"  # Fast and free
    
    def __init__(self):
        """Initialize Gemini client."""
        self.gemini_key = config.GEMINI_API_KEY
        self.openrouter_available = bool(config.OPENROUTER_API_KEYS and any(config.OPENROUTER_API_KEYS))
        
        if self.gemini_key:
            logger.info("✅ Gemini API configured (primary)")
        elif self.openrouter_available:
            logger.info("✅ OpenRouter configured (fallback)")
        else:
            logger.warning("⚠️ No AI API configured - content generation will fail")
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate content using Gemini (or fallback to OpenRouter).
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum response tokens
            temperature: Creativity (0.0-1.0)
        
        Returns:
            Generated text
        
        Raises:
            RuntimeError: If all providers fail
        """
        # Try Gemini first
        if self.gemini_key:
            try:
                return self._call_gemini(prompt, max_tokens, temperature)
            except Exception as e:
                logger.warning("Gemini failed, trying fallback: %s", e)
        
        # Fallback to OpenRouter
        if self.openrouter_available:
            try:
                from openrouter_client import OpenRouterClient
                client = OpenRouterClient()
                return client.call(prompt, max_tokens, temperature)
            except Exception as e:
                logger.error("OpenRouter fallback failed: %s", e)
        
        raise RuntimeError("All AI providers failed - check your API keys")
    
    def _call_gemini(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call Gemini API directly."""
        url = f"{self.GEMINI_BASE_URL}/models/{self.GEMINI_MODEL}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        params = {"key": self.gemini_key}
        
        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=config.HTTP_TIMEOUT_SECONDS + 10,  # Gemini can be slow
            )
            
            if response.status_code == 429:
                logger.warning("Gemini rate limit hit")
                raise RuntimeError("Gemini rate limit exceeded")
            
            if response.status_code != 200:
                error_msg = response.text[:200]
                logger.error("Gemini API error %d: %s", response.status_code, error_msg)
                raise RuntimeError(f"Gemini API error: {response.status_code}")
            
            data = response.json()
            
            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise RuntimeError("Gemini returned no content")
            
            text = parts[0].get("text", "")
            if not text:
                raise RuntimeError("Gemini returned empty text")
            
            logger.info("✅ Gemini response: %d chars", len(text))
            return text
            
        except requests.RequestException as e:
            logger.error("Gemini request failed: %s", e)
            raise RuntimeError(f"Gemini request failed: {e}")
    
    def test_connection(self) -> dict:
        """
        Test AI connection and return status.
        
        Returns:
            Dict with provider status
        """
        status = {
            "gemini": {"available": False, "error": None},
            "openrouter": {"available": False, "error": None},
            "primary": None
        }
        
        # Test Gemini
        if self.gemini_key:
            try:
                response = self.generate("Say 'Hello' in Arabic. Reply with just one word.", max_tokens=50)
                if response:
                    status["gemini"]["available"] = True
                    status["primary"] = "gemini"
                    logger.info("✅ Gemini test passed: %s", response.strip()[:20])
            except Exception as e:
                status["gemini"]["error"] = str(e)
                logger.warning("❌ Gemini test failed: %s", e)
        
        # Test OpenRouter
        if self.openrouter_available and not status["gemini"]["available"]:
            try:
                from openrouter_client import OpenRouterClient
                client = OpenRouterClient()
                response = client.call("Say 'Hello' in Arabic. Reply with just one word.", max_tokens=50)
                if response:
                    status["openrouter"]["available"] = True
                    status["primary"] = "openrouter"
                    logger.info("✅ OpenRouter test passed: %s", response.strip()[:20])
            except Exception as e:
                status["openrouter"]["error"] = str(e)
                logger.warning("❌ OpenRouter test failed: %s", e)
        
        return status


# Global instance
_client: Optional[GeminiClient] = None


def get_ai_client() -> GeminiClient:
    """Get or create the global AI client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def generate_content(prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
    """Quick access to generate content."""
    return get_ai_client().generate(prompt, max_tokens, temperature)


def test_ai_connection() -> dict:
    """Test AI connection and return status."""
    return get_ai_client().test_connection()


if __name__ == "__main__":
    print("🤖 Testing Gemini Client...\n")
    
    client = GeminiClient()
    status = client.test_connection()
    
    print("📊 Connection Status:")
    print(f"  Primary: {status['primary'] or 'None'}")
    print(f"  Gemini: {'✅' if status['gemini']['available'] else '❌'}")
    if status['gemini']['error']:
        print(f"    Error: {status['gemini']['error']}")
    print(f"  OpenRouter: {'✅' if status['openrouter']['available'] else '❌'}")
    if status['openrouter']['error']:
        print(f"    Error: {status['openrouter']['error']}")
    
    if status['primary']:
        print(f"\n✅ AI ready with {status['primary']}")
    else:
        print("\n❌ No AI provider available - check API keys")
