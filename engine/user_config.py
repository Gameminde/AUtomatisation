"""Per-user runtime configuration loaded from managed_pages + user_settings."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List

import config

logger = logging.getLogger("user_config")


def _normalize_country_code(value: str | None) -> str:
    candidate = (value or config.DEFAULT_COUNTRY_CODE).strip().upper()
    if candidate in config.TARGET_POSTING_PRESETS:
        return candidate
    return config.DEFAULT_COUNTRY_CODE


def _normalize_language_code(value: str | None, fallback: str = "en") -> str:
    candidate = (value or "").strip().lower()
    if candidate in config.SUPPORTED_LANGUAGE_CODES:
        return candidate
    return fallback


def _parse_csv_list(raw_value: str | None, fallback: list[str]) -> List[str]:
    tokens = [token.strip().lower() for token in str(raw_value or "").split(",") if token.strip()]
    normalized: List[str] = []
    for token in tokens:
        if token in config.SUPPORTED_LANGUAGE_CODES and token not in normalized:
            normalized.append(token)
    return normalized or list(fallback)


def _parse_csv_strings(raw_value: str | None, fallback: list[str] | None = None) -> List[str]:
    values = [token.strip() for token in str(raw_value or "").split(",") if token.strip()]
    if values:
        return values
    return list(fallback or [])


def _get_locale_preset(country_code: str) -> dict:
    return config.TARGET_POSTING_PRESETS.get(
        country_code,
        config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE],
    )


@dataclass
class UserConfig:
    """All runtime settings for one tenant."""

    user_id: str
    ai_provider: str = "gemini"
    provider_fallback: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    gemini_api_key: str = ""
    facebook_access_token: str = ""
    facebook_page_id: str = ""
    instagram_account_id: str = ""
    newsdata_api_key: str = ""
    pexels_api_key: str = ""
    posts_per_day: int = 3
    posting_times: str = config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE]["posting_times"]
    country_code: str = config.DEFAULT_COUNTRY_CODE
    timezone: str = config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE]["timezone"]
    ui_language: str = "en"
    content_language: str = "en"
    content_languages: List[str] = field(default_factory=lambda: ["en"])
    content_tone: str = "professional"
    content_dialect: str = ""
    content_mode: str = "single_language"
    language_ratio: float = 0.7
    telegram_chat_id: str = ""
    niche_keywords: List[str] = field(default_factory=list)
    rss_feed_urls: List[str] = field(default_factory=list)
    source_preset: str = config.DEFAULT_COUNTRY_CODE
    niche_preset: str = ""
    brand_color: str = "#F9C74F"

    @classmethod
    def from_db(cls, user_id: str) -> "UserConfig":
        """
        Load config for a user from managed_pages + user_settings.

        Falls back to env vars for keys that are not stored in the DB.
        Never raises; returns a minimally-populated instance on any error.
        """
        try:
            from app.utils import (
                get_ai_key_for_user,
                get_gemini_key_for_user,
                get_user_settings,
                load_tokens_for_user,
            )

            tokens = load_tokens_for_user(user_id) or {}
            settings = get_user_settings(user_id)
            country_code = _normalize_country_code(settings.get("country_code"))
            locale_preset = _get_locale_preset(country_code)
            timezone_name = settings.get("timezone") or locale_preset["timezone"]
            ai_provider = (settings.get("ai_provider") or "gemini").strip().lower() or "gemini"
            provider_fallback = (settings.get("provider_fallback") or "").strip().lower()
            ai_model = (settings.get("ai_model") or "").strip()
            ai_api_key = get_ai_key_for_user(user_id) or ""
            gemini_key = get_gemini_key_for_user(user_id) or ""

            default_posting_times = locale_preset["posting_times"]
            default_posts_per_day = len(
                [token for token in default_posting_times.split(",") if token.strip()]
            )
            posts_per_day_final = int(
                tokens.get("posts_per_day")
                or settings.get("posts_per_day")
                or default_posts_per_day
            )
            posting_times_final = (
                tokens.get("posting_times")
                or settings.get("posting_times")
                or default_posting_times
            )

            newsdata_key = (
                settings.get("newsdata_api_key")
                or os.getenv("NEWSDATA_API_KEY", "")
            )
            pexels_key = (
                settings.get("pexels_api_key")
                or os.getenv("PEXELS_API_KEY", "")
            )

            raw_kw = settings.get("niche_keywords") or ""
            niche_kw: List[str] = (
                [k.strip() for k in raw_kw.split(",") if k.strip()]
                if raw_kw
                else []
            )
            source_preset = (
                settings.get("source_preset")
                or country_code
            )
            source_config = config.CONTENT_SOURCE_PRESETS.get(
                str(source_preset).strip().upper(),
                config.CONTENT_SOURCE_PRESETS[country_code],
            )
            rss_feed_urls = _parse_csv_strings(
                settings.get("rss_feed_urls"),
                fallback=source_config["local_rss_feeds"],
            )
            niche_preset = str(settings.get("niche_preset") or "").strip().lower()
            if not niche_kw and niche_preset in config.NICHE_KEYWORD_PRESETS:
                niche_kw = list(config.NICHE_KEYWORD_PRESETS[niche_preset]["keywords"])

            preset_languages = [
                token.strip().lower()
                for token in locale_preset["default_content_languages"].split(",")
                if token.strip()
            ]
            content_languages = _parse_csv_list(
                settings.get("content_languages"),
                fallback=preset_languages,
            )
            content_language = _normalize_language_code(
                settings.get("content_language")
                or tokens.get("page_language")
                or (content_languages[0] if content_languages else None)
                or locale_preset["default_content_language"],
                fallback=locale_preset["default_content_language"],
            )
            if content_language not in content_languages:
                content_languages.insert(0, content_language)
            content_mode = (
                settings.get("content_mode")
                or ("mixed" if len(content_languages) > 1 else "single_language")
            )

            return cls(
                user_id=user_id,
                ai_provider=ai_provider,
                provider_fallback=provider_fallback,
                ai_model=ai_model,
                ai_api_key=ai_api_key,
                gemini_api_key=gemini_key,
                facebook_access_token=tokens.get("page_token", ""),
                facebook_page_id=tokens.get("page_id", ""),
                instagram_account_id=tokens.get("instagram_account_id", ""),
                newsdata_api_key=newsdata_key,
                pexels_api_key=pexels_key,
                posts_per_day=posts_per_day_final,
                posting_times=posting_times_final,
                country_code=country_code,
                timezone=timezone_name,
                ui_language=_normalize_language_code(
                    settings.get("ui_language"),
                    fallback="en",
                ),
                content_language=content_language,
                content_languages=content_languages,
                content_tone=(
                    settings.get("content_tone")
                    or locale_preset["default_content_tone"]
                ),
                content_dialect=(
                    settings.get("content_dialect")
                    or ""
                ),
                content_mode=content_mode,
                language_ratio=float(settings.get("language_ratio") or 0.7),
                telegram_chat_id=settings.get("telegram_chat_id") or "",
                niche_keywords=niche_kw,
                rss_feed_urls=rss_feed_urls,
                source_preset=source_config["id"],
                niche_preset=niche_preset,
                brand_color=str(settings.get("brand_color") or "#F9C74F"),
            )
        except Exception as exc:
            logger.error("UserConfig.from_db failed for user %s: %s", user_id[:8], exc)
            return cls(user_id=user_id)

    def is_configured(self) -> bool:
        """Return True if the user has the minimum config to run the pipeline."""
        return bool(
            (self.ai_api_key or self.gemini_api_key)
            and self.facebook_access_token
            and self.facebook_page_id
        )


def get_user_config(user_id: str) -> UserConfig:
    """Return a request-cached UserConfig when a Flask context is active."""
    try:
        from flask import g

        cache_key = f"_user_config_{user_id}"
        cached = getattr(g, cache_key, None)
        if cached is not None:
            return cached
    except RuntimeError:
        cache_key = None

    resolved = UserConfig.from_db(user_id)

    if cache_key is not None:
        try:
            from flask import g

            setattr(g, cache_key, resolved)
        except RuntimeError:
            pass

    return resolved
