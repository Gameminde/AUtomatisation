"""Per-user runtime configuration loaded from Supabase."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("user_config")


@dataclass
class UserConfig:
    """All runtime settings for one tenant, resolved from Supabase."""

    user_id: str
    gemini_api_key: str = ""
    facebook_access_token: str = ""
    facebook_page_id: str = ""
    instagram_account_id: str = ""
    posts_per_day: int = 3
    posting_times: str = "08:00,13:00,19:00"
    telegram_chat_id: str = ""
    pexels_api_key: str = ""
    niche_keywords: List[str] = field(default_factory=list)

    @classmethod
    def from_db(cls, user_id: str) -> "UserConfig":
        """Load config for a user from managed_pages + user_settings."""
        try:
            from app.utils import (
                get_gemini_key_for_user,
                get_user_settings,
                load_tokens_for_user,
            )

            tokens = load_tokens_for_user(user_id) or {}
            settings = get_user_settings(user_id)
            gemini_key = get_gemini_key_for_user(user_id) or ""

            return cls(
                user_id=user_id,
                gemini_api_key=gemini_key,
                facebook_access_token=tokens.get("page_token", ""),
                facebook_page_id=tokens.get("page_id", ""),
                instagram_account_id=tokens.get("instagram_account_id", ""),
                posts_per_day=int(settings.get("posts_per_day") or 3),
                posting_times=settings.get("posting_times") or "08:00,13:00,19:00",
                telegram_chat_id=settings.get("telegram_chat_id") or "",
                pexels_api_key=settings.get("pexels_api_key") or "",
            )
        except Exception as exc:
            logger.error("UserConfig.from_db failed for user %s: %s", user_id[:8], exc)
            return cls(user_id=user_id)

    def is_configured(self) -> bool:
        """Return True if the user has enough config to run the pipeline."""
        return bool(
            self.gemini_api_key
            and self.facebook_access_token
            and self.facebook_page_id
        )
