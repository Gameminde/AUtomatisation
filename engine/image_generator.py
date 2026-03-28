"""Carousel slide rendering helpers built on top of the legacy image generator."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
import uuid

from PIL import Image, ImageDraw

import config
from image_generator import OUTPUT_DIR, get_arabic_font, prepare_arabic_text, wrap_text

logger = config.get_logger("engine.image_generator")

DEFAULT_BRAND_COLOR = "#F9C74F"
DEFAULT_BACKGROUND_COLOR = "#12100E"
DEFAULT_SURFACE_COLOR = "#1B1713"
DEFAULT_TEXT_COLOR = "#F7F3EE"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    value = (hex_color or DEFAULT_BRAND_COLOR).strip().lstrip("#")
    if len(value) != 6:
        value = DEFAULT_BRAND_COLOR.lstrip("#")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except Exception:
        return (249, 199, 79)


def _build_output_path(prefix: str) -> str:
    return str(Path(OUTPUT_DIR) / f"{prefix}_{uuid.uuid4().hex[:10]}.png")


def _draw_centered_lines(draw: ImageDraw.ImageDraw, lines, font, *, center_y: int, width: int, color):
    line_height = int(font.size * 1.35)
    total_height = len(lines) * line_height
    y = center_y - (total_height // 2)
    for line in lines:
        bbox = font.getbbox(line)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 140))
        draw.text((x, y), line, font=font, fill=color)
        y += line_height


def generate_carousel_slide(
    headline: str,
    body: str,
    *,
    slide_number: int,
    brand_color: str = DEFAULT_BRAND_COLOR,
    output_path: str | None = None,
) -> str:
    """Generate a clean 1080x1080 carousel slide image."""
    width = 1080
    height = 1080
    accent = _hex_to_rgb(brand_color)
    background = _hex_to_rgb(DEFAULT_BACKGROUND_COLOR)
    surface = _hex_to_rgb(DEFAULT_SURFACE_COLOR)
    text_color = _hex_to_rgb(DEFAULT_TEXT_COLOR)

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image, "RGBA")

    draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=48, fill=surface)
    draw.rectangle((96, 96, width - 96, 118), fill=accent)

    headline_font = get_arabic_font(78)
    body_font = get_arabic_font(44)
    slide_font = get_arabic_font(34)

    display_headline = prepare_arabic_text((headline or "").strip())
    display_body = prepare_arabic_text((body or "").strip())

    headline_lines = wrap_text(display_headline, headline_font, width - 220, max_lines=3)
    body_lines = wrap_text(display_body, body_font, width - 220, max_lines=5)

    _draw_centered_lines(draw, headline_lines, headline_font, center_y=330, width=width, color=text_color)
    _draw_centered_lines(draw, body_lines, body_font, center_y=650, width=width, color=(230, 224, 214))

    indicator_text = f"{slide_number:02d}"
    indicator_bbox = slide_font.getbbox(indicator_text)
    indicator_width = indicator_bbox[2] - indicator_bbox[0]
    indicator_height = indicator_bbox[3] - indicator_bbox[1]
    indicator_left = width - 160
    indicator_top = height - 130
    draw.rounded_rectangle(
        (
            indicator_left - 26,
            indicator_top - 14,
            indicator_left + indicator_width + 26,
            indicator_top + indicator_height + 22,
        ),
        radius=24,
        fill=accent + (255,),
    )
    draw.text((indicator_left, indicator_top), indicator_text, font=slide_font, fill=background)

    target_path = output_path or _build_output_path(f"carousel_slide_{slide_number}")
    image.save(target_path, quality=95)
    logger.info("Generated carousel slide: %s", target_path)
    return target_path


def generate_carousel_placeholder(
    headline: str,
    *,
    slide_number: int,
    brand_color: str = DEFAULT_BRAND_COLOR,
    output_path: str | None = None,
) -> str:
    """Fallback slide when richer image generation fails."""
    return generate_carousel_slide(
        headline=headline,
        body="",
        slide_number=slide_number,
        brand_color=brand_color,
        output_path=output_path,
    )
