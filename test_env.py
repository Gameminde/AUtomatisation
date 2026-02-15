#!/usr/bin/env python3
"""Test if FB_APP_ID and FB_APP_SECRET are loaded from .env"""

import os
from dotenv import load_dotenv

print("=" * 60)
print("Test Environment Variables Loading")
print("=" * 60)

# Load .env
load_dotenv()

# Check FB variables
fb_app_id = os.getenv("FB_APP_ID", "")
fb_app_secret = os.getenv("FB_APP_SECRET", "")

print(f"\nFB_APP_ID: '{fb_app_id}'")
print(f"FB_APP_ID length: {len(fb_app_id)}")
print(f"FB_APP_ID empty: {not fb_app_id}")

print(f"\nFB_APP_SECRET: '{fb_app_secret}'")
print(f"FB_APP_SECRET length: {len(fb_app_secret)}")
print(f"FB_APP_SECRET empty: {not fb_app_secret}")

print(f"\nOAuth configured: {bool(fb_app_id and fb_app_secret)}")

# Show all env vars starting with FB_
print("\n" + "=" * 60)
print("All FB_ environment variables:")
print("=" * 60)
for key, value in os.environ.items():
    if key.startswith("FB_"):
        print(f"{key} = {value[:20]}..." if len(value) > 20 else f"{key} = {value}")
