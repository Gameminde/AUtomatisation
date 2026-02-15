"""
Template Manager - Manages text and image templates for Content Factory v3.0.

Features:
- Load and select text templates by language
- Load and select image templates with anti-repeat
- Weighted random selection
- Template history tracking
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque

import config

logger = config.get_logger("template_manager")

BASE_DIR = Path(__file__).parent

# Track recently used templates to avoid repetition
_recent_text_templates: Dict[str, deque] = {"AR": deque(maxlen=3), "FR": deque(maxlen=2), "EN": deque(maxlen=2)}
_recent_image_templates: deque = deque(maxlen=3)


def load_text_templates() -> Dict:
    """Load text templates from JSON file."""
    path = BASE_DIR / "text_templates.json"
    if not path.exists():
        logger.warning("text_templates.json not found, using defaults")
        return _get_default_text_templates()
    
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_image_templates() -> Dict:
    """Load image templates from JSON file."""
    path = BASE_DIR / "image_templates.json"
    if not path.exists():
        logger.warning("image_templates.json not found, using defaults")
        return _get_default_image_templates()
    
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pick_text_template(lang: str) -> Dict:
    """
    Select a text template for the given language.
    Uses weighted random selection and avoids recent templates.
    
    Args:
        lang: Language code (AR/FR/EN)
    
    Returns:
        Template dict with id, name, structure, example
    """
    templates = load_text_templates()
    lang_data = templates.get(lang, templates.get("AR", {}))
    patterns = lang_data.get("patterns", [])
    
    if not patterns:
        logger.error(f"No patterns found for language {lang}")
        return _get_fallback_template(lang)
    
    # Filter out recently used templates
    recent = _recent_text_templates.get(lang, deque())
    available = [p for p in patterns if p["id"] not in recent]
    
    # If all templates were recently used, reset
    if not available:
        available = patterns
    
    # Weighted random selection
    weights = [p.get("weight", 1) for p in available]
    selected = random.choices(available, weights=weights)[0]
    
    # Track usage
    _recent_text_templates[lang].append(selected["id"])
    
    logger.info(f"📝 Selected text template: {selected['name']} ({lang})")
    return selected


def pick_image_template(exclude_ids: Optional[List[str]] = None) -> Dict:
    """
    Select an image template with anti-repeat rotation.
    
    Args:
        exclude_ids: Optional list of template IDs to exclude
    
    Returns:
        Template dict with id, name, config
    """
    templates = load_image_templates()
    layouts = templates.get("layouts", [])
    
    if not layouts:
        logger.error("No image layouts found")
        return _get_fallback_image_template()
    
    # Combine recent + explicit excludes
    exclude = set(exclude_ids or []) | set(_recent_image_templates)
    available = [l for l in layouts if l["id"] not in exclude]
    
    # If all templates excluded, reset
    if not available:
        available = layouts
    
    # Weighted random selection
    weights = [l.get("weight", 1) for l in available]
    selected = random.choices(available, weights=weights)[0]
    
    # Track usage
    _recent_image_templates.append(selected["id"])
    
    logger.info(f"🖼️ Selected image template: {selected['name']}")
    return selected


def get_template_config(template: Dict) -> Dict:
    """
    Get the image configuration from a template.
    
    Returns dict compatible with image_generator.generate_post_image()
    """
    config_data = template.get("config", {})
    
    # Convert to image_generator format
    return {
        "canvas_width": config_data.get("canvas_width", 1080),
        "canvas_height": config_data.get("canvas_height", 1350),
        "image_area_top": config_data.get("image_area_top", 316),
        "image_area_bottom": config_data.get("image_area_bottom", 991),
        "image_area_left": config_data.get("image_area_left", 35),
        "image_area_right": config_data.get("image_area_right", 1045),
        "text_area_top": config_data.get("text_area_top", 1045),
        "text_area_bottom": config_data.get("text_area_bottom", 1230),
        "text_padding_x": config_data.get("text_padding_x", 30),
        "text_color": tuple(config_data.get("text_color", [255, 200, 50])),
        "text_font_size": config_data.get("text_font_size", 76),
        "text_line_spacing": config_data.get("text_line_spacing", 8),
        "text_max_lines": config_data.get("text_max_lines", 3),
        "image_overlay_alpha": config_data.get("image_overlay_alpha", 45),
    }


def get_template_file(template: Dict) -> Optional[Path]:
    """Get the template file path if specified."""
    template_file = template.get("template_file")
    if template_file:
        path = BASE_DIR / template_file
        if path.exists():
            return path
    return None


def _get_fallback_template(lang: str) -> Dict:
    """Fallback template when none found."""
    return {
        "id": f"{lang.lower()}_fallback",
        "name": "Fallback",
        "weight": 1,
        "structure": "🔥 [HOOK]\n\n[BODY]\n\n🔗 {CTA}\n\n{HASHTAGS}",
        "example": ""
    }


def _get_fallback_image_template() -> Dict:
    """Fallback image template."""
    return {
        "id": "fallback",
        "name": "Fallback Classic",
        "template_file": None,
        "config": {
            "canvas_width": 1080,
            "canvas_height": 1350,
            "image_area_top": 316,
            "image_area_bottom": 991,
            "image_area_left": 35,
            "image_area_right": 1045,
            "text_area_top": 1045,
            "text_area_bottom": 1230,
            "text_padding_x": 30,
            "text_color": [255, 200, 50],
            "text_font_size": 76,
            "text_max_lines": 3,
            "image_overlay_alpha": 45
        }
    }


def _get_default_text_templates() -> Dict:
    """Default text templates if JSON not found."""
    return {
        "AR": {"patterns": [_get_fallback_template("AR")]},
        "FR": {"patterns": [_get_fallback_template("FR")]},
        "EN": {"patterns": [_get_fallback_template("EN")]}
    }


def _get_default_image_templates() -> Dict:
    """Default image templates if JSON not found."""
    return {"layouts": [_get_fallback_image_template()]}


if __name__ == "__main__":
    # Test template selection
    print("Testing text templates:")
    for lang in ["AR", "FR", "EN"]:
        template = pick_text_template(lang)
        print(f"  {lang}: {template['name']}")
    
    print("\nTesting image templates:")
    for _ in range(5):
        template = pick_image_template()
        print(f"  Selected: {template['name']}")
