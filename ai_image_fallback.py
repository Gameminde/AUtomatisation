"""
ai_image_fallback — AI image generation fallback stub.
Full implementation arrives in Phase 4.
"""
from typing import Dict
import config

logger = config.get_logger("ai_image_fallback")


class _AIImageFallback:
    def get_status(self) -> Dict:
        return {"available": False, "reason": "AI image module not yet implemented", "providers": []}

    def generate(self, prompt: str, **kwargs) -> str:
        logger.warning("ai_image_fallback: generate called (stub)")
        return ""


_fallback = _AIImageFallback()


def get_fallback() -> _AIImageFallback:
    return _fallback
