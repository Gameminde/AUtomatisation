"""Image generator for Instagram-style posts with Arabic text."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config

# Try to import Arabic text support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False

logger = config.get_logger("image_generator")

# Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "Publication Instagram - Transforming the  Future of Business (1).png"
OUTPUT_DIR = BASE_DIR / "generated_images"
FONTS_DIR = BASE_DIR / "fonts"

# Create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

# Default configuration - can be adjusted manually
DEFAULT_CONFIG = {
    # Image dimensions
    "canvas_width": 640,
    "canvas_height": 800,
    # Article image placement (cover crop, centered)
    "image_area_top": 80,  # Start below social icons
    "image_area_bottom": 620,  # End before text area
    "image_area_left": 0,
    "image_area_right": 640,
    # Text area
    "text_area_top": 630,
    "text_area_bottom": 780,
    "text_padding_x": 30,
    # Text styling
    "text_color": (255, 200, 50),  # Gold/amber color
    "text_font_size": 32,
    "text_line_spacing": 8,
    "text_max_lines": 3,
    # Image overlay (optional darkening)
    "image_overlay_alpha": 0,  # 0 = no overlay, 50 = slight darken
}


def load_config() -> dict:
    """Load configuration, allowing manual overrides from config file."""
    config_path = BASE_DIR / "image_config.json"
    if config_path.exists():
        import json

        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            return {**DEFAULT_CONFIG, **user_config}
    return DEFAULT_CONFIG.copy()


def save_config(config_dict: dict) -> None:
    """Save configuration for manual adjustments."""
    import json

    config_path = BASE_DIR / "image_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)
    logger.info("Configuration saved to %s", config_path)


def get_arabic_font(size: int = 32) -> ImageFont.FreeTypeFont:
    """Get a font that supports BOTH Arabic and Latin characters."""
    # Priority: Fonts that support Arabic AND Latin (for mixed text like "Facebook")
    font_candidates = [
        # Windows fonts that support Arabic + Latin (BEST for mixed content)
        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold - supports Arabic + Latin
        "C:/Windows/Fonts/tahomabd.ttf",  # Tahoma Bold - supports Arabic + Latin
        "C:/Windows/Fonts/seguibl.ttf",  # Segoe UI Black - supports Arabic + Latin
        # Custom fonts (Arabic only - fallback)
        str(FONTS_DIR / "NotoSansArabic-Bold.ttf"),
        str(FONTS_DIR / "arabic_bold.ttf"),
        # Regular fonts (fallback)
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]

    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                logger.info("Loaded mixed Arabic+Latin font: %s", font_path)
                return font
            except Exception as e:
                logger.warning("Failed to load font %s: %s", font_path, e)
                continue

    # Fallback to default
    logger.warning("No Arabic font found, using default")
    return ImageFont.load_default()


def prepare_arabic_text(text: str) -> str:
    """
    Reshape and reorder Arabic text for correct RTL display.
    Handles mixed Arabic/English text (brand names stay in original order).
    """
    if not ARABIC_SUPPORT:
        logger.warning("Arabic support not available (install arabic-reshaper python-bidi)")
        return text

    try:
        import re

        # Detect if text contains both Arabic and English
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
        has_english = bool(re.search(r"[A-Za-z]", text))

        if has_arabic and has_english:
            # Mixed text: special handling
            # Strategy: reshape Arabic parts, keep English as-is, then apply BiDi

            # Split text into Arabic and English segments
            segments = re.split(r"([A-Za-z0-9:]+(?:\s+[A-Za-z0-9:]+)*)", text)

            processed_segments = []
            for segment in segments:
                if not segment.strip():
                    continue

                # Check if this segment is English (brand name, etc.)
                if re.match(r"^[A-Za-z0-9:\s]+$", segment.strip()):
                    # English segment - keep as-is
                    processed_segments.append(segment.strip())
                else:
                    # Arabic segment - reshape only
                    reshaped = arabic_reshaper.reshape(segment)
                    processed_segments.append(reshaped)

            # Join and apply BiDi algorithm
            combined = " ".join(processed_segments)
            bidi_text = get_display(combined)

            logger.debug(f"Mixed text processed: {text[:30]}... -> {bidi_text[:30]}...")
            return bidi_text

        elif has_arabic:
            # Pure Arabic text
            reshaped = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped)
            return bidi_text
        else:
            # Pure English text
            return text

    except Exception as exc:
        logger.error("Arabic text processing failed: %s", exc)
        return text


def wrap_text(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 3
) -> list[str]:
    """Wrap text to fit within max_width, limiting to max_lines."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = font.getbbox(test_line)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

            if len(lines) >= max_lines:
                break

    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))

    return lines[:max_lines]


