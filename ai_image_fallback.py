"""
AI Image Fallback - Generate images when stock photos fail.

Uses Gemini or other AI image generation as fallback when
Pexels/Unsplash don't have suitable images.
"""

import os
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests

import config

logger = config.get_logger("ai_image_fallback")

# Paths
BASE_DIR = Path(__file__).parent
AI_IMAGES_DIR = BASE_DIR / "ai_generated_images"
AI_IMAGES_DIR.mkdir(exist_ok=True)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class AIImageFallback:
    """Generate AI images when stock photos aren't available."""
    
    STYLE_PROMPTS = {
        "photorealistic": "photorealistic, high quality, professional photography, 8k resolution",
        "digital_art": "digital art, vibrant colors, modern style, trending on artstation",
        "minimalist": "minimalist design, clean, simple, modern, professional",
        "futuristic": "futuristic, sci-fi, neon lights, cyberpunk aesthetic",
        "tech": "technology themed, modern devices, clean tech aesthetic"
    }
    
    def __init__(self):
        """Initialize AI image generator."""
        self.gemini_available = bool(GEMINI_API_KEY)
        self.openai_available = bool(OPENAI_API_KEY)
        
        if self.gemini_available:
            logger.info("✅ Gemini API available for image generation")
        if self.openai_available:
            logger.info("✅ OpenAI DALL-E available for image generation")
        
        if not self.gemini_available and not self.openai_available:
            logger.warning("⚠️ No AI image generation APIs configured")
    
    def generate_image(
        self,
        prompt: str,
        style: str = "tech",
        size: str = "1024x1024",
        provider: str = "auto"
    ) -> Optional[str]:
        """
        Generate an AI image.
        
        Args:
            prompt: Description of the image to generate
            style: Style preset (photorealistic, digital_art, etc.)
            size: Image size (1024x1024, 512x512)
            provider: API to use (auto, gemini, openai)
        
        Returns:
            Path to generated image or None
        """
        # Enhance prompt with style
        style_suffix = self.STYLE_PROMPTS.get(style, self.STYLE_PROMPTS["tech"])
        full_prompt = f"{prompt}, {style_suffix}"
        
        logger.info(f"🎨 Generating AI image: {prompt[:50]}...")
        
        # Auto-select provider
        if provider == "auto":
            if self.openai_available:
                return self._generate_with_openai(full_prompt, size)
            elif self.gemini_available:
                return self._generate_with_gemini(full_prompt, size)
            else:
                logger.error("No AI image generation API available")
                return None
        elif provider == "openai" and self.openai_available:
            return self._generate_with_openai(full_prompt, size)
        elif provider == "gemini" and self.gemini_available:
            return self._generate_with_gemini(full_prompt, size)
        else:
            logger.error(f"Provider {provider} not available")
            return None
    
    def _generate_with_openai(self, prompt: str, size: str) -> Optional[str]:
        """Generate image using OpenAI DALL-E."""
        try:
            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "response_format": "b64_json"
            }
            
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            resp.raise_for_status()
            
            result = resp.json()
            image_data = result["data"][0]["b64_json"]
            
            # Save image
            output_path = AI_IMAGES_DIR / f"dalle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(image_data))
            
            logger.info(f"✅ DALL-E image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"DALL-E error: {e}")
            return None
    
    def _generate_with_gemini(self, prompt: str, size: str) -> Optional[str]:
        """Generate image using Google Gemini."""
        try:
            # Gemini image generation API (Imagen)
            url = f"https://generativelanguage.googleapis.com/v1/models/imagen-3.0-generate-002:generateImage?key={GEMINI_API_KEY}"
            
            data = {
                "prompt": prompt,
                "numberOfImages": 1,
                "aspectRatio": "1:1" if "1024x1024" in size else "16:9"
            }
            
            resp = requests.post(url, json=data, timeout=60)
            
            if resp.status_code == 200:
                result = resp.json()
                if "predictions" in result and result["predictions"]:
                    image_data = result["predictions"][0].get("bytesBase64Encoded")
                    if image_data:
                        output_path = AI_IMAGES_DIR / f"gemini_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        with open(output_path, 'wb') as f:
                            f.write(base64.b64decode(image_data))
                        
                        logger.info(f"✅ Gemini image saved: {output_path}")
                        return str(output_path)
            
            logger.warning(f"Gemini response: {resp.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return None
    
    def generate_for_topic(
        self,
        topic_title: str,
        topic_keywords: list = None,
        style: str = "tech"
    ) -> Optional[str]:
        """
        Generate an image relevant to a topic.
        
        Args:
            topic_title: Title of the article/topic
            topic_keywords: Keywords from AI content generation
            style: Visual style
        
        Returns:
            Path to generated image
        """
        # Build descriptive prompt
        if topic_keywords:
            keywords_str = ", ".join(topic_keywords[:3])
            prompt = f"Technology concept image showing {keywords_str}, related to: {topic_title}"
        else:
            prompt = f"Modern technology concept image related to: {topic_title}"
        
        return self.generate_image(prompt, style)
    
    def is_available(self) -> bool:
        """Check if any AI image generation is available."""
        return self.gemini_available or self.openai_available
    
    def get_status(self) -> Dict:
        """Get status of available providers."""
        return {
            "gemini": self.gemini_available,
            "openai": self.openai_available,
            "any_available": self.is_available()
        }


# Global instance
_fallback = None


def get_fallback() -> AIImageFallback:
    """Get or create AI image fallback instance."""
    global _fallback
    if _fallback is None:
        _fallback = AIImageFallback()
    return _fallback


def generate_ai_image(prompt: str, style: str = "tech") -> Optional[str]:
    """Quick access to generate AI image."""
    fallback = get_fallback()
    return fallback.generate_image(prompt, style)


def generate_for_topic(title: str, keywords: list = None) -> Optional[str]:
    """Generate image for a specific topic."""
    fallback = get_fallback()
    return fallback.generate_for_topic(title, keywords)


def is_ai_available() -> bool:
    """Check if AI image generation is available."""
    fallback = get_fallback()
    return fallback.is_available()


# Integration function for unified_content_creator
def get_image_with_fallback(
    image_info: Dict,
    article_title: str,
    pexels_search_func=None,
    unsplash_search_func=None
) -> Optional[str]:
    """
    Try stock photos first, then fall back to AI generation.
    
    Args:
        image_info: Image info from AI content generation
        article_title: Title for context
        pexels_search_func: Function to search Pexels
        unsplash_search_func: Function to search Unsplash
    
    Returns:
        Path to image (stock or AI-generated)
    """
    keywords = image_info.get("keywords_en", ["technology"])
    query = " ".join(keywords[:3])
    
    # 1. Try Pexels
    if pexels_search_func:
        result = pexels_search_func(query)
        if result:
            logger.info("✅ Found image on Pexels")
            return result
    
    # 2. Try Unsplash
    if unsplash_search_func:
        result = unsplash_search_func(query)
        if result:
            logger.info("✅ Found image on Unsplash")
            return result
    
    # 3. Fall back to AI generation
    logger.info("🔄 No stock image found, trying AI generation...")
    fallback = get_fallback()
    
    if fallback.is_available():
        style = image_info.get("style", "tech")
        result = fallback.generate_for_topic(article_title, keywords, style)
        if result:
            logger.info("✅ Generated AI image as fallback")
            return result
    
    logger.warning("❌ No image available (stock or AI)")
    return None


if __name__ == "__main__":
    print("🎨 Testing AI Image Fallback...\n")
    
    fallback = AIImageFallback()
    
    # Show status
    status = fallback.get_status()
    print("📊 Provider Status:")
    print(f"  Gemini: {'✅' if status['gemini'] else '❌'}")
    print(f"  OpenAI: {'✅' if status['openai'] else '❌'}")
    print(f"  Any available: {'✅' if status['any_available'] else '❌'}")
    
    if status['any_available']:
        print("\n🎨 Testing image generation...")
        
        result = fallback.generate_image(
            prompt="Futuristic AI robot with holographic display",
            style="futuristic"
        )
        
        if result:
            print(f"✅ Generated: {result}")
        else:
            print("❌ Generation failed")
    else:
        print("\n⚠️ Configure API keys to enable AI image generation:")
        print("  GEMINI_API_KEY=your_key")
        print("  OPENAI_API_KEY=your_key")
    
    print("\n✅ AI Image Fallback tests complete!")
