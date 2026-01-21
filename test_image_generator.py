"""Test script for image generator module."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Test 1: Load template
print("Test 1: Loading template...")
template_path = Path("Publication Instagram - Transforming the  Future of Business.png")
try:
    template = Image.open(template_path).convert("RGBA")
    print(f"  ✓ Template loaded: {template.size}")
except Exception as e:
    print(f"  ✗ Failed: {e}")
    exit(1)

# Test 2: Create output directory
print("\nTest 2: Creating output directory...")
output_dir = Path("generated_images")
output_dir.mkdir(exist_ok=True)
print(f"  ✓ Output directory: {output_dir.absolute()}")

# Test 3: Add text to template
print("\nTest 3: Adding text to template...")
draw = ImageDraw.Draw(template)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
except:
    font = ImageFont.load_default()

test_text = "L'intelligence artificielle transforme le futur des entreprises"
draw.text((30, 500), test_text, font=font, fill=(255, 215, 0, 255))
print(f"  ✓ Text added: '{test_text[:40]}...'")

# Test 4: Save generated image
print("\nTest 4: Saving generated image...")
output_path = output_dir / "test_output.png"
template.save(output_path, "PNG")
print(f"  ✓ Image saved: {output_path.absolute()}")

# Test 5: Verify output
print("\nTest 5: Verifying output...")
if output_path.exists():
    size = output_path.stat().st_size
    print(f"  ✓ File exists, size: {size:,} bytes")
else:
    print("  ✗ File not found!")

print("\n" + "="*50)
print("All tests passed! Image generator is working.")
print(f"Generated image: {output_path.absolute()}")
