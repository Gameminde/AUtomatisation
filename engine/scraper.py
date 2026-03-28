"""Collect and filter tech news from locale-aware sources."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Iterable, List, Optional

import feedparser
import requests

import config

logger = config.get_logger("scraper")


_DEFAULT_RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://news.mit.edu/rss/topic/technology",
]


def _unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def get_source_preset(
    source_preset: Optional[str] = None,
    country_code: Optional[str] = None,
) -> dict:
    normalized_country = (
        source_preset
        or country_code
        or config.DEFAULT_COUNTRY_CODE
    ).strip().upper()
    return config.CONTENT_SOURCE_PRESETS.get(
        normalized_country,
        config.CONTENT_SOURCE_PRESETS[config.DEFAULT_COUNTRY_CODE],
    )


def normalize_languages(languages: Optional[Iterable[str]]) -> List[str]:
    normalized: List[str] = []
    for value in languages or []:
        code = str(value or "").strip().lower()
        if code in config.SUPPORTED_LANGUAGE_CODES and code not in normalized:
            normalized.append(code)
    return normalized


def resolve_newsdata_languages(
    content_languages: Optional[Iterable[str]] = None,
    country_code: Optional[str] = None,
) -> List[str]:
    resolved = normalize_languages(content_languages)
    if resolved:
        return resolved

    locale_preset = config.TARGET_POSTING_PRESETS.get(
        (country_code or config.DEFAULT_COUNTRY_CODE).strip().upper(),
        config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE],
    )
    return normalize_languages(locale_preset["default_content_languages"].split(","))


def normalize_country_filters(
    source_preset: Optional[str] = None,
    country_code: Optional[str] = None,
) -> List[str]:
    preset = get_source_preset(source_preset=source_preset, country_code=country_code)
    return [code.lower() for code in preset["newsdata_countries"]]


def get_feeds(
    user_feeds: Optional[Iterable[str]] = None,
    content_languages: Optional[Iterable[str]] = None,
    source_preset: Optional[str] = None,
    country_code: Optional[str] = None,
) -> List[str]:
    """Resolve RSS feeds using language preference first, then locale."""
    resolved_languages = resolve_newsdata_languages(
        content_languages=content_languages,
        country_code=country_code,
    )
    language_feeds: List[str] = []
    for language_code in resolved_languages:
        language_feeds.extend(
            config.LANGUAGE_SOURCE_PRESETS.get(language_code, {}).get("rss_feeds", [])
        )

    env_val = os.environ.get("RSS_FEED_URLS", "").strip()
    env_feeds = env_val.split(",") if env_val else []

    preset = get_source_preset(source_preset=source_preset, country_code=country_code)
    return _unique_preserve_order(
        [
            *(user_feeds or []),
            *language_feeds,
            *preset["local_rss_feeds"],
            *env_feeds,
            *_DEFAULT_RSS_FEEDS,
        ]
    )


def set_feeds(urls: List[str]) -> None:
    """Update RSS_FEED_URLS in the runtime environment."""
    os.environ["RSS_FEED_URLS"] = ",".join(urls)


# Keep module-level name for backward compatibility
RSS_FEEDS = get_feeds()


def fetch_newsdata_articles(
    api_key: Optional[str] = None,
    languages: Optional[Iterable[str]] = None,
    countries: Optional[Iterable[str]] = None,
) -> List[dict]:
    """Fetch articles from NewsData.io using locale-aware parameters."""
    effective_key = api_key or config.NEWSDATA_API_KEY
    if not effective_key:
        logger.warning("NEWSDATA_API_KEY not set; skipping NewsData.io")
        return []

    resolved_languages = normalize_languages(languages) or list(
        resolve_newsdata_languages(country_code=config.DEFAULT_COUNTRY_CODE)
    )
    resolved_countries = [code.lower() for code in (countries or normalize_country_filters())]

    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": effective_key,
        "category": "technology",
        "language": ",".join(resolved_languages),
    }
    if resolved_countries:
        params["country"] = ",".join(resolved_countries)
    try:
        resp = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("NewsData.io request failed: %s", exc)
        return []

    data = resp.json()
    results = data.get("results", [])
    items: List[dict] = []
    for item in results:
        items.append(
            {
                "source_name": item.get("source_id") or "newsdata",
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "content": item.get("description") or item.get("content"),
                "published_date": item.get("pubDate"),
            }
        )
    return items


def fetch_rss_feed(url: str) -> List[dict]:
    """Fetch articles from an RSS feed."""
    feed = feedparser.parse(url)
    items: List[dict] = []
    for entry in feed.entries:
        items.append(
            {
                "source_name": feed.feed.get("title", "rss"),
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "content": entry.get("summary", ""),
                "published_date": entry.get("published", ""),
            }
        )
    return items


def fetch_hackernews_top(limit: int = 20) -> List[dict]:
    """Fetch top stories from Hacker News."""
    base_url = "https://hacker-news.firebaseio.com/v0"
    try:
        resp = requests.get(
            f"{base_url}/topstories.json",
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Hacker News request failed: %s", exc)
        return []

    ids = resp.json()[:limit]
    items: List[dict] = []
    for story_id in ids:
        try:
            story_resp = requests.get(
                f"{base_url}/item/{story_id}.json",
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
            story_resp.raise_for_status()
        except requests.RequestException:
            continue

        story = story_resp.json() or {}
        if story.get("type") != "story":
            continue
        items.append(
            {
                "source_name": "hackernews",
                "title": story.get("title", ""),
                "url": story.get("url", ""),
                "content": story.get("text", ""),
                "published_date": datetime.utcfromtimestamp(
                    story.get("time", 0)
                ).isoformat(),
            }
        )
    return items


def keyword_match(text: str, keywords: Iterable[str]) -> bool:
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def filter_articles(items: Iterable[dict], keywords: Iterable[str]) -> List[dict]:
    filtered: List[dict] = []
    for item in items:
        blob = f"{item.get('title', '')} {item.get('content', '')}"
        if keyword_match(blob, keywords):
            filtered.append(item)
    return filtered


def score_virality(item: dict) -> int:
    """Simple heuristic score using title length, freshness, and source."""
    title = item.get("title", "")
    score = min(len(title), 120) // 10
    source = (item.get("source_name") or "").lower()
    if "techcrunch" in source:
        score += 3
    if "verge" in source:
        score += 2
    return int(score)


def dedupe_by_url(items: Iterable[dict]) -> List[dict]:
    seen = set()
    unique: List[dict] = []
    for item in items:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique


def save_articles(
    items: Iterable[dict],
    user_id: Optional[str] = None,
    keywords: Optional[List[str]] = None,
) -> int:
    """Save scraped articles to raw_articles."""
    client = config.get_database_client()
    kw_list = keywords or config.DEFAULT_KEYWORDS
    saved = 0
    for item in items:
        url = item.get("url")
        if not url:
            continue
        try:
            query = client.table("raw_articles").select("id").eq("url", url)
            if user_id:
                query = query.eq("user_id", user_id)
            existing = query.execute()
            if existing.data:
                continue
        except Exception as exc:
            logger.warning("Supabase check failed for %s: %s", url, exc)

        payload = {
            "source_name": item.get("source_name"),
            "title": item.get("title"),
            "url": url,
            "content": item.get("content"),
            "published_date": item.get("published_date"),
            "keywords": kw_list,
            "virality_score": score_virality(item),
            "status": "pending",
        }
        if user_id:
            payload["user_id"] = user_id
        try:
            client.table("raw_articles").insert(payload).execute()
            saved += 1
        except Exception as exc:
            logger.error("Supabase insert failed for %s: %s", url, exc)
    return saved


def run(
    user_id: Optional[str] = None,
    newsdata_api_key: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    content_languages: Optional[Iterable[str]] = None,
    country_code: Optional[str] = None,
    source_preset: Optional[str] = None,
    rss_feeds: Optional[Iterable[str]] = None,
) -> int:
    """Run the full scrape pipeline with language-first source discovery."""
    filter_kw = keywords or config.DEFAULT_KEYWORDS
    resolved_languages = resolve_newsdata_languages(
        content_languages=content_languages,
        country_code=country_code,
    )
    resolved_countries = normalize_country_filters(
        source_preset=source_preset,
        country_code=country_code,
    )
    resolved_feeds = get_feeds(
        user_feeds=rss_feeds,
        content_languages=resolved_languages,
        source_preset=source_preset,
        country_code=country_code,
    )

    items: List[dict] = []
    items.extend(
        fetch_newsdata_articles(
            api_key=newsdata_api_key,
            languages=resolved_languages,
            countries=resolved_countries,
        )
    )
    for rss_url in resolved_feeds:
        items.extend(fetch_rss_feed(rss_url))
        time.sleep(config.REQUEST_SLEEP_SECONDS)
    items.extend(fetch_hackernews_top())

    filtered = filter_articles(items, filter_kw)
    unique = dedupe_by_url(filtered)
    saved = save_articles(unique, user_id=user_id, keywords=filter_kw)
    logger.info(
        "Scraper saved %s new articles (user_id=%s, country=%s, languages=%s)",
        saved,
        user_id,
        country_code,
        resolved_languages or "default",
    )
    return saved


def run_for_user(user_config: "UserConfig") -> int:  # type: ignore[name-defined]
    """Run the full scrape pipeline for a single tenant using a UserConfig object."""
    return run(
        user_id=user_config.user_id,
        newsdata_api_key=user_config.newsdata_api_key or None,
        keywords=user_config.niche_keywords or None,
        content_languages=user_config.content_languages or [user_config.content_language],
        country_code=user_config.country_code,
        source_preset=user_config.source_preset or user_config.country_code,
        rss_feeds=user_config.rss_feed_urls or None,
    )


if __name__ == "__main__":
    run()
