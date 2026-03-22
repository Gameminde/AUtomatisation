"""Per-user runtime configuration loaded from Supabase."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger("user_config")


@dataclass
class UserConfig:
    """
    All runtime settings for one tenant, resolved from Supabase.

    Fields
    ------
    user_id             : Supabase user UUID (required).
    gemini_api_key      : Per-user encrypted Gemini key (from user_settings).
    facebook_access_token : Decrypted page access token (from managed_pages).
    facebook_page_id    : Facebook page ID (from managed_pages).
    instagram_account_id: Linked Instagram Business Account ID.
    newsdata_api_key    : NewsData.io API key (from user_settings or env).
    pexels_api_key      : Pexels API key for stock images.
    posts_per_day       : Maximum posts per day (1-5, from user_settings).
    posting_times       : Comma-separated HH:MM slots, e.g. "08:00,13:00,19:00".
    language_ratio      : Fraction of Arabic content (0.0–1.0, default 0.7).
    telegram_chat_id    : Optional Telegram chat for notifications.
    niche_keywords      : Custom topic keywords for content filtering.
    """

    user_id: str
    gemini_api_key: str = ""
    facebook_access_token: str = ""
    facebook_page_id: str = ""
    instagram_account_id: str = ""
    newsdata_api_key: str = ""
    pexels_api_key: str = ""
    posts_per_day: int = 3
    posting_times: str = "08:00,13:00,19:00"
    language_ratio: float = 0.7
    telegram_chat_id: str = ""
    niche_keywords: List[str] = field(default_factory=list)

    @classmethod
    def from_db(cls, user_id: str) -> "UserConfig":
        """
        Load config for a user from managed_pages + user_settings.

        Falls back to env vars for keys that are not stored in the DB.
        Never raises — returns a minimally-populated instance on any error.
        """
        try:
            from app.utils import (
                get_gemini_key_for_user,
                get_user_settings,
                load_tokens_for_user,
            )

            tokens = load_tokens_for_user(user_id) or {}
            settings = get_user_settings(user_id)
            gemini_key = get_gemini_key_for_user(user_id) or ""

            # newsdata_api_key: per-user setting → env fallback
            newsdata_key = (
                settings.get("newsdata_api_key")
                or os.getenv("NEWSDATA_API_KEY", "")
            )
            # pexels_api_key: per-user setting → env fallback
            pexels_key = (
                settings.get("pexels_api_key")
                or os.getenv("PEXELS_API_KEY", "")
            )

            # niche_keywords: comma-separated string in DB → list
            raw_kw = settings.get("niche_keywords") or ""
            niche_kw: List[str] = (
                [k.strip() for k in raw_kw.split(",") if k.strip()]
                if raw_kw
                else []
            )

            return cls(
                user_id=user_id,
                gemini_api_key=gemini_key,
                facebook_access_token=tokens.get("page_token", ""),
                facebook_page_id=tokens.get("page_id", ""),
                instagram_account_id=tokens.get("instagram_account_id", ""),
                newsdata_api_key=newsdata_key,
                pexels_api_key=pexels_key,
                posts_per_day=int(settings.get("posts_per_day") or 3),
                posting_times=settings.get("posting_times") or "08:00,13:00,19:00",
                language_ratio=float(settings.get("language_ratio") or 0.7),
                telegram_chat_id=settings.get("telegram_chat_id") or "",
                niche_keywords=niche_kw,
            )
        except Exception as exc:
            logger.error("UserConfig.from_db failed for user %s: %s", user_id[:8], exc)
            return cls(user_id=user_id)

    def is_configured(self) -> bool:
        """Return True if the user has the minimum config to run the pipeline."""
        return bool(
            self.gemini_api_key
            and self.facebook_access_token
            and self.facebook_page_id
        )
