"""Collect and filter tech news from free sources."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Iterable, List

import feedparser
import requests

import config

logger = config.get_logger("scraper")


_DEFAULT_RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://news.mit.edu/rss/topic/technology",
]


def get_feeds() -> List[str]:
    """Get current RSS feed URLs from env or defaults."""
    env_val = os.environ.get("RSS_FEED_URLS", "").strip()
    if env_val:
        return [u.strip() for u in env_val.split(",") if u.strip()]
    return list(_DEFAULT_RSS_FEEDS)


def set_feeds(urls: List[str]) -> None:
    """Update RSS_FEED_URLS in the runtime environment."""
    os.environ["RSS_FEED_URLS"] = ",".join(urls)


# Keep module-level name for backward compatibility
RSS_FEEDS = get_feeds()


def fetch_newsdata_articles(api_key: Optional[str] = None) -> List[dict]:
    """Fetch articles from NewsData.io.

    Args:
        api_key: NewsData.io API key to use. Falls back to config.NEWSDATA_API_KEY
                 when not provided. Pass a per-user key for multi-tenant isolation
                 (avoids mutating module globals in a threaded environment).
    """
    effective_key = api_key or config.NEWSDATA_API_KEY
    if not effective_key:
        logger.warning("NEWSDATA_API_KEY not set; skipping NewsData.io")
        return []

    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": effective_key,
        "category": "technology",
        "language": "en",
        "country": "us,gb,ca",
    }
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
        resp = requests.get(f"{base_url}/topstories.json", timeout=config.HTTP_TIMEOUT_SECONDS)
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
                "published_date": datetime.utcfromtimestamp(story.get("time", 0)).isoformat(),
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
    """Save scraped articles to raw_articles.

    Per-tenant isolation: when user_id is provided, the deduplication check
    is scoped to that user so two tenants can both ingest the same URL
    independently.

    Args:
        items:    Iterable of article dicts from fetch_* functions.
        user_id:  Tenant ID — tag each row so the article belongs to a specific user.
                  Required for multi-tenant operation; None only in single-user dev mode.
        keywords: Override list of keywords to store on the row (per-user niche).
                  Falls back to config.DEFAULT_KEYWORDS when not supplied.
    """
    client = config.get_supabase_client()
    kw_list = keywords or config.DEFAULT_KEYWORDS
    saved = 0
    for item in items:
        url = item.get("url")
        if not url:
            continue
        try:
            # Per-tenant deduplication: scope by user_id when available so
            # different users can independently process the same URL.
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
) -> int:
    """Run the full scrape pipeline.

    Args:
        user_id:          Tenant ID — tags every saved row; required for
                          multi-tenant operation.
        newsdata_api_key: Per-user NewsData.io API key passed directly to
                          fetch_newsdata_articles() (no global mutation — safe
                          for concurrent threads).
        keywords:         Per-user keyword list for filtering; falls back to
                          config.DEFAULT_KEYWORDS when not provided.
    """
    filter_kw = keywords or config.DEFAULT_KEYWORDS

    items: List[dict] = []
    # Pass the per-user API key explicitly — no global state mutation
    items.extend(fetch_newsdata_articles(api_key=newsdata_api_key))
    for rss_url in get_feeds():
        items.extend(fetch_rss_feed(rss_url))
        time.sleep(config.REQUEST_SLEEP_SECONDS)
    items.extend(fetch_hackernews_top())

    filtered = filter_articles(items, filter_kw)
    unique = dedupe_by_url(filtered)
    saved = save_articles(unique, user_id=user_id, keywords=filter_kw)
    logger.info("Scraper saved %s new articles (user_id=%s)", saved, user_id)
    return saved


def run_for_user(user_config: "UserConfig") -> int:  # type: ignore[name-defined]
    """
    Run the full scrape pipeline for a single tenant using a UserConfig object.

    This is the preferred entry point for the multi-tenant pipeline runner.
    All per-user credentials and keyword preferences are extracted from
    ``user_config`` rather than environment variables.

    Parameters
    ----------
    user_config : UserConfig
        Fully-populated tenant configuration object.

    Returns
    -------
    int
        Number of new articles saved.
    """
    return run(
        user_id=user_config.user_id,
        newsdata_api_key=user_config.newsdata_api_key or None,
        keywords=user_config.niche_keywords or None,
    )


if __name__ == "__main__":
    run()
