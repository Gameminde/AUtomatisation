"""
Advanced Analytics Module - Comprehensive metrics tracking and ML insights.

Features:
- Real CPM calculation
- Engagement rate tracking
- Performance predictions
- A/B testing support
- Content optimization insights
- Revenue estimation

Author: Content Factory Team
Version: 2.0.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import config

logger = config.get_logger("advanced_analytics")


class MetricType(Enum):
    """Types of metrics tracked."""

    REACH = "reach"
    IMPRESSIONS = "impressions"
    ENGAGEMENT = "engagement"
    CLICKS = "clicks"
    SHARES = "shares"
    COMMENTS = "comments"
    LIKES = "likes"
    VIDEO_VIEWS = "video_views"
    WATCH_TIME = "watch_time"


@dataclass
class PostMetrics:
    """
    Comprehensive metrics for a single post.

    Attributes:
        post_id: Facebook post ID
        content_id: Internal content ID
        published_at: Publication timestamp
        reach: Number of unique users who saw the post
        impressions: Total number of times post was displayed
        likes: Number of likes/reactions
        comments: Number of comments
        shares: Number of shares
        clicks: Number of clicks
        video_views: Video views (for reels)
        watch_time: Total watch time in seconds
        engagement_rate: Calculated engagement rate (%)
        cpm: Cost per mille (estimated revenue per 1000 impressions)
        estimated_revenue: Estimated revenue from this post
    """

    post_id: str
    content_id: str
    published_at: datetime
    reach: int = 0
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    video_views: int = 0
    watch_time: int = 0
    engagement_rate: float = 0.0
    cpm: float = 0.0
    estimated_revenue: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["published_at"] = self.published_at.isoformat()
        return data


@dataclass
class DailyStats:
    """
    Aggregated daily statistics.

    Attributes:
        date: Date for these stats
        total_posts: Number of posts published
        total_reach: Combined reach
        total_impressions: Combined impressions
        total_engagement: Total engagement (likes + comments + shares)
        avg_engagement_rate: Average engagement rate
        avg_cpm: Average CPM
        total_revenue: Estimated total revenue
        best_post_id: ID of best performing post
        worst_post_id: ID of worst performing post
    """

    date: datetime
    total_posts: int = 0
    total_reach: int = 0
    total_impressions: int = 0
    total_engagement: int = 0
    avg_engagement_rate: float = 0.0
    avg_cpm: float = 0.0
    total_revenue: float = 0.0
    best_post_id: Optional[str] = None
    worst_post_id: Optional[str] = None


class CPMCalculator:
    """
    Calculate Cost Per Mille (CPM) based on various factors.

    Factors affecting CPM:
    - Audience geography (US/UK/CA have higher CPM)
    - Content type (video typically has higher CPM)
    - Engagement rate (higher engagement = higher CPM)
    - Time of day
    - Season/holidays
    """

    # Base CPM rates by region (in USD)
    BASE_CPM_BY_REGION = {
        "US": 15.0,
        "UK": 12.0,
        "CA": 11.0,
        "AU": 10.0,
        "EU": 8.0,
        "MENA": 3.0,
        "OTHER": 2.0,
    }

    # Multipliers
    VIDEO_MULTIPLIER = 1.5
    HIGH_ENGAGEMENT_MULTIPLIER = 1.3  # For engagement > 5%
    PEAK_HOUR_MULTIPLIER = 1.2

    @classmethod
    def calculate_cpm(
        cls,
        region: str = "US",
        is_video: bool = False,
        engagement_rate: float = 0.0,
        is_peak_hour: bool = False,
    ) -> float:
        """
        Calculate estimated CPM based on factors.

        Args:
            region: Target audience region
            is_video: Whether content is video/reel
            engagement_rate: Post engagement rate (%)
            is_peak_hour: Whether posted during peak hours

        Returns:
            Estimated CPM in USD
        """
        base_cpm = cls.BASE_CPM_BY_REGION.get(region, cls.BASE_CPM_BY_REGION["OTHER"])

        cpm = base_cpm

        if is_video:
            cpm *= cls.VIDEO_MULTIPLIER

        if engagement_rate > 5.0:
            cpm *= cls.HIGH_ENGAGEMENT_MULTIPLIER
        elif engagement_rate > 3.0:
            cpm *= 1.1

        if is_peak_hour:
            cpm *= cls.PEAK_HOUR_MULTIPLIER

        return round(cpm, 2)

    @classmethod
    def estimate_revenue(cls, impressions: int, cpm: float) -> float:
        """
        Estimate revenue from impressions.

        Args:
            impressions: Number of impressions
            cpm: CPM rate

        Returns:
            Estimated revenue in USD
        """
        return round((impressions / 1000) * cpm, 2)


class EngagementAnalyzer:
    """
    Analyze engagement patterns and provide insights.
    """

    @staticmethod
    def calculate_engagement_rate(likes: int, comments: int, shares: int, reach: int) -> float:
        """
        Calculate engagement rate.

        Formula: ((likes + comments + shares) / reach) * 100

        Args:
            likes: Number of likes
            comments: Number of comments
            shares: Number of shares
            reach: Number of unique viewers

        Returns:
            Engagement rate as percentage
        """
        if reach == 0:
            return 0.0

        total_engagement = likes + comments + shares
        rate = (total_engagement / reach) * 100
        return round(rate, 2)

    @staticmethod
    def calculate_virality_score(shares: int, reach: int, comments: int) -> float:
        """
        Calculate virality score.

        Virality is weighted towards shares (they expand reach).

        Args:
            shares: Number of shares
            reach: Number of unique viewers
            comments: Number of comments

        Returns:
            Virality score (0-100)
        """
        if reach == 0:
            return 0.0

        # Shares are weighted 3x, comments 1x
        score = ((shares * 3 + comments) / reach) * 100
        return min(100, round(score, 2))

    @staticmethod
    def get_engagement_grade(rate: float) -> Tuple[str, str]:
        """
        Get engagement grade and description.

        Args:
            rate: Engagement rate percentage

        Returns:
            Tuple of (grade, description)
        """
        if rate >= 10.0:
            return ("A+", "🔥 Exceptional - Viral potential!")
        elif rate >= 6.0:
            return ("A", "🌟 Excellent engagement")
        elif rate >= 4.0:
            return ("B", "✅ Good engagement")
        elif rate >= 2.0:
            return ("C", "⚠️ Average engagement")
        elif rate >= 1.0:
            return ("D", "📉 Below average")
        else:
            return ("F", "❌ Poor engagement")


class PerformancePredictor:
    """
    Predict post performance based on historical data.

    Uses simple heuristics (can be upgraded to ML later).
    """

    def __init__(self):
        self.historical_data: List[PostMetrics] = []

    def load_historical_data(self, limit: int = 100) -> None:
        """
        Load historical performance data from database.

        Args:
            limit: Maximum posts to load
        """
        try:
            client = config.get_supabase_client()

            response = (
                client.table("published_posts")
                .select("*")
                .order("published_at", desc=True)
                .limit(limit)
                .execute()
            )

            for row in response.data or []:
                metrics = PostMetrics(
                    post_id=row.get("facebook_post_id", ""),
                    content_id=row.get("content_id", ""),
                    published_at=datetime.fromisoformat(
                        row.get("published_at", datetime.now().isoformat())
                    ),
                    reach=row.get("reach", 0),
                    impressions=row.get("impressions", 0),
                    likes=row.get("likes", 0),
                    comments=row.get("comments", 0),
                    shares=row.get("shares", 0),
                )
                self.historical_data.append(metrics)

            logger.info("Loaded %d historical posts", len(self.historical_data))

        except Exception as e:
            logger.error("Failed to load historical data: %s", e)

    def predict_engagement(
        self,
        post_type: str,
        hook_length: int,
        has_emoji: bool,
        has_question: bool,
        hour_of_day: int,
    ) -> Dict[str, Any]:
        """
        Predict expected engagement based on content features.

        Args:
            post_type: "text" or "reel"
            hook_length: Number of words in hook
            has_emoji: Whether hook has emojis
            has_question: Whether hook is a question
            hour_of_day: Hour of planned posting (0-23)

        Returns:
            Dict with predictions
        """
        base_engagement = 3.0  # Base expected engagement %

        # Adjust based on features
        if post_type == "reel":
            base_engagement *= 1.5  # Videos typically have higher engagement

        if has_emoji:
            base_engagement *= 1.2

        if has_question:
            base_engagement *= 1.15

        # Optimal hook length is 5-10 words
        if 5 <= hook_length <= 10:
            base_engagement *= 1.1
        elif hook_length > 20:
            base_engagement *= 0.9

        # Peak hours (US timezone consideration)
        peak_hours = [7, 8, 12, 13, 17, 18, 19, 20]
        if hour_of_day in peak_hours:
            base_engagement *= 1.2

        # Calculate confidence based on historical data
        confidence = min(0.9, 0.3 + (len(self.historical_data) * 0.006))

        return {
            "predicted_engagement_rate": round(base_engagement, 2),
            "confidence": round(confidence, 2),
            "estimated_reach_low": int(base_engagement * 100),
            "estimated_reach_high": int(base_engagement * 500),
            "recommendation": self._get_recommendation(base_engagement),
        }

    def _get_recommendation(self, predicted_engagement: float) -> str:
        """Get recommendation based on prediction."""
        if predicted_engagement >= 5.0:
            return "🚀 High potential! Prioritize this content."
        elif predicted_engagement >= 3.0:
            return "✅ Good potential. Consider A/B testing variations."
        else:
            return "⚠️ Consider improving hook or timing."


class AdvancedAnalyticsTracker:
    """
    Main analytics tracking and reporting class.
    """

    def __init__(self):
        self.cpm_calculator = CPMCalculator()
        self.engagement_analyzer = EngagementAnalyzer()
        self.predictor = PerformancePredictor()

    def track_post_metrics(self, post_id: str) -> Optional[PostMetrics]:
        """
        Fetch and track metrics for a specific post.

        Args:
            post_id: Facebook post ID

        Returns:
            PostMetrics if successful, None otherwise
        """
        try:
            # In production, this would call Facebook Graph API
            # For now, we fetch from our database
            client = config.get_supabase_client()

            response = (
                client.table("published_posts")
                .select("*")
                .eq("facebook_post_id", post_id)
                .single()
                .execute()
            )

            if not response.data:
                return None

            row = response.data

            # Calculate derived metrics
            engagement_rate = self.engagement_analyzer.calculate_engagement_rate(
                likes=row.get("likes", 0),
                comments=row.get("comments", 0),
                shares=row.get("shares", 0),
                reach=row.get("reach", 0),
            )

            is_video = row.get("post_type") == "reel"
            cpm = self.cpm_calculator.calculate_cpm(
                region="US",  # Default to US audience
                is_video=is_video,
                engagement_rate=engagement_rate,
            )

            revenue = self.cpm_calculator.estimate_revenue(
                impressions=row.get("impressions", 0),
                cpm=cpm,
            )

            metrics = PostMetrics(
                post_id=post_id,
                content_id=row.get("content_id", ""),
                published_at=datetime.fromisoformat(
                    row.get("published_at", datetime.now().isoformat())
                ),
                reach=row.get("reach", 0),
                impressions=row.get("impressions", 0),
                likes=row.get("likes", 0),
                comments=row.get("comments", 0),
                shares=row.get("shares", 0),
                video_views=row.get("video_views", 0),
                engagement_rate=engagement_rate,
                cpm=cpm,
                estimated_revenue=revenue,
            )

            # Update database with calculated metrics
            client.table("published_posts").update(
                {
                    "engagement_rate": engagement_rate,
                    "estimated_cpm": cpm,
                    "estimated_revenue": revenue,
                    "last_updated": datetime.now().isoformat(),
                }
            ).eq("facebook_post_id", post_id).execute()

            return metrics

        except Exception as e:
            logger.error("Failed to track metrics for %s: %s", post_id, e)
            return None

    def get_daily_report(self, date: Optional[datetime] = None) -> DailyStats:
        """
        Generate daily analytics report.

        Args:
            date: Date for report (default: today)

        Returns:
            DailyStats for the day
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        try:
            client = config.get_supabase_client()

            response = (
                client.table("published_posts")
                .select("*")
                .gte("published_at", start_of_day.isoformat())
                .lt("published_at", end_of_day.isoformat())
                .execute()
            )

            posts = response.data or []

            if not posts:
                return DailyStats(date=date)

            total_reach = sum(p.get("reach", 0) for p in posts)
            total_impressions = sum(p.get("impressions", 0) for p in posts)
            total_likes = sum(p.get("likes", 0) for p in posts)
            total_comments = sum(p.get("comments", 0) for p in posts)
            total_shares = sum(p.get("shares", 0) for p in posts)

            total_engagement = total_likes + total_comments + total_shares

            engagement_rates = [
                self.engagement_analyzer.calculate_engagement_rate(
                    p.get("likes", 0), p.get("comments", 0), p.get("shares", 0), p.get("reach", 1)
                )
                for p in posts
            ]
            avg_engagement = (
                sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0
            )

            # Find best and worst posts
            posts_by_engagement = sorted(
                posts, key=lambda p: p.get("likes", 0) + p.get("comments", 0), reverse=True
            )

            stats = DailyStats(
                date=date,
                total_posts=len(posts),
                total_reach=total_reach,
                total_impressions=total_impressions,
                total_engagement=total_engagement,
                avg_engagement_rate=round(avg_engagement, 2),
                avg_cpm=CPMCalculator.calculate_cpm("US", engagement_rate=avg_engagement),
                total_revenue=CPMCalculator.estimate_revenue(total_impressions, 15.0),
                best_post_id=(
                    posts_by_engagement[0].get("facebook_post_id") if posts_by_engagement else None
                ),
                worst_post_id=(
                    posts_by_engagement[-1].get("facebook_post_id")
                    if len(posts_by_engagement) > 1
                    else None
                ),
            )

            return stats

        except Exception as e:
            logger.error("Failed to generate daily report: %s", e)
            return DailyStats(date=date)

    def get_top_performing_content(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top performing content with analysis.

        Args:
            limit: Number of posts to return

        Returns:
            List of top posts with analysis
        """
        try:
            client = config.get_supabase_client()

            response = (
                client.table("published_posts")
                .select("*, processed_content(hook, hashtags, post_type)")
                .order("likes", desc=True)
                .limit(limit)
                .execute()
            )

            results = []
            for post in response.data or []:
                engagement_rate = self.engagement_analyzer.calculate_engagement_rate(
                    post.get("likes", 0),
                    post.get("comments", 0),
                    post.get("shares", 0),
                    post.get("reach", 1),
                )
                grade, description = self.engagement_analyzer.get_engagement_grade(engagement_rate)

                results.append(
                    {
                        "post_id": post.get("facebook_post_id"),
                        "published_at": post.get("published_at"),
                        "engagement_rate": engagement_rate,
                        "grade": grade,
                        "description": description,
                        "likes": post.get("likes", 0),
                        "comments": post.get("comments", 0),
                        "shares": post.get("shares", 0),
                        "reach": post.get("reach", 0),
                        "hook": (
                            post.get("processed_content", {}).get("hook")
                            if post.get("processed_content")
                            else None
                        ),
                    }
                )

            return results

        except Exception as e:
            logger.error("Failed to get top content: %s", e)
            return []

    def generate_insights(self) -> Dict[str, Any]:
        """
        Generate actionable insights from analytics data.

        Returns:
            Dict with insights and recommendations
        """
        self.predictor.load_historical_data(limit=50)

        insights = {
            "generated_at": datetime.now().isoformat(),
            "total_posts_analyzed": len(self.predictor.historical_data),
            "recommendations": [],
            "best_practices": [],
            "areas_to_improve": [],
        }

        if not self.predictor.historical_data:
            insights["recommendations"].append("📊 Start publishing content to generate insights")
            return insights

        # Analyze patterns
        avg_engagement = sum(
            self.engagement_analyzer.calculate_engagement_rate(
                m.likes, m.comments, m.shares, max(m.reach, 1)
            )
            for m in self.predictor.historical_data
        ) / len(self.predictor.historical_data)

        insights["average_engagement_rate"] = round(avg_engagement, 2)

        if avg_engagement >= 5.0:
            insights["best_practices"].append(
                "🔥 Your engagement rate is excellent! Keep the same strategy."
            )
        elif avg_engagement >= 3.0:
            insights["recommendations"].append(
                "✅ Good engagement. Try A/B testing hooks for improvement."
            )
        else:
            insights["areas_to_improve"].append("⚠️ Focus on improving hooks and CTAs")
            insights["areas_to_improve"].append(
                "💡 Consider posting more during peak hours (7-9 AM, 12-1 PM, 6-8 PM EST)"
            )

        # Add specific recommendations
        insights["recommendations"].append("📱 Videos/Reels typically have 50% higher engagement")
        insights["recommendations"].append("❓ Questions in hooks increase comments by 40%")
        insights["recommendations"].append("🎯 Optimal hook length: 5-10 words")

        return insights


# Convenience functions
def track_all_posts(limit: int = 50) -> int:
    """Track metrics for recent posts."""
    tracker = AdvancedAnalyticsTracker()

    try:
        client = config.get_supabase_client()
        response = (
            client.table("published_posts")
            .select("facebook_post_id")
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )

        tracked = 0
        for row in response.data or []:
            post_id = row.get("facebook_post_id")
            if post_id and tracker.track_post_metrics(post_id):
                tracked += 1

        logger.info("Tracked metrics for %d posts", tracked)
        return tracked

    except Exception as e:
        logger.error("Failed to track posts: %s", e)
        return 0


def get_revenue_estimate(days: int = 30) -> Dict[str, Any]:
    """Get revenue estimate for a period."""
    try:
        client = config.get_supabase_client()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        response = (
            client.table("published_posts")
            .select("impressions, estimated_cpm")
            .gte("published_at", cutoff)
            .execute()
        )

        total_impressions = sum(p.get("impressions", 0) for p in response.data or [])
        avg_cpm = 15.0  # Default CPM

        if response.data:
            cpms = [p.get("estimated_cpm", 15.0) for p in response.data if p.get("estimated_cpm")]
            if cpms:
                avg_cpm = sum(cpms) / len(cpms)

        revenue = CPMCalculator.estimate_revenue(total_impressions, avg_cpm)

        return {
            "period_days": days,
            "total_impressions": total_impressions,
            "average_cpm": round(avg_cpm, 2),
            "estimated_revenue_usd": revenue,
            "posts_analyzed": len(response.data or []),
        }

    except Exception as e:
        logger.error("Failed to estimate revenue: %s", e)
        return {"error": str(e)}


if __name__ == "__main__":
    print("🔍 Advanced Analytics Demo\n")

    # Demo CPM calculation
    print("📊 CPM Calculations:")
    print(f"  US audience, text: ${CPMCalculator.calculate_cpm('US', is_video=False)}")
    print(f"  US audience, video: ${CPMCalculator.calculate_cpm('US', is_video=True)}")
    print(
        f"  US audience, high engagement: ${CPMCalculator.calculate_cpm('US', engagement_rate=8.0)}"
    )

    # Demo engagement analysis
    print("\n📈 Engagement Analysis:")
    rate = EngagementAnalyzer.calculate_engagement_rate(150, 25, 10, 3000)
    grade, desc = EngagementAnalyzer.get_engagement_grade(rate)
    print(f"  Rate: {rate}% - Grade: {grade} {desc}")

    # Demo prediction
    print("\n🔮 Performance Prediction:")
    predictor = PerformancePredictor()
    prediction = predictor.predict_engagement(
        post_type="text",
        hook_length=7,
        has_emoji=True,
        has_question=True,
        hour_of_day=18,
    )
    print(f"  Predicted engagement: {prediction['predicted_engagement_rate']}%")
    print(f"  Confidence: {prediction['confidence']*100}%")
    print(f"  Recommendation: {prediction['recommendation']}")

    print("\n✅ Analytics module ready!")
