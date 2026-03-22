"""
Ban Detector - Detect potential shadowbans and alert user.

Monitors:
- Reach drops (>50% = warning)
- Engagement rate degradation
- Suspicious patterns
"""

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

import config

logger = config.get_logger("ban_detector")


class BanDetector:
    """Detect potential Facebook shadowbans and alert user."""
    
    # Thresholds
    REACH_DROP_THRESHOLD = 0.5  # 50% drop = warning
    ENGAGEMENT_DROP_THRESHOLD = 0.4  # 60% drop = warning
    MIN_POSTS_FOR_ANALYSIS = 5
    
    def __init__(self, page_id: Optional[str] = None):
        """
        Initialize ban detector.
        
        Args:
            page_id: Facebook page ID to monitor
        """
        self.page_id = page_id or config.FACEBOOK_PAGE_ID
        self.client = config.get_supabase_client()
    
    def check_for_shadowban(self) -> Dict:
        """
        Analyze recent posts for ban indicators.
        
        Returns:
            Status dict with detection results
        """
        logger.info("🔍 Checking for shadowban indicators...")
        
        # Get recent posts
        posts = self._get_recent_posts(lookback=10)
        
        if len(posts) < self.MIN_POSTS_FOR_ANALYSIS:
            return {
                "status": "ok",
                "reason": f"Insufficient data ({len(posts)} posts, need {self.MIN_POSTS_FOR_ANALYSIS})",
                "severity": 0
            }
        
        # Check reach drop
        reach_status = self._check_reach_drop(posts)
        if reach_status["status"] != "ok":
            return reach_status
        
        # Check engagement drop
        engagement_status = self._check_engagement_drop(posts)
        if engagement_status["status"] != "ok":
            return engagement_status
        
        # Check posting frequency anomaly
        frequency_status = self._check_frequency_anomaly(posts)
        if frequency_status["status"] != "ok":
            return frequency_status
        
        logger.info("✅ No shadowban indicators detected")
        return {
            "status": "ok",
            "reason": "All metrics healthy",
            "severity": 0
        }
    
    def _get_recent_posts(self, lookback: int = 10) -> List[Dict]:
        """Fetch recent published posts."""
        try:
            result = (
                self.client.table("published_posts")
                .select("id, published_at, reach, likes, comments, shares, impressions")
                .order("published_at", desc=True)
                .limit(lookback)
                .execute()
            )
            
            return result.data or []
        
        except Exception as e:
            logger.error("Error fetching posts: %s", e)
            return []
    
    def _check_reach_drop(self, posts: List[Dict]) -> Dict:
        """Check for sudden reach drops."""
        if len(posts) < 6:
            return {"status": "ok", "reason": "Not enough posts", "severity": 0}
        
        # Compare recent vs older posts
        recent_posts = posts[:3]
        older_posts = posts[3:7]
        
        recent_avg_reach = sum(p.get("reach", 0) for p in recent_posts) / len(recent_posts)
        older_avg_reach = sum(p.get("reach", 0) for p in older_posts) / len(older_posts)
        
        if older_avg_reach == 0:
            return {"status": "ok", "reason": "No baseline reach", "severity": 0}
        
        drop_ratio = recent_avg_reach / older_avg_reach
        
        if drop_ratio < self.REACH_DROP_THRESHOLD:
            drop_pct = (1 - drop_ratio) * 100
            logger.warning(f"⚠️ REACH DROP DETECTED: {drop_pct:.1f}%")
            
            return {
                "status": "warning",
                "reason": f"Reach dropped {drop_pct:.1f}% - possible shadowban",
                "recent_avg": recent_avg_reach,
                "older_avg": older_avg_reach,
                "drop_ratio": drop_ratio,
                "severity": 8 if drop_ratio < 0.3 else 5
            }
        
        logger.debug(f"✅ Reach stable ({drop_ratio:.2f} ratio)")
        return {"status": "ok", "reason": "Reach stable", "severity": 0}
    
    def _check_engagement_drop(self, posts: List[Dict]) -> Dict:
        """Check for engagement rate drops."""
        if len(posts) < 6:
            return {"status": "ok", "reason": "Not enough posts", "severity": 0}
        
        recent_posts = posts[:3]
        older_posts = posts[3:7]
        
        def calc_engagement_rate(post_list):
            total_engagement = sum(
                p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0)
                for p in post_list
            )
            total_reach = sum(p.get("reach", 1) for p in post_list)
            return (total_engagement / total_reach * 100) if total_reach > 0 else 0
        
        recent_rate = calc_engagement_rate(recent_posts)
        older_rate = calc_engagement_rate(older_posts)
        
        if older_rate == 0:
            return {"status": "ok", "reason": "No baseline engagement", "severity": 0}
        
        drop_ratio = recent_rate / older_rate
        
        if drop_ratio < self.ENGAGEMENT_DROP_THRESHOLD:
            drop_pct = (1 - drop_ratio) * 100
            logger.warning(f"⚠️ ENGAGEMENT DROP: {drop_pct:.1f}%")
            
            return {
                "status": "warning",
                "reason": f"Engagement dropped {drop_pct:.1f}%",
                "recent_rate": recent_rate,
                "older_rate": older_rate,
                "severity": 6
            }
        
        return {"status": "ok", "reason": "Engagement stable", "severity": 0}
    
    def _check_frequency_anomaly(self, posts: List[Dict]) -> Dict:
        """Check if posts are being throttled (delayed visibility)."""
        # Check if recent posts have suspiciously low impressions relative to reach
        recent_posts = posts[:3]
        
        for post in recent_posts:
            reach = post.get("reach", 0)
            impressions = post.get("impressions", 0)
            
            if reach > 0 and impressions > 0:
                impressions_ratio = impressions / reach
                
                # Normally impressions should be 1.5-3x reach
                if impressions_ratio < 0.5:
                    logger.warning(f"⚠️ Low impressions ratio: {impressions_ratio:.2f}")
                    return {
                        "status": "warning",
                        "reason": "Abnormally low impressions - posts may be throttled",
                        "severity": 5
                    }
        
        return {"status": "ok", "reason": "Impression ratios normal", "severity": 0}
    
    def send_alert(self, detection_result: Dict):
        """
        Send email alert about potential ban.
        
        Args:
            detection_result: Result from check_for_shadowban()
        """
        email = os.getenv("ALERT_EMAIL")
        if not email:
            logger.warning("⚠️ ALERT_EMAIL not configured - cannot send alert")
            logger.warning("Would have sent: %s", detection_result['reason'])
            return
        
        severity = detection_result.get("severity", 0)
        emoji = "🚨" if severity >= 7 else "⚠️"
        
        subject = f"{emoji} Facebook Automation Alert - Severity {severity}/10"
        
        body = f"""
{emoji} FACEBOOK AUTOMATION ALERT

Severity: {severity}/10
Status: {detection_result['status']}
Reason: {detection_result['reason']}

Detection Details:
{self._format_detection_details(detection_result)}

Timestamp: {datetime.now(timezone.utc).isoformat()} UTC

Recommended Actions:
1. Check your Facebook page manually
2. Review recent post performance
3. Consider pausing automation for 24-48 hours
4. Verify page hasn't been restricted

---
Content Factory Automation System
        """
        
        # Route through central alert system (Discord/Email/Log)
        try:
            from alert_system import send_alert, AlertLevel
            alert_level = AlertLevel.CRITICAL if severity >= 7 else AlertLevel.WARNING
            send_alert(subject, body, alert_level)
        except ImportError:
            # Fallback to direct email if alert_system unavailable
            success = self._send_email(email, subject, body)
            if success:
                logger.info("✅ Alert email sent to %s", email)
            else:
                logger.error("❌ Failed to send alert to %s", email)
    
    def _format_detection_details(self, result: Dict) -> str:
        """Format detection results for email."""
        details = []
        
        if "recent_avg" in result:
            details.append(f"- Recent avg reach: {result['recent_avg']:.0f}")
            details.append(f"- Older avg reach: {result['older_avg']:.0f}")
            details.append(f"- Drop ratio: {result['drop_ratio']:.2%}")
        
        if "recent_rate" in result:
            details.append(f"- Recent engagement: {result['recent_rate']:.2f}%")
            details.append(f"- Older engagement: {result['older_rate']:.2f}%")
        
        return "\n".join(details) if details else "No additional details"
    
    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        
        if not smtp_user or not smtp_pass:
            logger.warning("SMTP credentials not configured")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            return True
        
        except Exception as e:
            logger.error("SMTP error: %s", e)
            return False
    
    def auto_pause_if_needed(self, detection_result: Dict) -> bool:
        """
        Auto-pause automation if severe ban detected.
        
        Args:
            detection_result: Result from check_for_shadowban()
        
        Returns:
            True if automation should pause
        """
        severity = detection_result.get("severity", 0)
        
        if severity >= 7:
            logger.warning(f"🛑 HIGH SEVERITY ({severity}/10) - AUTO-PAUSING AUTOMATION")
            self.send_alert(detection_result)
            return True
        
        elif severity >= 5:
            logger.warning(f"⚠️ MODERATE SEVERITY ({severity}/10) - ALERT SENT")
            self.send_alert(detection_result)
            return False  # Continue but watch closely
        
        return False


