"""Test Pexels API integration with full image generation."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 50)
print("TEST: Pexels API + Full Image Generation")
print("=" * 50)

# Test 1: Check API key
print("\n1. Checking Pexels API key...")
api_key = os.getenv("PEXELS_API_KEY", "")
if api_key:
    print(f"   ✓ API key found: {api_key[:10]}...")
else:
    print("   ✗ No API key found!")
    exit(1)

# Test 2: Search for image
print("\n2. Searching for image on Pexels...")
import requests

url = "https://api.pexels.com/v1/search"
headers = {"Authorization": api_key}
params = {"query": "artificial intelligence", "per_page": 1, "orientation": "landscape"}

try:
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("photos"):
        photo = data["photos"][0]
        image_url = photo["src"]["medium"]
        print(f"   ✓ Found image: {photo['alt'][:50] if photo.get('alt') else 'No description'}")
        print(f"   ✓ URL: {image_url[:60]}...")
    else:
        print("   ✗ No photos found")
        image_url = None
except Exception as e:
    print(f"   ✗ API Error: {e}")
    image_url = None

# Test 3: Generate full image
print("\n3. Generating social media post...")
from image_generator import generate_social_post

try:
    result = generate_social_post(
        article_text="L'intelligence artificielle révolutionne les entreprises",
        image_query="artificial intelligence technology",
        output_filename="test_pexels_full.png",
    )
    print(f"   ✓ Generated: {result}")
except Exception as e:
    print(f"   ✗ Generation error: {e}")

# Test 4: Verify output
print("\n4. Verifying output...")
output_path = Path("generated_images/test_pexels_full.png")
if output_path.exists():
    size = output_path.stat().st_size
    print(f"   ✓ File exists: {size:,} bytes")
else:
    print("   ✗ Output file not found")

print("\n" + "=" * 50)
print("Test complete!")
print("=" * 50)