def crop_and_fit_image(
    image: Image.Image,
    target_width: int,
    target_height: int,
) -> Image.Image:
    """Crop and resize image to fill target area (cover crop, centered)."""
    img_width, img_height = image.size

    # Calculate aspect ratios
    target_ratio = target_width / target_height
    img_ratio = img_width / img_height

    if img_ratio > target_ratio:
        # Image is wider - crop sides
        new_width = int(img_height * target_ratio)
        left = (img_width - new_width) // 2
        image = image.crop((left, 0, left + new_width, img_height))
    else:
        # Image is taller - crop top/bottom
        new_height = int(img_width / target_ratio)
        top = (img_height - new_height) // 2
        image = image.crop((0, top, img_width, top + new_height))

    # Resize to exact target size
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def generate_post_image(
    article_image_path: Optional[str] = None,
    text: str = "",
    output_path: Optional[str] = None,
    config_overrides: Optional[dict] = None,
    template_path: Optional[str] = None,
) -> str:
    """
    Generate an Instagram post image with template, article image, and Arabic text.

    Args:
        article_image_path: Path to article/news image (optional)
        text: Text to display (Arabic supported)
        output_path: Where to save the result
        config_overrides: Override default configuration values
        template_path: Path to specific template image to use
    """
    # Load configuration
    cfg = load_config()
    if config_overrides:
        cfg.update(config_overrides)

    # Convert color from list to tuple (JSON stores as list)
    if isinstance(cfg.get("text_color"), list):
        cfg["text_color"] = tuple(cfg["text_color"])

    # Load template
    # Use provided template_path, or fallback to default TEMPLATE_PATH
    target_template = Path(template_path) if template_path else TEMPLATE_PATH
    
    if not target_template.exists():
        # Fallback to default if specific template missing
        logger.warning(f"Template not found: {target_template}, falling back to default")
        target_template = TEMPLATE_PATH
        
    if not target_template.exists():
        raise FileNotFoundError(f"Default template not found: {TEMPLATE_PATH}")

    template = Image.open(target_template).convert("RGBA")
    canvas_width, canvas_height = template.size

    # Update config with actual template size
    cfg["canvas_width"] = canvas_width
    cfg["canvas_height"] = canvas_height

    # Create result image starting with template
    result = template.copy()

    # Add article image if provided (placed ON TOP of template in designated area)
    if article_image_path and os.path.exists(article_image_path):
        try:
            article_img = Image.open(article_image_path).convert("RGBA")

            # Calculate image area dimensions
            img_area_width = cfg["image_area_right"] - cfg["image_area_left"]
            img_area_height = cfg["image_area_bottom"] - cfg["image_area_top"]

            # Crop and fit
            fitted_img = crop_and_fit_image(article_img, img_area_width, img_area_height)

            # Apply overlay if configured (darken image)
            if cfg["image_overlay_alpha"] > 0:
                overlay = Image.new("RGBA", fitted_img.size, (0, 0, 0, cfg["image_overlay_alpha"]))
                fitted_img = Image.alpha_composite(fitted_img, overlay)

            # Paste onto result (on top of template)
            result.paste(fitted_img, (cfg["image_area_left"], cfg["image_area_top"]))

        except Exception as exc:
            logger.error("Failed to process article image: %s", exc)

    # Add text
    if text:
        draw = ImageDraw.Draw(result)
        font = get_arabic_font(cfg["text_font_size"])

        # Prepare Arabic text
        display_text = prepare_arabic_text(text)

        # Calculate text area
        text_area_width = canvas_width - (2 * cfg["text_padding_x"])

        # Wrap text
        lines = wrap_text(display_text, font, text_area_width, cfg["text_max_lines"])

        # Calculate total text height
        line_height = cfg["text_font_size"] + cfg["text_line_spacing"]
        total_text_height = len(lines) * line_height

        # Center text vertically in text area
        text_area_height = cfg["text_area_bottom"] - cfg["text_area_top"]
        start_y = cfg["text_area_top"] + (text_area_height - total_text_height) // 2

        # Draw each line (centered horizontally)
        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            x = (canvas_width - line_width) // 2
            y = start_y + (i * line_height)

            # Draw text with slight shadow for visibility
            shadow_color = (0, 0, 0, 128)
            draw.text((x + 2, y + 2), line, font=font, fill=shadow_color)
            draw.text((x, y), line, font=font, fill=cfg["text_color"])

    # Convert to RGB for saving as PNG/JPEG
    result_rgb = result.convert("RGB")

    # Generate output path
    if output_path is None:
        import uuid

        output_path = str(OUTPUT_DIR / f"post_{uuid.uuid4().hex[:8]}.png")

    # Save
    result_rgb.save(output_path, quality=95)
    logger.info("Generated image: %s", output_path)

    return output_path


def preview_config() -> str:
    """Generate a preview image with current configuration to help with manual adjustment."""
    cfg = load_config()

    # Load template
    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(template)

    # Draw configuration overlay
    # Image area box
    draw.rectangle(
        [
            cfg["image_area_left"],
            cfg["image_area_top"],
            cfg["image_area_right"],
            cfg["image_area_bottom"],
        ],
        outline=(255, 0, 0, 255),
        width=2,
    )
    draw.text(
        (cfg["image_area_left"] + 10, cfg["image_area_top"] + 10),
        "IMAGE AREA",
        fill=(255, 0, 0),
    )

    # Text area box
    draw.rectangle(
        [
            cfg["text_padding_x"],
            cfg["text_area_top"],
            template.width - cfg["text_padding_x"],
            cfg["text_area_bottom"],
        ],
        outline=(0, 255, 0, 255),
        width=2,
    )
    draw.text(
        (cfg["text_padding_x"] + 10, cfg["text_area_top"] + 10),
        "TEXT AREA",
        fill=(0, 255, 0),
    )

    # Save preview
    preview_path = str(OUTPUT_DIR / "config_preview.png")
    template.save(preview_path)

    # Also save current config
    save_config(cfg)

    logger.info("Preview saved: %s", preview_path)
    logger.info("Edit image_config.json to adjust, then run preview again")

    return preview_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        # Generate preview for configuration adjustment
        preview_path = preview_config()
        print(f"Preview generated: {preview_path}")
        print("Edit image_config.json to adjust parameters")
    else:
        # Test with sample text
        test_text = "لم نعد في عصر كتابة الكود، نحن في عصر إدارة الذكاء الاصطناعي"
        output = generate_post_image(
            text=test_text,
            output_path=str(OUTPUT_DIR / "test_arabic.png"),
        )
        print(f"Test image generated: {output}")
