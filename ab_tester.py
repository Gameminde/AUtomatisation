"""
A/B Testing Framework - Generate and track content variations.

Creates multiple variants of content and tracks which performs better
to optimize future posts.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import config

logger = config.get_logger("ab_tester")


class ABTester:
    """A/B test different content variations for optimization."""
    
    # Variation styles
    STYLES = {
        "emotional": {
            "tone": "exciting, urgent, emotional",
            "hooks": ["🚨", "🔥", "⚡"],
            "cta_style": "Strong call to action with question"
        },
        "factual": {
            "tone": "informative, professional, detailed",
            "hooks": ["📢", "📰", "💡"],
            "cta_style": "Informative prompt for discussion"
        },
        "casual": {
            "tone": "friendly, conversational, relatable",
            "hooks": ["👀", "📱", "✨"],
            "cta_style": "Casual question to spark conversation"
        }
    }
    
    def __init__(self):
        """Initialize A/B tester."""
        self.client = config.get_supabase_client()
        self.active_tests = {}
    
    def create_test(
        self, 
        topic: Dict, 
        styles: List[str] = ["emotional", "factual"]
    ) -> str:
        """
        Create an A/B test with multiple content variants.
        
        Args:
            topic: Topic to generate variants for
            styles: List of style variations to test
        
        Returns:
            Test ID
        """
        test_id = str(uuid4())[:8]
        
        variants = []
        for style in styles:
            variant = self._generate_variant(topic, style)
            variant["style"] = style
            variant["test_id"] = test_id
            variants.append(variant)
        
        self.active_tests[test_id] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "variants": variants,
            "status": "active"
        }
        
        logger.info(f"🧪 Created A/B test {test_id} with {len(variants)} variants")
        return test_id
    
    def _generate_variant(self, topic: Dict, style: str) -> Dict:
        """Generate a content variant with specific style."""
        style_config = self.STYLES.get(style, self.STYLES["factual"])
        
        # Adjust content based on style
        hook = self._adjust_hook(topic.get("title", ""), style_config)
        body = topic.get("content", "")
        cta = self._generate_cta(style_config)
        
        return {
            "hook": hook,
            "body": body,
            "cta": cta,
            "hashtags": topic.get("hashtags", []),
            "content_id": None,  # Will be set when saved to DB
            "published_at": None,
            "metrics": None
        }
    
    def _adjust_hook(self, title: str, style_config: Dict) -> str:
        """Adjust the hook based on style."""
        import random
        
        hook_emoji = random.choice(style_config["hooks"])
        
        if style_config["tone"] == "exciting, urgent, emotional":
            return f"{hook_emoji} عاجل: {title}!"
        elif style_config["tone"] == "informative, professional, detailed":
            return f"{hook_emoji} خبر مهم: {title}"
        else:
            return f"{hook_emoji} شاهدوا هذا: {title}"
    
    def _generate_cta(self, style_config: Dict) -> str:
        """Generate call-to-action based on style."""
        if style_config["cta_style"] == "Strong call to action with question":
            return "ما رأيكم؟ شاركونا في التعليقات الآن! 💬🔥"
        elif style_config["cta_style"] == "Informative prompt for discussion":
            return "شاركونا آراءكم وتجاربكم في التعليقات 💭"
        else:
            return "ايش رأيكم؟ 💬"
    
    def save_variant_to_db(self, test_id: str, variant_index: int) -> Optional[str]:
        """Save a specific variant to the database."""
        test = self.active_tests.get(test_id)
        if not test or variant_index >= len(test["variants"]):
            return None
        
        variant = test["variants"][variant_index]
        
        try:
            # Build full text
            full_text = f"{variant['hook']}\n\n{variant['body']}\n\n{variant['cta']}"
            
            content_data = {
                "post_type": "text",
                "generated_text": full_text,
                "hook": variant["hook"],
                "call_to_action": variant["cta"],
                "hashtags": variant["hashtags"],
                "ab_test_id": test_id,
                "ab_variant_style": variant["style"]
            }
            
            result = self.client.table("processed_content").insert(content_data).execute()
            content_id = result.data[0]["id"] if result.data else None
            
            # Update variant with content_id
            variant["content_id"] = content_id
            
            logger.info(f"💾 Saved variant {variant['style']} as {content_id}")
            return content_id
            
        except Exception as e:
            logger.error(f"Error saving variant: {e}")
            return None
    
    def record_publication(
        self, 
        test_id: str, 
        variant_style: str, 
        facebook_post_id: str
    ) -> None:
        """Record when a variant is published."""
        test = self.active_tests.get(test_id)
        if not test:
            return
        
        for variant in test["variants"]:
            if variant["style"] == variant_style:
                variant["published_at"] = datetime.now(timezone.utc).isoformat()
                variant["facebook_post_id"] = facebook_post_id
                break
        
        logger.info(f"📤 Recorded publication for {variant_style} variant")
    
    def collect_metrics(self, test_id: str) -> Dict:
        """
        Collect engagement metrics for all variants in a test.
        
        Should be called 24-48h after publishing.
        """
        test = self.active_tests.get(test_id)
        if not test:
            return {"error": "Test not found"}
        
        results = []
        
        for variant in test["variants"]:
            content_id = variant.get("content_id")
            if not content_id:
                continue
            
            try:
                # Get metrics from published_posts
                result = (
                    self.client.table("published_posts")
                    .select("likes, shares, comments, reach")
                    .eq("content_id", content_id)
                    .single()
                    .execute()
                )
                
                if result.data:
                    metrics = result.data
                    engagement = (
                        metrics.get("likes", 0) + 
                        metrics.get("shares", 0) * 3 + 
                        metrics.get("comments", 0) * 2
                    )
                    reach = metrics.get("reach", 1) or 1
                    engagement_rate = (engagement / reach) * 100
                    
                    variant["metrics"] = {
                        **metrics,
                        "engagement_rate": engagement_rate
                    }
                    results.append({
                        "style": variant["style"],
                        "engagement_rate": engagement_rate,
                        **metrics
                    })
                    
            except Exception as e:
                logger.error(f"Error collecting metrics for {content_id}: {e}")
        
        return {
            "test_id": test_id,
            "variants": results,
            "winner": self._determine_winner(results)
        }
    
    def _determine_winner(self, results: List[Dict]) -> Optional[Dict]:
        """Determine the winning variant."""
        if not results:
            return None
        
        winner = max(results, key=lambda x: x.get("engagement_rate", 0))
        
        logger.info(f"🏆 Winner: {winner['style']} with {winner['engagement_rate']:.2f}% engagement")
        return winner
    
    def get_best_style(self, days: int = 30) -> str:
        """
        Analyze historical A/B tests to find best-performing style.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Best performing style name
        """
        style_scores = {style: [] for style in self.STYLES.keys()}
        
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            result = (
                self.client.table("processed_content")
                .select("ab_variant_style")
                .not_("ab_variant_style", "is", "null")
                .gte("created_at", cutoff)
                .execute()
            )
            
            # This would need to be joined with metrics in practice
            # Simplified for demonstration
            
        except Exception as e:
            logger.warning(f"Error analyzing best style: {e}")
        
        # Default to emotional if no data
        return "emotional"
    
    def get_active_tests(self) -> List[Dict]:
        """Get all active A/B tests."""
        return [
            {"test_id": k, **v}
            for k, v in self.active_tests.items()
            if v.get("status") == "active"
        ]


# Global instance
_tester = None


def get_tester() -> ABTester:
    """Get or create global A/B tester instance."""
    global _tester
    if _tester is None:
        _tester = ABTester()
    return _tester


def create_ab_test(topic: Dict, styles: List[str] = ["emotional", "factual"]) -> str:
    """Create an A/B test for a topic."""
    tester = get_tester()
    return tester.create_test(topic, styles)


def get_test_results(test_id: str) -> Dict:
    """Get results for an A/B test."""
    tester = get_tester()
    return tester.collect_metrics(test_id)


if __name__ == "__main__":
    print("🧪 Testing A/B Testing Framework...\n")
    
    tester = ABTester()
    
    # Create test topic
    test_topic = {
        "title": "OpenAI Releases GPT-5 with Amazing New Features",
        "content": "OpenAI has announced the release of GPT-5, featuring unprecedented capabilities in reasoning and creativity.",
        "hashtags": ["#AI", "#OpenAI", "#GPT5", "#Technology"]
    }
    
    # Create A/B test
    print("📋 Creating A/B test with emotional vs factual variants...")
    test_id = tester.create_test(test_topic, ["emotional", "factual", "casual"])
    
    print(f"\n✅ Test ID: {test_id}")
    
    # Show variants
    test = tester.active_tests[test_id]
    print(f"\n📊 Generated {len(test['variants'])} variants:\n")
    
    for i, variant in enumerate(test["variants"]):
        print(f"Variant {i+1} ({variant['style']}):")
        print(f"  Hook: {variant['hook']}")
        print(f"  CTA: {variant['cta']}")
        print()
    
    # Show active tests
    print(f"📋 Active tests: {len(tester.get_active_tests())}")
    
    print("\n✅ A/B Testing Framework tests complete!")
