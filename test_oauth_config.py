#!/usr/bin/env python3
"""Test is_configured() from facebook_oauth.py"""

from facebook_oauth import is_configured, FB_APP_ID, FB_APP_SECRET

print("=" * 60)
print("Testing facebook_oauth.is_configured()")
print("=" * 60)

print(f"\nFB_APP_ID from module: '{FB_APP_ID}'")
print(f"FB_APP_SECRET from module: '{FB_APP_SECRET}'")
print(f"\nis_configured() returns: {is_configured()}")
print(f"Expected: True (since both vars are set)")
