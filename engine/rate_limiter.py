"""
Adaptive Rate Limiter - Safe posting limits based on page maturity.

Prevents bans by:
- Starting slow (2 posts/day for new pages)
- Ramping up gradually as page ages
- Monitoring engagement before posting
- Auto-pausing on low engagement
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import config

logger = config.get_logger("rate_limiter")


class AdaptiveRateLimiter:
    """Enforce safe posting limits based on page maturity and engagement."""
    
    # Configuration
    MIN_ENGAGEMENT_RATE = 0.5  # 0.5% minimum to continue posting
    
    def __init__(self, user_id: Optional[str] = None, page_id: Optional[str] = None):
        """
        Initialize rate limiter for a specific page.
        
        Args:
            user_id: Tenant scope for multi-tenant SaaS flows
            page_id: Facebook page ID (defaults to config value)
        """
        self.user_id = user_id
        self.page_id = page_id or config.FACEBOOK_PAGE_ID
        self.client = config.get_database_client()

    def _scope_query(self, query):
        if self.user_id:
            return query.eq("user_id", self.user_id)
        if self.page_id:
            return query.eq("page_id", self.page_id)
        return query
    
    def get_page_age_days(self) -> int:
        """
        Calculate days since first post.
        
        Returns:
            Number of days since first publish, 0 if no posts
        """
        try:
            result = (
                self._scope_query(
                    self.client.table("published_posts")
                    .select("published_at")
                )
                .order("published_at", desc=False)
                .limit(1)
                .execute()
            )
            
            if not result.data:
                logger.info("📅 New page - no posts yet")
                return 0
            
            first_post = datetime.fromisoformat(
                result.data[0]["published_at"].replace("Z", "+00:00")
            )
            if first_post.tzinfo is None:
                first_post = first_post.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - first_post).days
            
            logger.debug(f"📅 Page age: {age} days")
            return age
        
        except Exception as e:
            logger.error(f"Error calculating page age: {e}")
            return 0
    
    def get_safe_daily_limit(self) -> int:
        """
        Progressive limit based on page age.
        
        New pages start conservative, mature pages can post more.
        
        Returns:
            Maximum posts allowed per day
        """
        age_days = self.get_page_age_days()
        
        if age_days < 7:
            limit = 2  # Week 1: very conservative
        elif age_days < 30:
            limit = 3  # Month 1: cautious
        elif age_days < 90:
            limit = 5  # Quarter 1: moderate
        else:
            limit = 8  # Mature page: higher volume
        
        logger.info("🎯 Daily limit for %d-day-old page: %d posts/day", age_days, limit)
        return limit
    
    def get_today_post_count(self) -> int:
        """
        Count posts published today (UTC).
        
        Returns:
            Number of posts published today
        """
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = (
                self._scope_query(
                    self.client.table("published_posts")
                    .select("id")
                    .gte("published_at", today_start.isoformat())
                )
                .execute()
            )
            
            count = len(result.data or [])
            logger.debug(f"📊 Posts today: {count}")
            return count
        
        except Exception as e:
            logger.error(f"Error counting today's posts: {e}")
            return 0
    
    def get_recent_engagement_rate(self, lookback_posts: int = 5) -> float:
        """
        Calculate average engagement rate of recent posts.
        
        Args:
            lookback_posts: Number of recent posts to analyze
        
        Returns:
            Engagement rate as percentage (0-100)
        """
        try:
            result = (
                self._scope_query(
                    self.client.table("published_posts")
                    .select("likes, comments, shares, reach")
                )
                .order("published_at", desc=True)
                .limit(lookback_posts)
                .execute()
            )
            
            if not result.data or len(result.data) == 0:
                logger.info("💡 New page - giving benefit of doubt (100% engagement)")
                return 100.0  # Give new pages benefit of doubt
            
            total_engagement = 0
            total_reach = 0
            
            for post in result.data:
                engagement = (
                    post.get("likes", 0) + 
                    post.get("comments", 0) + 
                    post.get("shares", 0)
                )
                reach = post.get("reach", 0)
                
                total_engagement += engagement
                total_reach += reach
            
            if total_reach == 0:
                logger.warning("⚠️ No reach data yet - assuming good engagement")
                return 5.0  # Reasonable default
            
            engagement_rate = (total_engagement / total_reach) * 100
            logger.info("📈 Recent engagement rate: %.2f%%", engagement_rate)
            
            return engagement_rate
        
        except Exception as e:
            logger.error(f"Error calculating engagement: {e}")
            return 5.0  # Safe default
    
    def can_post_now(self) -> Tuple[bool, str]:
        """
        Check if posting is allowed right now.
        
        Checks:
        1. Daily limit not exceeded
        2. Engagement rate healthy
        
        Returns:
            (can_post, reason)
        """
        # Check daily limit
        limit = self.get_safe_daily_limit()
        count = self.get_today_post_count()
        
        if count >= limit:
            reason = f"Daily limit reached ({count}/{limit} posts)"
            logger.warning("⏸️ %s", reason)
            return False, reason
        
        # Check engagement health (prevent shadowban)
        engagement_rate = self.get_recent_engagement_rate()
        
        if engagement_rate < self.MIN_ENGAGEMENT_RATE:
            reason = f"Low engagement detected ({engagement_rate:.2f}% < {self.MIN_ENGAGEMENT_RATE}%) - pausing to avoid flags"
            logger.warning("⚠️ %s", reason)
            return False, reason
        
        logger.info("✅ Can post (%d/%d today, %.2f%% engagement)", count, limit, engagement_rate)
        return True, "OK"
    
    def get_status_summary(self) -> Dict:
        """
        Get detailed status summary.
        
        Returns:
            Dictionary with current status metrics
        """
        can_post, reason = self.can_post_now()
        return {
            "page_age_days": self.get_page_age_days(),
            "daily_limit": self.get_safe_daily_limit(),
            "posts_today": self.get_today_post_count(),
            "engagement_rate": self.get_recent_engagement_rate(),
            "can_post": can_post,
            "reason": reason
        }
    
    def wait_until_can_post(self) -> timedelta:
        """
        Calculate how long to wait before next post allowed.
        
        Returns:
            Time to wait before posting allowed
        """
        can_post, reason = self.can_post_now()
        
        if can_post:
            return timedelta(0)
        
        # If daily limit reached, wait until tomorrow
        if "Daily limit" in reason:
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)
            wait_time = tomorrow - datetime.now(timezone.utc)
            logger.info("⏰ Wait until tomorrow: %s", wait_time)
            return wait_time
        
        # If engagement low, wait 24h for recovery
        if "Low engagement" in reason:
            logger.info("⏰ Waiting 24h for engagement recovery")
            return timedelta(hours=24)
        
        return timedelta(hours=1)  # Default wait


def get_rate_limiter(
    user_id: Optional[str] = None,
    page_id: Optional[str] = None,
) -> AdaptiveRateLimiter:
    """Build a scoped rate limiter instance."""
    return AdaptiveRateLimiter(user_id=user_id, page_id=page_id)


# Convenience function
def can_post_now(
    user_id: Optional[str] = None,
    page_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Check if posting allowed right now."""
    limiter = get_rate_limiter(user_id=user_id, page_id=page_id)
    return limiter.can_post_now()


if __name__ == "__main__":
    print("🚦 Testing Adaptive Rate Limiter...\n")
    
    limiter = AdaptiveRateLimiter()
    
    # Get status summary
    status = limiter.get_status_summary()
    
    print("📊 Current Status:")
    print(f"  Page age: {status['page_age_days']} days")
    print(f"  Daily limit: {status['daily_limit']} posts/day")
    print(f"  Posted today: {status['posts_today']}")
    print(f"  Engagement rate: {status['engagement_rate']:.2f}%")
    print(f"  Can post: {status['can_post']}")
    print(f"  Reason: {status['reason']}")
    
    # Test posting check
    print("\n🎯 Testing posting check:")
    can_post, reason = limiter.can_post_now()
    if can_post:
        print(f"  ✅ Posting allowed: {reason}")
    else:
        print(f"  ⏸️ Posting paused: {reason}")
        wait = limiter.wait_until_can_post()
        print(f"  ⏰ Wait time: {wait}")
    
    print("\n✅ Rate limiter tests complete!")
