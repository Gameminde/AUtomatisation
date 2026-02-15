# 📚 Content Factory - API Documentation

## Version 2.0.0 | Updated: January 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Module Reference](#module-reference)
3. [Core Functions](#core-functions)
4. [Configuration](#configuration)
5. [Error Handling](#error-handling)
6. [Testing](#testing)
7. [Security](#security)

---

## Overview

Content Factory is a modular content automation system for Facebook. This document describes the public APIs for each module.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONTENT FACTORY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  main.py (CLI Orchestrator)                                     │
│     │                                                           │
│     ├── scraper.py          (News Collection)                   │
│     ├── ai_generator.py     (Content Generation)                │
│     ├── scheduler.py        (Publication Planning)              │
│     ├── publisher.py        (Facebook Publishing)               │
│     └── analytics.py        (Metrics Tracking)                  │
│                                                                 │
│  Support Modules:                                               │
│     ├── config.py           (Configuration)                     │
│     ├── openrouter_client.py (AI API Client)                    │
│     ├── image_pipeline.py   (Image Generation)                  │
│     ├── content_quality.py  (Quality Validation)                │
│     ├── duplicate_detector.py (Duplicate Prevention)            │
│     ├── publication_tracker.py (Publication Management)         │
│     ├── retry_utils.py      (Retry Logic)                       │
│     ├── security_utils.py   (Security Features)                 │
│     └── advanced_analytics.py (Analytics Engine)                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Reference

### 1. `scraper.py` - News Collection

Collects tech news from multiple sources.

#### Functions

```python
def run() -> int:
    """
    Execute full scraping pipeline.
    
    Returns:
        Number of new articles saved
        
    Example:
        >>> import scraper
        >>> count = scraper.run()
        >>> print(f"Collected {count} articles")
    """

def fetch_rss_feed(url: str) -> List[dict]:
    """
    Fetch articles from an RSS feed.
    
    Args:
        url: RSS feed URL
        
    Returns:
        List of article dicts with keys:
        - source_name: str
        - title: str
        - url: str
        - content: str
        - published_date: str
    """

def fetch_hackernews_top(limit: int = 20) -> List[dict]:
    """
    Fetch top stories from Hacker News.
    
    Args:
        limit: Maximum stories to fetch
        
    Returns:
        List of article dicts
    """

def filter_articles(items: Iterable[dict], keywords: Iterable[str]) -> List[dict]:
    """
    Filter articles by keyword matching.
    
    Args:
        items: Articles to filter
        keywords: Keywords to match (case-insensitive)
        
    Returns:
        Filtered list of articles
    """

def score_virality(item: dict) -> int:
    """
    Calculate virality score for an article.
    
    Args:
        item: Article dict with 'title' and 'source_name'
        
    Returns:
        Score from 0-10
    """
```

---

### 2. `ai_generator.py` - Content Generation

Generates viral content using AI.

#### Functions

```python
def process_pending_articles(limit: int = 10, batch_size: int = 5) -> int:
    """
    Process pending articles and generate content.
    
    Args:
        limit: Maximum articles to process
        batch_size: Articles per API call
        
    Returns:
        Number of articles processed
        
    Example:
        >>> import ai_generator
        >>> processed = ai_generator.process_pending_articles(limit=10)
    """

def generate_batch(articles: List[dict], client: Optional[OpenRouterClient] = None) -> List[Dict]:
    """
    Generate content for multiple articles in one API call.
    
    Args:
        articles: List of article dicts with 'title' and 'content'
        client: Optional OpenRouter client
        
    Returns:
        List of generated content dicts with keys:
        - article_index: int
        - text_post: dict (hook, body, cta, hashtags)
        - reel_script: str
        
    Raises:
        AllKeysExhaustedError: When all API keys are rate-limited
    """

def generate_single(article: dict, post_type: str, client: Optional[OpenRouterClient] = None) -> Dict:
    """
    Generate content for a single article.
    
    Args:
        article: Article dict
        post_type: 'text' or 'reel'
        client: Optional OpenRouter client
        
    Returns:
        Generated content dict
    """

def parse_json_response(text: str) -> any:
    """
    Extract and parse JSON from model response.
    
    Handles:
    - Markdown code blocks
    - Trailing commas
    - Malformed JSON recovery
    
    Args:
        text: Raw model response
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If JSON cannot be parsed
    """
```

---

### 3. `scheduler.py` - Publication Planning

Plans optimal publication times.

#### Functions

```python
def schedule_posts(days: int = 7) -> int:
    """
    Schedule content for publication.
    
    Args:
        days: Number of days to schedule
        
    Returns:
        Number of posts scheduled
        
    Example:
        >>> import scheduler
        >>> scheduled = scheduler.schedule_posts(days=7)
    """

def build_slots_for_day(day: date) -> List[Dict]:
    """
    Generate publication slots for a day.
    
    Args:
        day: Date to generate slots for
        
    Returns:
        List of slot dicts with:
        - scheduled_time: ISO timestamp (UTC)
        - timezone: Timezone name
    """

def enforce_min_gap(slots: List[Dict], min_hours: int) -> List[Dict]:
    """
    Ensure minimum gap between slots.
    
    Args:
        slots: List of slot dicts
        min_hours: Minimum hours between posts
        
    Returns:
        Filtered slots respecting minimum gap
    """
```

#### Constants

```python
PEAK_HOURS = {
    "US_EST": [7, 12, 18, 20],
    "US_PST": [9, 14, 20, 22],
    "UK_GMT": [8, 13, 17, 21],
}

CONTENT_MIX = {
    "text": 0.60,
    "reel": 0.40,
}
```

---

### 4. `publisher.py` - Facebook Publishing

Publishes content to Facebook.

#### Functions

```python
def publish_due_posts(limit: int = 5) -> int:
    """
    Publish scheduled posts that are due.
    
    Features:
    - Duplicate checking via PublicationTracker
    - Automatic retry on transient failures
    - Rate limiting compliance
    
    Args:
        limit: Maximum posts to publish
        
    Returns:
        Number of posts published
    """

def publish_text_post(message: str) -> str:
    """
    Publish a text post to Facebook.
    
    Args:
        message: Post content
        
    Returns:
        Facebook post ID
        
    Raises:
        RuntimeError: On Facebook API error
    """

def publish_photo_post(message: str, image_path: str) -> str:
    """
    Publish a photo post to Facebook.
    
    Args:
        message: Caption
        image_path: Local path to image
        
    Returns:
        Facebook post ID
    """

def publish_with_duplicate_check(content_id: str) -> Optional[str]:
    """
    Publish content with duplicate prevention.
    
    Args:
        content_id: Content ID to publish
        
    Returns:
        Facebook post ID if successful, None otherwise
    """
```

---

### 5. `publication_tracker.py` - Publication Management

Prevents duplicate publications.

#### Classes

```python
class PublicationTracker:
    """
    Track publications to prevent duplicates.
    
    Prevents:
    1. Same article being processed twice
    2. Same content being published twice
    3. Similar content published too close together
    """
    
    def can_publish(self, content_id: str) -> Tuple[bool, str]:
        """
        Check if content can be published.
        
        Returns:
            Tuple of (can_publish, reason if not)
        """
    
    def record_publication(self, content_id: str, facebook_post_id: str) -> None:
        """Record a successful publication."""
    
    def get_unpublished_content(self, limit: int = 50) -> List[Dict]:
        """Get content ready for publishing."""
    
    def is_similar_content_recent(self, text: str, hours: int = 72) -> Tuple[bool, float, str]:
        """
        Check if similar content was published recently.
        
        Returns:
            Tuple of (is_similar, similarity_score, reason)
        """
```

#### Convenience Functions

```python
def can_publish_content(content_id: str) -> Tuple[bool, str]:
    """Check if content can be published."""

def record_publication(content_id: str, facebook_post_id: str) -> None:
    """Record a publication."""

def get_unpublished_content(limit: int = 50) -> List[Dict]:
    """Get publishable content."""
```

---

### 6. `retry_utils.py` - Retry Logic

Robust retry mechanisms.

#### Decorators

```python
@retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
)
def my_function():
    """Function with automatic retry."""
    pass
```

#### Circuit Breaker

```python
@circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 2,
)
def external_api_call():
    """Function with circuit breaker protection."""
    pass
```

#### Classes

```python
class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
    
    def reset(self) -> None:
        """Manually reset the circuit."""

class RateLimitError(Exception):
    """Rate limit hit."""

class AllKeysExhaustedError(Exception):
    """All API keys exhausted."""

class CircuitBreakerOpenError(Exception):
    """Circuit breaker is open."""
```

---

### 7. `content_quality.py` - Quality Validation

Validates generated content.

#### Classes

```python
class ContentQualityValidator:
    """Validate content quality."""
    
    def validate_content(self, content: Dict) -> Dict:
        """
        Full content validation.
        
        Args:
            content: Dict with hook, body, cta, hashtags
            
        Returns:
            Dict with:
            - overall_score: float (0-1)
            - is_valid: bool
            - grade: str (A+ to F)
            - components: dict (individual scores)
            - suggestions: list (improvements)
        """
    
    def validate_hook(self, hook: str) -> Dict:
        """Validate hook quality."""
    
    def validate_body(self, body: str) -> Dict:
        """Validate body content."""
    
    def validate_cta(self, cta: str) -> Dict:
        """Validate call-to-action."""
    
    def validate_hashtags(self, hashtags: List[str]) -> Dict:
        """Validate hashtags."""
```

---

### 8. `advanced_analytics.py` - Analytics Engine

Advanced metrics and insights.

#### Classes

```python
class CPMCalculator:
    """Calculate Cost Per Mille."""
    
    @classmethod
    def calculate_cpm(
        cls,
        region: str = "US",
        is_video: bool = False,
        engagement_rate: float = 0.0,
        is_peak_hour: bool = False,
    ) -> float:
        """
        Calculate estimated CPM.
        
        Returns:
            CPM in USD
        """
    
    @classmethod
    def estimate_revenue(cls, impressions: int, cpm: float) -> float:
        """Estimate revenue from impressions."""

class EngagementAnalyzer:
    """Analyze engagement patterns."""
    
    @staticmethod
    def calculate_engagement_rate(
        likes: int, comments: int, shares: int, reach: int
    ) -> float:
        """Calculate engagement rate percentage."""
    
    @staticmethod
    def get_engagement_grade(rate: float) -> Tuple[str, str]:
        """Get grade and description for engagement rate."""

class AdvancedAnalyticsTracker:
    """Main analytics tracking class."""
    
    def track_post_metrics(self, post_id: str) -> Optional[PostMetrics]:
        """Fetch and track metrics for a post."""
    
    def get_daily_report(self, date: datetime = None) -> DailyStats:
        """Generate daily analytics report."""
    
    def get_top_performing_content(self, limit: int = 10) -> List[Dict]:
        """Get top performing content."""
    
    def generate_insights(self) -> Dict[str, Any]:
        """Generate actionable insights."""
```

---

### 9. `security_utils.py` - Security Features

Security and credential management.

#### Classes

```python
class CredentialManager:
    """Secure credential management."""
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string."""
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string."""
    
    def hash_password(self, password: str) -> Tuple[str, str]:
        """Hash password with salt."""

class TokenRotationManager:
    """Manage API token rotation."""
    
    def register_token(self, name: str, token_preview: str, expires_in_days: int = None) -> str:
        """Register a token for tracking."""
    
    def check_expiration(self) -> List[Tuple[str, int]]:
        """Check for expiring tokens."""

class InputValidator:
    """Validate and sanitize inputs."""
    
    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Check if URL is valid."""
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 10000) -> str:
        """Sanitize text input."""

class RateLimitTracker:
    """Track rate limits across APIs."""
    
    def update_limit(self, api_name: str, limit: int, remaining: int) -> None:
        """Update rate limit info."""
    
    def can_make_request(self, api_name: str) -> Tuple[bool, Optional[float]]:
        """Check if request can be made."""
```

---

## Configuration

### Environment Variables

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key

# AI Generation
OPENROUTER_API_KEY_1=sk-or-v1-key1
OPENROUTER_API_KEY_2=sk-or-v1-key2
OPENROUTER_MODEL=anthropic/claude-3-haiku

# Facebook
FACEBOOK_ACCESS_TOKEN=your-token
FACEBOOK_PAGE_ID=your-page-id

# Optional
PEXELS_API_KEY=your-pexels-key
NEWSDATA_API_KEY=your-newsdata-key

# Configuration
HTTP_TIMEOUT_SECONDS=20
REQUEST_SLEEP_SECONDS=2
```

---

## Error Handling

### Exception Hierarchy

```
Exception
├── RateLimitError         # API rate limit hit
├── AllKeysExhaustedError  # All API keys rate-limited
├── CircuitBreakerOpenError # Circuit breaker is open
├── RetryableError         # Can be retried
└── NonRetryableError      # Should not be retried
```

### Best Practices

```python
from retry_utils import retry_with_backoff, is_transient_error

@retry_with_backoff(max_retries=3)
def api_call():
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        if is_transient_error(e):
            raise  # Will be retried
        raise NonRetryableError(str(e))  # Won't be retried
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific module tests
pytest tests/test_scraper.py

# Run with verbose output
pytest -v

# Run only failing tests
pytest --lf
```

### Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Fixtures
├── test_scraper.py
├── test_ai_generator.py
├── test_scheduler.py
├── test_publisher.py
├── test_config.py
├── test_content_quality.py
└── test_duplicate_detector.py
```

---

## Security

### Credential Protection

```python
from security_utils import CredentialManager, mask_sensitive

# Encrypt sensitive data
manager = CredentialManager(master_key="your-key")
encrypted = manager.encrypt("api-key")
decrypted = manager.decrypt(encrypted)

# Log safely
logger.info("Using token: %s", mask_sensitive(token))
# Output: Using token: sk-a...xyz
```

### Input Validation

```python
from security_utils import InputValidator

# Validate URLs
if InputValidator.is_valid_url(user_url):
    process_url(user_url)

# Sanitize text
clean_text = InputValidator.sanitize_text(user_input, max_length=1000)
```

---

## Quick Reference

### CLI Commands

```bash
# Collect articles
python main.py scrape

# Generate content
python main.py generate --limit 10

# Schedule posts
python main.py schedule

# Publish due posts
python main.py publish --limit 5

# Sync analytics
python main.py analytics

# Run full pipeline
python main.py run-all
```

### Dashboard

```bash
streamlit run dashboard.py
```

---

**Document Version**: 2.0.0  
**Last Updated**: January 22, 2026  
**Author**: Content Factory Team
