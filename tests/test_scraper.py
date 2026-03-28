"""
Unit tests for scraper module.

Tests cover:
- RSS feed parsing
- NewsData.io API integration
- HackerNews API integration
- Keyword filtering
- Deduplication
- Virality scoring
- Database persistence
"""

# pytest used implicitly
from unittest.mock import MagicMock, patch
# datetime available if needed


class TestKeywordMatch:
    """Tests for keyword_match function."""

    def test_keyword_match_single_keyword(self):
        """Test matching a single keyword."""
        import scraper

        assert scraper.keyword_match("AI is revolutionizing tech", ["ai"]) is True
        assert scraper.keyword_match("New blockchain technology", ["blockchain"]) is True

    def test_keyword_match_case_insensitive(self):
        """Test case-insensitive matching."""
        import scraper

        assert scraper.keyword_match("AI is great", ["ai"]) is True
        assert scraper.keyword_match("ai is great", ["AI"]) is True
        assert scraper.keyword_match("Artificial Intelligence", ["artificial intelligence"]) is True

    def test_keyword_match_no_match(self):
        """Test no match scenario."""
        import scraper

        assert scraper.keyword_match("Random news about sports", ["ai", "blockchain"]) is False
        assert scraper.keyword_match("", ["ai"]) is False

    def test_keyword_match_multiple_keywords(self):
        """Test matching multiple keywords."""
        import scraper

        assert scraper.keyword_match("Startup innovation in AI", ["ai", "startup"]) is True
        assert scraper.keyword_match("New software update", ["software"]) is True


class TestFilterArticles:
    """Tests for filter_articles function."""

    def test_filter_articles_with_matches(self, sample_articles):
        """Test filtering articles with keyword matches."""
        import scraper

        keywords = ["ai", "openai"]
        filtered = scraper.filter_articles(sample_articles, keywords)

        # Should match article with "AI" in title/content
        assert len(filtered) >= 1

    def test_filter_articles_no_matches(self, sample_articles):
        """Test filtering with no matches."""
        import scraper

        keywords = ["sports", "football"]
        filtered = scraper.filter_articles(sample_articles, keywords)

        assert len(filtered) == 0

    def test_filter_articles_empty_input(self):
        """Test filtering empty list."""
        import scraper

        filtered = scraper.filter_articles([], ["ai"])
        assert filtered == []


class TestScoreVirality:
    """Tests for score_virality function."""

    def test_score_virality_techcrunch_source(self):
        """Test virality scoring for TechCrunch source."""
        import scraper

        item = {"title": "Breaking: AI Revolution", "source_name": "techcrunch"}
        score = scraper.score_virality(item)

        # TechCrunch gets +3 bonus
        assert score >= 3

    def test_score_virality_verge_source(self):
        """Test virality scoring for The Verge source."""
        import scraper

        item = {"title": "New Tech Announcement", "source_name": "the verge"}
        score = scraper.score_virality(item)

        # The Verge gets +2 bonus
        assert score >= 2

    def test_score_virality_long_title(self):
        """Test virality scoring with long title."""
        import scraper

        item = {"title": "A" * 100, "source_name": "unknown"}  # 100 character title
        score = scraper.score_virality(item)

        # Score based on title length (capped at 120)
        assert score >= 10


class TestDedupeByUrl:
    """Tests for dedupe_by_url function."""

    def test_dedupe_removes_duplicates(self):
        """Test that duplicate URLs are removed."""
        import scraper

        items = [
            {"url": "https://example.com/1", "title": "Article 1"},
            {"url": "https://example.com/2", "title": "Article 2"},
            {"url": "https://example.com/1", "title": "Article 1 Duplicate"},  # Duplicate
        ]

        unique = scraper.dedupe_by_url(items)

        assert len(unique) == 2
        assert unique[0]["url"] == "https://example.com/1"
        assert unique[1]["url"] == "https://example.com/2"

    def test_dedupe_handles_empty_urls(self):
        """Test handling of empty URLs."""
        import scraper

        items = [
            {"url": "", "title": "No URL"},
            {"url": "https://example.com/1", "title": "Article 1"},
            {"url": None, "title": "Null URL"},
        ]

        unique = scraper.dedupe_by_url(items)

        assert len(unique) == 1

    def test_dedupe_empty_list(self):
        """Test deduplication of empty list."""
        import scraper

        unique = scraper.dedupe_by_url([])
        assert unique == []


class TestFetchRssFeed:
    """Tests for fetch_rss_feed function."""

    @patch("feedparser.parse")
    def test_fetch_rss_feed_success(self, mock_parse):
        """Test successful RSS feed parsing."""
        import scraper

        mock_parse.return_value = MagicMock(
            feed={"title": "Test Feed"},
            entries=[
                {
                    "title": "Test Article",
                    "link": "https://example.com/test",
                    "summary": "Test content",
                    "published": "2026-01-20",
                }
            ],
        )

        items = scraper.fetch_rss_feed("https://example.com/rss")

        assert len(items) == 1
        assert items[0]["title"] == "Test Article"
        assert items[0]["url"] == "https://example.com/test"

    @patch("feedparser.parse")
    def test_fetch_rss_feed_empty(self, mock_parse):
        """Test RSS feed with no entries."""
        import scraper

        mock_parse.return_value = MagicMock(feed={"title": "Empty Feed"}, entries=[])

        items = scraper.fetch_rss_feed("https://example.com/rss")

        assert items == []


