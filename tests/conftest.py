"""
Pytest fixtures and configuration for Content Factory tests.
"""

# os is available via pytest fixtures
import sys
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Create a mock Supabase client."""
    mock_client = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.neq.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[], count=0)

    mock_client.table.return_value = mock_table
    return mock_client


@pytest.fixture
def sample_articles() -> List[Dict]:
    """Sample articles for testing."""
    return [
        {
            "id": "test-uuid-1",
            "source_name": "techcrunch",
            "title": "OpenAI Releases GPT-5 with Revolutionary AI Capabilities",
            "url": "https://techcrunch.com/2026/01/20/openai-gpt5",
            "content": "OpenAI has announced GPT-5, featuring breakthrough advances in reasoning and multimodal capabilities.",
            "published_date": "2026-01-20T10:00:00",
            "keywords": ["ai", "openai", "gpt"],
            "virality_score": 8,
            "status": "pending",
        },
        {
            "id": "test-uuid-2",
            "source_name": "theverge",
            "title": "Tesla Unveils New Electric Truck for 2026",
            "url": "https://theverge.com/2026/01/19/tesla-truck",
            "content": "Tesla has revealed its latest electric truck model with 500-mile range.",
            "published_date": "2026-01-19T15:30:00",
            "keywords": ["tesla", "electric", "truck"],
            "virality_score": 7,
            "status": "pending",
        },
        {
            "id": "test-uuid-3",
            "source_name": "mit",
            "title": "MIT Develops Quantum Computing Breakthrough",
            "url": "https://news.mit.edu/2026/quantum-breakthrough",
            "content": "Researchers at MIT have achieved a major breakthrough in quantum error correction.",
            "published_date": "2026-01-18T09:00:00",
            "keywords": ["quantum", "mit", "innovation"],
            "virality_score": 9,
            "status": "pending",
        },
    ]


@pytest.fixture
def sample_processed_content() -> List[Dict]:
    """Sample processed content for testing."""
    return [
        {
            "id": "content-uuid-1",
            "article_id": "test-uuid-1",
            "post_type": "text",
            "generated_text": "اكتشفت للتو شيئاً مذهلاً! OpenAI أطلقت GPT-5",
            "hook": "🚨 صدمة! GPT-5 يغير كل شيء!",
            "call_to_action": "ما رأيكم؟ شاركونا تجربتكم! 💬",
            "hashtags": ["#ChatGPT", "#AI", "#تقنية"],
            "target_audience": "US",
        },
        {
            "id": "content-uuid-2",
            "article_id": "test-uuid-2",
            "post_type": "text",
            "generated_text": "Tesla أعلنت عن شاحنة كهربائية جديدة",
            "hook": "🔥 Tesla تفاجئ الجميع!",
            "call_to_action": "هل تفكرون بشراء سيارة كهربائية؟",
            "hashtags": ["#Tesla", "#EV", "#سيارات"],
            "target_audience": "US",
        },
    ]


@pytest.fixture
def mock_openrouter_response() -> Dict:
    """Mock OpenRouter API response."""
    return {
        "choices": [{"message": {"content": """[
                        {
                            "article_index": 0,
                            "text_post": {
                                "hook": "🚨 صدمة! OpenAI تغير قواعد اللعبة!",
                                "body": "اكتشفت للتو أن GPT-5 يمكنه فهم الصور والفيديو بدقة مذهلة!",
                                "cta": "ما رأيكم؟ شاركونا تجربتكم! 💬",
                                "hashtags": ["#ChatGPT", "#OpenAI", "#AI", "#تقنية"]
                            },
                            "reel_script": "[بصري: شاشة GPT-5] السرد: هل تصدقون ما فعلته OpenAI؟"
                        }
                    ]"""}}],
        "usage": {"total_tokens": 500},
    }


@pytest.fixture
def mock_env_vars(monkeypatch) -> None:
    """Set up mock environment variables."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key-12345")
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "test-openrouter-key-1")
    monkeypatch.setenv("OPENROUTER_API_KEY_2", "test-openrouter-key-2")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "test-fb-token")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "123456789")
    monkeypatch.setenv("PEXELS_API_KEY", "test-pexels-key")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("REQUEST_SLEEP_SECONDS", "1")


@pytest.fixture
def mock_requests_get(monkeypatch) -> MagicMock:
    """Mock requests.get for testing."""
    mock = MagicMock()
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = {}
    mock.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr("requests.get", mock)
    return mock


@pytest.fixture
def mock_requests_post(monkeypatch) -> MagicMock:
    """Mock requests.post for testing."""
    mock = MagicMock()
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = {"id": "test-post-id"}
    mock.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr("requests.post", mock)
    return mock
