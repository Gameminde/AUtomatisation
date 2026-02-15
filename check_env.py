
import os
from dotenv import load_dotenv

print("Loading .env file...")
load_success = load_dotenv()
print(f"load_dotenv() returned: {load_success}")

fb_app_id = os.getenv("FB_APP_ID")
fb_app_secret = os.getenv("FB_APP_SECRET")

print(f"FB_APP_ID: '{fb_app_id}'")
print(f"FB_APP_SECRET: '{fb_app_secret}'")

if not fb_app_id or not fb_app_secret:
    print("❌ ERROR: Facebook credentials not found in environment variables.")
else:
    print("✅ SUCCESS: Facebook credentials found.")
