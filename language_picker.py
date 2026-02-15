"""
Language Picker - Multi-language support for Content Factory v3.0.

Features:
- Weighted language selection (AR 80%, FR 15%, EN 5%)
- Keep-English Glossary for Arabic content
- CTA templates per language
- Dynamic configuration via brand_config.json
"""

from __future__ import annotations

import random
import json
import os
from typing import Dict, List, Tuple

# Default Configuration
DEFAULT_LANGUAGE_WEIGHTS = {
    "AR": 0.80,
    "FR": 0.15,
    "EN": 0.05
}

DEFAULT_GLOSSARY = [
    "Discord", "IELTS", "Email Marketing", "Open Source", "Self-Hosted",
    "Rate Limit", "Gemini", "GPT", "Claude", "API", "SaaS", "Mailchimp",
    "Automation", "Productivity", "AI", "Crypto", "GPU", "NVIDIA", "Apple",
    "Google", "Meta", "ChatGPT", "OpenAI", "Tesla", "Microsoft", "Facebook",
    "Instagram", "WhatsApp", "YouTube", "TikTok", "LinkedIn", "Twitter", "X",
    "iPhone", "Android", "iOS", "Windows", "Linux", "Mac", "Python", "JavaScript"
]

CTA_TEMPLATES = {
    "AR": "🔗 الرابط: {LINK}",
    "FR": "🔗 Lien : {LINK}",
    "EN": "🔗 Link: {LINK}"
}

LANGUAGE_NAMES = {
    "AR": "Arabic (العربية)",
    "FR": "French (Français)",
    "EN": "English"
}

CONFIG_FILE = 'brand_config.json'

def load_config() -> Tuple[Dict[str, float], List[str]]:
    """
    Load configuration from JSON file or return defaults.
    """
    weights = DEFAULT_LANGUAGE_WEIGHTS.copy()
    glossary = DEFAULT_GLOSSARY[:]
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # Update weights if present
                if 'language_weights' in config:
                    # Normalize weights to sum to 1.0 (or check if they are percentage 0-100)
                    raw_weights = config['language_weights']
                    total = sum(raw_weights.values())
                    if total > 0:
                        weights = {k: v / total for k, v in raw_weights.items()}
                
                # Update glossary if present
                if 'glossary' in config:
                    glossary = config['glossary']
        except Exception as e:
            print(f"Warning: Failed to load brand config: {e}")
            
    return weights, glossary


def pick_language() -> str:
    """
    Pick a language based on weighted distribution.
    Read config fresh on each call to support runtime changes.
    """
    weights, _ = load_config()
    
    return random.choices(
        list(weights.keys()),
        weights=list(weights.values())
    )[0]


def get_cta(lang: str, link: str = "") -> str:
    """Get CTA text for the given language."""
    template = CTA_TEMPLATES.get(lang, CTA_TEMPLATES["EN"])
    return template.format(LINK=link if link else "[LINK]")


def get_glossary_string() -> str:
    """Get glossary as comma-separated string for prompt injection."""
    _, glossary = load_config()
    return ", ".join(glossary)


def apply_glossary_reminder(text: str, lang: str) -> str:
    """For Arabic content, remind that English terms should stay in English."""
    if lang != "AR":
        return text
    # The glossary terms are already handled in the LLM prompt
    return text


def get_language_config(lang: str) -> Dict:
    """Get full configuration for a language."""
    _, glossary = load_config()
    return {
        "code": lang,
        "name": LANGUAGE_NAMES.get(lang, lang),
        "cta_template": CTA_TEMPLATES.get(lang, CTA_TEMPLATES["EN"]),
        "text_direction": "rtl" if lang == "AR" else "ltr",
        "glossary": glossary if lang == "AR" else []
    }


if __name__ == "__main__":
    # Test language distribution
    print("Testing Language Picker with Dynamic Config...")
    
    # Create a dummy config for test if not exists
    if not os.path.exists(CONFIG_FILE):
        print("Creating temporary config for test...")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "language_weights": {"AR": 50, "FR": 50, "EN": 0},
                "glossary": ["TEST_TERM"]
            }, f)
            
    current_weights, current_glossary = load_config()
    print(f"Loaded Weights: {current_weights}")
    print(f"Loaded Glossary (first 5): {current_glossary[:5]}...")
    
    results = {"AR": 0, "FR": 0, "EN": 0}
    for _ in range(100):
        lang = pick_language()
        if lang in results:
            results[lang] += 1
    
    print("Distribution (100 picks):")
    for lang, count in results.items():
        print(f"  {lang}: {count}%")
        
    # Clean up test config if it was created just now? 
    # Better leave it or manual clean.

