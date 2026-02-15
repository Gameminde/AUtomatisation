"""
ML Virality Scorer - Predict content virality using machine learning.

Uses historical engagement data to predict how viral new content will be.
Falls back to heuristic scoring if insufficient data.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import re

import config

logger = config.get_logger("ml_virality")


class MLViralityScorer:
    """Machine learning-based virality prediction."""
    
    # Viral indicators in content
    VIRAL_KEYWORDS = {
        # High impact (score +3)
        "high": ["breaking", "exclusive", "urgent", "leaked", "confirmed", "official", "new"],
        # Medium impact (score +2)
        "medium": ["announces", "releases", "launches", "reveals", "introduces"],
        # Low impact (score +1)
        "low": ["update", "change", "improve", "fix", "add"]
    }
    
    # Tech/Gaming brand bonus
    BRAND_BONUS = {
        "openai": 3, "chatgpt": 3, "gpt": 2, "nvidia": 2, "tesla": 2,
        "apple": 2, "google": 2, "microsoft": 1, "meta": 1, "ai": 2,
        "playstation": 2, "xbox": 2, "nintendo": 2, "steam": 1
    }
    
    def __init__(self):
        """Initialize the scorer."""
        self.model_trained = False
        self.vectorizer = None
        self.model = None
        self.historical_data = []
        
        # Try to train on historical data
        self._load_historical_data()
        if len(self.historical_data) >= 20:
            self._train_model()
    
    def _load_historical_data(self) -> None:
        """Load historical posts with engagement metrics."""
        try:
            client = config.get_supabase_client()
            
            # Get published posts with analytics
            result = (
                client.table("published_posts")
                .select("content_id, likes, shares, comments, reach")
                .gte("published_at", (datetime.now(timezone.utc) - timedelta(days=90)).isoformat())
                .limit(200)
                .execute()
            )
            
            for post in result.data or []:
                content_id = post.get("content_id")
                if not content_id:
                    continue
                
                # Get content text
                content_result = (
                    client.table("processed_content")
                    .select("generated_text")
                    .eq("id", content_id)
                    .single()
                    .execute()
                )
                
                if content_result.data:
                    text = content_result.data.get("generated_text", "")
                    if text:
                        engagement = (
                            post.get("likes", 0) + 
                            post.get("shares", 0) * 3 +  # Shares weighted higher
                            post.get("comments", 0) * 2   # Comments weighted higher
                        )
                        reach = post.get("reach", 1) or 1
                        engagement_rate = (engagement / reach) * 100
                        
                        self.historical_data.append({
                            "text": text,
                            "engagement_rate": engagement_rate
                        })
            
            logger.info(f"📊 Loaded {len(self.historical_data)} historical posts for ML training")
            
        except Exception as e:
            logger.warning(f"Could not load historical data: {e}")
    
    def _train_model(self) -> None:
        """Train ML model on historical data."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.ensemble import RandomForestRegressor
            
            texts = [d["text"] for d in self.historical_data]
            scores = [d["engagement_rate"] for d in self.historical_data]
            
            # Vectorize text
            self.vectorizer = TfidfVectorizer(
                max_features=200,
                stop_words="english",
                ngram_range=(1, 2)
            )
            X = self.vectorizer.fit_transform(texts)
            
            # Train model
            self.model = RandomForestRegressor(
                n_estimators=50,
                max_depth=10,
                random_state=42
            )
            self.model.fit(X, scores)
            
            self.model_trained = True
            logger.info("✅ ML model trained successfully")
            
        except ImportError:
            logger.warning("scikit-learn not installed - using heuristic scoring")
        except Exception as e:
            logger.warning(f"ML training failed: {e}")
    
    def score_content(self, text: str) -> Tuple[float, Dict]:
        """
        Score content for virality potential.
        
        Args:
            text: Content text to score
        
        Returns:
            Tuple of (score 0-10, detailed breakdown)
        """
        details = {
            "ml_score": None,
            "keyword_score": 0,
            "brand_score": 0,
            "length_score": 0,
            "emoji_score": 0,
            "method": "heuristic"
        }
        
        # Try ML prediction first
        if self.model_trained and self.vectorizer and self.model:
            try:
                X = self.vectorizer.transform([text])
                ml_prediction = self.model.predict(X)[0]
                # Normalize to 0-10 scale
                details["ml_score"] = min(10, max(0, ml_prediction / 2))
                details["method"] = "ml"
                
                # Combine ML with heuristics (70% ML, 30% heuristic)
                heuristic = self._heuristic_score(text, details)
                final_score = details["ml_score"] * 0.7 + heuristic * 0.3
                
                logger.debug(f"🤖 ML score: {details['ml_score']:.2f}, Final: {final_score:.2f}")
                return min(10, final_score), details
                
            except Exception as e:
                logger.warning(f"ML prediction failed, using heuristic: {e}")
        
        # Fallback to heuristic
        score = self._heuristic_score(text, details)
        return score, details
    
    def _heuristic_score(self, text: str, details: Dict) -> float:
        """Calculate heuristic virality score."""
        score = 5.0  # Base score
        text_lower = text.lower()
        
        # Keyword analysis
        for impact, keywords in self.VIRAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if impact == "high":
                        details["keyword_score"] += 0.5
                    elif impact == "medium":
                        details["keyword_score"] += 0.3
                    else:
                        details["keyword_score"] += 0.1
        
        score += min(2, details["keyword_score"])  # Cap at +2
        
        # Brand bonus
        for brand, bonus in self.BRAND_BONUS.items():
            if brand in text_lower:
                details["brand_score"] += bonus * 0.2
        
        score += min(1.5, details["brand_score"])  # Cap at +1.5
        
        # Length scoring (optimal: 200-500 chars)
        length = len(text)
        if 200 <= length <= 500:
            details["length_score"] = 1.0
        elif 100 <= length < 200 or 500 < length <= 700:
            details["length_score"] = 0.5
        else:
            details["length_score"] = 0
        
        score += details["length_score"]
        
        # Emoji presence
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if 1 <= emoji_count <= 5:
            details["emoji_score"] = 0.5
        elif emoji_count > 5:
            details["emoji_score"] = 0.2  # Too many emojis
        
        score += details["emoji_score"]
        
        return min(10, max(0, score))
    
    def get_top_performing_topics(self, limit: int = 10) -> List[Dict]:
        """Get historically best-performing topic patterns."""
        if not self.historical_data:
            return []
        
        # Sort by engagement rate
        sorted_data = sorted(
            self.historical_data, 
            key=lambda x: x["engagement_rate"], 
            reverse=True
        )
        
        return sorted_data[:limit]
    
    def analyze_content_improvement(self, text: str) -> Dict:
        """
        Suggest improvements to boost virality.
        
        Args:
            text: Content to analyze
        
        Returns:
            Dict with suggestions
        """
        score, details = self.score_content(text)
        suggestions = []
        
        if details["keyword_score"] < 0.5:
            suggestions.append("Add viral keywords (breaking, exclusive, leaked, confirmed)")
        
        if details["brand_score"] < 0.5:
            suggestions.append("Mention popular tech brands (OpenAI, ChatGPT, Nvidia)")
        
        if details["length_score"] < 0.5:
            if len(text) < 200:
                suggestions.append("Expand content (optimal: 200-500 chars)")
            else:
                suggestions.append("Trim content (optimal: 200-500 chars)")
        
        if details["emoji_score"] < 0.3:
            suggestions.append("Add 2-3 relevant emojis for engagement")
        
        return {
            "current_score": score,
            "potential_score": min(10, score + len(suggestions) * 0.5),
            "suggestions": suggestions,
            "details": details
        }


