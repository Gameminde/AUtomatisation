import os
import sys
from dotenv import load_dotenv

print(f"CWD: {os.getcwd()}")
print(f"Python: {sys.executable}")

# 1. Load .env
load_dotenv()
print("Loaded .env")

# 2. Check variables directly
app_id = os.getenv("FB_APP_ID")
print(f"Direct Env Check: FB_APP_ID='{app_id}'")

# 3. Import module and check
try:
    import facebook_oauth
    print(f"Module FB_APP_ID: '{facebook_oauth.FB_APP_ID}'")
    print(f"is_configured(): {facebook_oauth.is_configured()}")
except ImportError as e:
    print(f"Import Error: {e}")