# Global instance
_detector = None


def get_detector(page_id: Optional[str] = None) -> BanDetector:
    """Get or create ban detector instance."""
    global _detector
    if _detector is None or (page_id and _detector.page_id != page_id):
        _detector = BanDetector(page_id)
    return _detector


# Convenience functions
def check_for_shadowban(page_id: Optional[str] = None) -> Dict:
    """Check for shadowban indicators."""
    detector = get_detector(page_id)
    return detector.check_for_shadowban()


def should_pause_automation(page_id: Optional[str] = None) -> bool:
    """Check if automation should pause due to ban risk."""
    detector = get_detector(page_id)
    result = detector.check_for_shadowban()
    return detector.auto_pause_if_needed(result)


if __name__ == "__main__":
    print("🔍 Testing Ban Detector...\n")
    
    detector = BanDetector()
    
    # Run shadowban check
    print("🔍 Running shadowban detection:")
    result = detector.check_for_shadowban()
    
    print(f"  Status: {result['status']}")
    print(f"  Reason: {result['reason']}")
    print(f"  Severity: {result.get('severity', 0)}/10")
    
    # Test auto-pause logic
    print("\n🛑 Testing auto-pause logic:")
    should_pause = detector.auto_pause_if_needed(result)
    
    if should_pause:
        print("  ⏸️ Automation would pause")
    else:
        print("  ▶️ Automation would continue")
    
    print("\n✅ Ban detector tests complete!")