# Global instance
_scorer = None


def get_scorer() -> MLViralityScorer:
    """Get or create global scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = MLViralityScorer()
    return _scorer


def score_content(text: str) -> float:
    """Quick access to score content."""
    scorer = get_scorer()
    score, _ = scorer.score_content(text)
    return score


def analyze_content(text: str) -> Dict:
    """Quick access to analyze content."""
    scorer = get_scorer()
    return scorer.analyze_content_improvement(text)


if __name__ == "__main__":
    print("🔬 Testing ML Virality Scorer...\n")
    
    scorer = MLViralityScorer()
    
    # Test cases
    test_contents = [
        "🚨 BREAKING: OpenAI just leaked GPT-5 features! This is massive!",
        "New update available",
        "ChatGPT announces revolutionary AI breakthrough - experts shocked",
        "🔥 Nvidia reveals next-gen gaming GPUs - PlayStation and Xbox should worry!"
    ]
    
    print("📊 Scoring Test Contents:\n")
    for content in test_contents:
        score, details = scorer.score_content(content)
        print(f"Score: {score:.1f}/10 | Method: {details['method']}")
        print(f"  Text: {content[:60]}...")
        print(f"  Keywords: +{details['keyword_score']:.1f}, Brands: +{details['brand_score']:.1f}")
        print()
    
    # Test improvement suggestions
    print("\n💡 Improvement Suggestions:")
    weak_content = "update on some tech stuff"
    analysis = scorer.analyze_content_improvement(weak_content)
    print(f"Current: {analysis['current_score']:.1f}/10")
    print(f"Potential: {analysis['potential_score']:.1f}/10")
    for suggestion in analysis['suggestions']:
        print(f"  ➡️ {suggestion}")
    
    print("\n✅ ML Virality Scorer tests complete!")
