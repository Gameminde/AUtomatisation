"""Collect and filter tech news from free sources."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Iterable, List

import feedparser
import requests

import config

logger = config.get_logger("scraper")


RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://news.mit.edu/rss/topic/technology",
]


def fetch_newsdata_articles() -> List[dict]:
    """Fetch articles from NewsData.io."""
    if not config.NEWSDATA_API_KEY:
        logger.warning("NEWSDATA_API_KEY not set; skipping NewsData.io")
        return []

    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": config.NEWSDATA_API_KEY,
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
    return any(keyword in text_lower for keyword in keywords)


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


def save_articles(items: Iterable[dict]) -> int:
    client = config.get_supabase_client()
    saved = 0
    for item in items:
        url = item.get("url")
        if not url:
            continue
        try:
            existing = (
                client.table("raw_articles")
                .select("id")
                .eq("url", url)
                .execute()
            )
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
            "keywords": config.DEFAULT_KEYWORDS,
            "virality_score": score_virality(item),
            "status": "pending",
        }
        try:
            client.table("raw_articles").insert(payload).execute()
            saved += 1
        except Exception as exc:
            logger.error("Supabase insert failed for %s: %s", url, exc)
    return saved


def run() -> int:
    items: List[dict] = []
    items.extend(fetch_newsdata_articles())
    for rss_url in RSS_FEEDS:
        items.extend(fetch_rss_feed(rss_url))
        time.sleep(config.REQUEST_SLEEP_SECONDS)
    items.extend(fetch_hackernews_top())

    filtered = filter_articles(items, config.DEFAULT_KEYWORDS)
    unique = dedupe_by_url(filtered)
    saved = save_articles(unique)
    logger.info("Scraper saved %s new articles", saved)
    return saved


if __name__ == "__main__":
    run()