class TestFetchHackernewsTop:
    """Tests for fetch_hackernews_top function."""

    @patch("requests.get")
    def test_fetch_hackernews_success(self, mock_get):
        """Test successful HackerNews fetch."""
        import scraper

        # Mock top stories response
        mock_response_ids = MagicMock()
        mock_response_ids.json.return_value = [1, 2]
        mock_response_ids.raise_for_status = MagicMock()

        # Mock story response
        mock_response_story = MagicMock()
        mock_response_story.json.return_value = {
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com/story",
            "text": "Story content",
            "time": 1705737600,
        }
        mock_response_story.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_response_ids, mock_response_story, mock_response_story]

        items = scraper.fetch_hackernews_top(limit=2)

        assert len(items) <= 2


class TestFetchNewsData:
    """Tests for locale-aware NewsData fetching."""

    @patch("requests.get")
    def test_fetch_newsdata_articles_uses_locale_filters(self, mock_get):
        """Test NewsData request includes per-user languages and countries."""
        import scraper

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper.fetch_newsdata_articles(
            api_key="news-key",
            languages=["fr", "en"],
            countries=["ma"],
        )

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["language"] == "fr,en"
        assert kwargs["params"]["country"] == "ma"

    def test_resolve_newsdata_languages_prefers_user_content_languages(self):
        import scraper

        assert scraper.resolve_newsdata_languages(["ar", "en"], country_code="US") == [
            "ar",
            "en",
        ]


class TestSourceRouting:
    """Tests for language-first source routing."""

    def test_get_feeds_combines_language_and_country_sources(self):
        import scraper

        feeds = scraper.get_feeds(
            user_feeds=["https://example.com/custom.xml"],
            content_languages=["fr"],
            source_preset="AE",
            country_code="AE",
        )

        assert "https://example.com/custom.xml" in feeds
        assert any("blogdumoderateur" in feed for feed in feeds)
        assert any("arabianbusiness" in feed for feed in feeds)


class TestSaveArticles:
    """Tests for save_articles function."""

    @patch("config.get_database_client")
    def test_save_articles_new_articles(self, mock_client_fn, sample_articles):
        """Test saving new articles."""
        import scraper

        mock_client = MagicMock()
        mock_table = MagicMock()

        # No existing articles
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        saved = scraper.save_articles(sample_articles)

        assert saved == len(sample_articles)

    @patch("config.get_database_client")
    def test_save_articles_skip_duplicates(self, mock_client_fn, sample_articles):
        """Test skipping duplicate articles."""
        import scraper

        mock_client = MagicMock()
        mock_table = MagicMock()

        # All articles exist
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "existing"}]
        )

        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        saved = scraper.save_articles(sample_articles)

        assert saved == 0

    @patch("config.get_database_client")
    def test_save_articles_scopes_duplicate_check_by_user(self, mock_client_fn, sample_articles):
        """Test duplicate check is tenant-scoped when user_id is provided."""
        import scraper

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        saved = scraper.save_articles(sample_articles[:1], user_id="user-1")

        assert saved == 1
        mock_table.select.return_value.eq.return_value.eq.assert_called_with("user_id", "user-1")


class TestRunPipeline:
    """Tests for run() orchestration."""

    @patch("scraper.save_articles", return_value=2)
    @patch("scraper.dedupe_by_url", side_effect=lambda items: items)
    @patch("scraper.filter_articles", side_effect=lambda items, keywords: items)
    @patch("scraper.fetch_hackernews_top", return_value=[{"url": "https://hn", "title": "HN", "content": "AI"}])
    @patch("scraper.fetch_rss_feed", return_value=[{"url": "https://rss", "title": "RSS", "content": "AI"}])
    @patch("scraper.fetch_newsdata_articles", return_value=[{"url": "https://news", "title": "News", "content": "AI"}])
    @patch("scraper.get_feeds", return_value=["https://example.com/rss"])
    @patch("scraper.time.sleep")
    def test_run_collects_and_saves_articles(
        self,
        mock_sleep,
        mock_get_feeds,
        mock_newsdata,
        mock_rss,
        mock_hn,
        mock_filter,
        mock_dedupe,
        mock_save,
    ):
        import scraper

        result = scraper.run(user_id="user-1", keywords=["ai"])

        assert result == 2
        mock_save.assert_called_once()

    @patch("scraper.run", return_value=4)
    def test_run_for_user_uses_user_config(self, mock_run):
        import scraper

        user_config = MagicMock(
            user_id="user-1",
            newsdata_api_key="news-key",
            niche_keywords=["ai", "openai"],
            content_languages=["fr", "en"],
            country_code="MA",
            source_preset="FR",
            rss_feed_urls=["https://example.com/fr.xml"],
        )

        assert scraper.run_for_user(user_config) == 4
        mock_run.assert_called_once_with(
            user_id="user-1",
            newsdata_api_key="news-key",
            keywords=["ai", "openai"],
            content_languages=["fr", "en"],
            country_code="MA",
            source_preset="FR",
            rss_feeds=["https://example.com/fr.xml"],
        )
