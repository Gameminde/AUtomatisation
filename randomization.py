"""
Randomization Module - Add human-like variations to content and scheduling.

This module prevents Meta's bot detection by:
- Varying post intervals (not fixed 2h)
- Adjusting text length randomly
- Randomizing hashtag counts
- Adding human touches (emojis, spacing)
"""

import random
import re
from datetime import timedelta
from typing import List, Tuple

import config

logger = config.get_logger("randomization")


class ContentRandomizer:
    """Add human-like variations to content and scheduling."""
    
    # Emojis commonly used in tech/gaming posts
    TECH_EMOJIS = ["🔥", "💡", "⚡", "🚀", "🎯", "✨", "💻", "🎮", "🤖", "📱"]
    
    # Arabic filler phrases for natural variation
    ARABIC_FILLERS = [
        "بالمناسبة، ",
        "من المثير للاهتمام أن ",
        "والجدير بالذكر أن ",
        "في الواقع، ",
        "للتوضيح، ",
        "ببساطة، ",
    ]
    
    def randomize_interval(
        self, 
        min_hours: float = 2.0, 
        max_hours: float = 4.0
    ) -> timedelta:
        """
        Random post spacing to avoid robotic patterns.
        
        Args:
            min_hours: Minimum hours between posts
            max_hours: Maximum hours between posts
        
        Returns:
            Random timedelta for scheduling
        """
        hours = random.uniform(min_hours, max_hours)
        logger.debug(f"🎲 Random interval: {hours:.2f} hours")
        return timedelta(hours=hours)
    
    def vary_text_length(
        self, 
        text: str, 
        target_range: Tuple[int, int] = (300, 600)
    ) -> str:
        """
        Adjust text length by adding/removing filler words.
        
        Args:
            text: Original text
            target_range: (min_length, max_length) tuple
        
        Returns:
            Text adjusted to fit target range
        """
        current_len = len(text)
        min_len, max_len = target_range
        
        if current_len < min_len:
            # Add context phrases
            text = random.choice(self.ARABIC_FILLERS) + text
            logger.debug(f"📝 Extended text: {current_len} → {len(text)} chars")
        
        elif current_len > max_len:
            # Trim without breaking meaning
            text = text[:max_len - 3] + "..."
            logger.debug(f"✂️ Trimmed text: {current_len} → {len(text)} chars")
        
        return text
    
    def randomize_hashtags(
        self, 
        hashtags: List[str], 
        min_tags: int = 5, 
        max_tags: int = 8
    ) -> List[str]:
        """
        Vary hashtag count for natural variation.
        
        Args:
            hashtags: List of all available hashtags
            min_tags: Minimum hashtags to use
            max_tags: Maximum hashtags to use
        
        Returns:
            Random subset of hashtags
        """
        if not hashtags:
            return []
        
        count = random.randint(min_tags, min(max_tags, len(hashtags)))
        selected = random.sample(hashtags, count)
        
        logger.debug(f"#️⃣ Selected {count} hashtags from {len(hashtags)} available")
        return selected
    
    def add_human_touch(self, text: str) -> str:
        """
        Add emojis and human-like variations.
        
        Args:
            text: Original text
        
        Returns:
            Text with human touches added
        """
        # 40% chance to add emoji at start
        if random.random() < 0.4:
            emoji = random.choice(self.TECH_EMOJIS)
            text = f"{emoji} {text}"
            logger.debug(f"✨ Added emoji: {emoji}")
        
        # 15% chance to add emoji at end
        if random.random() < 0.15:
            emoji = random.choice(self.TECH_EMOJIS)
            text = f"{text} {emoji}"
        
        # 10% chance for intentional spacing variation (human-like)
        if random.random() < 0.1:
            # Add occasional double space (natural typo)
            text = text.replace(". ", ".  ", 1)
            logger.debug("⌨️ Added human-like spacing variation")
        
        return text
    
    def add_minute_jitter(self, scheduled_time) -> timedelta:
        """
        Add random minutes to scheduled time (avoid posting at exact hours).
        
        Args:
            scheduled_time: Original scheduled time
        
        Returns:
            Jitter to add (5-25 minutes)
        """
        minutes = random.randint(5, 25)
        logger.debug(f"⏰ Time jitter: +{minutes} minutes")
        return timedelta(minutes=minutes)
    
    def should_skip_post(self, engagement_rate: float) -> bool:
        """
        Randomly skip post if engagement is low (human behavior).
        
        Args:
            engagement_rate: Recent engagement rate (0-100)
        
        Returns:
            True if should skip this post
        """
        if engagement_rate < 0.5:
            # 30% chance to skip when engagement is very low
            skip = random.random() < 0.3
            if skip:
                logger.info("⏭️ Skipping post due to low engagement (human-like)")
            return skip
        
        return False
    
    def vary_post_format(self, text: str) -> str:
        """
        Occasionally vary post format (line breaks, bullet points).
        
        Args:
            text: Original text
        
        Returns:
            Text with varied formatting
        """
        # 20% chance to add line breaks for readability
        if random.random() < 0.2:
            sentences = text.split('. ')
            if len(sentences) > 3:
                # Add line break after 2-3 sentences
                break_point = random.randint(2, 3)
                sentences[break_point] = sentences[break_point] + '\n\n'
                text = '. '.join(sentences)
                logger.debug("📄 Added formatting variation (line breaks)")
        
        return text


# Global instance for easy access
_randomizer = ContentRandomizer()


def get_randomizer() -> ContentRandomizer:
    """Get the global randomizer instance."""
    return _randomizer


# Convenience functions
def randomize_interval(min_hours: float = 2.0, max_hours: float = 4.0) -> timedelta:
    """Get random interval for scheduling."""
    return _randomizer.randomize_interval(min_hours, max_hours)


def randomize_content(text: str, hashtags: List[str]) -> Tuple[str, List[str]]:
    """
    Apply all randomization to content.
    
    Args:
        text: Original text
        hashtags: List of hashtags
    
    Returns:
        (randomized_text, randomized_hashtags)
    """
    text = _randomizer.vary_text_length(text)
    text = _randomizer.add_human_touch(text)
    text = _randomizer.vary_post_format(text)
    hashtags = _randomizer.randomize_hashtags(hashtags)
    
    return text, hashtags


if __name__ == "__main__":
    print("🎲 Testing Content Randomizer...\n")
    
    randomizer = ContentRandomizer()
    
    # Test interval randomization
    print("⏰ Testing interval randomization:")
    for i in range(5):
        interval = randomizer.randomize_interval()
        print(f"  {i+1}. {interval.total_seconds() / 3600:.2f} hours")
    
    # Test text variations
    print("\n📝 Testing text variations:")
    test_text = "اكتشاف جديد في الذكاء الاصطناعي يغير كل شيء"
    for i in range(3):
        varied = randomizer.add_human_touch(test_text)
        print(f"  {i+1}. {varied}")
    
    # Test hashtag randomization
    print("\n#️⃣ Testing hashtag randomization:")
    test_hashtags = ["#AI", "#tech", "#innovation", "#gaming", "#future", "#Algeria", "#MENA", "#startup"]
    for i in range(3):
        selected = randomizer.randomize_hashtags(test_hashtags)
        print(f"  {i+1}. {', '.join(selected)}")
    
    print("\n✅ Randomization tests complete!")
