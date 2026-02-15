
"""
VERIFY GENERATION SCRIPT
------------------------
This script triggers the Unified Content Creator in 'draft' mode.
It generates content + visual concepts but DOES NOT publish to Facebook.
It saves to the database so you can see it in the Studio.
"""

import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv()

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from unified_content_creator import create_and_publish
import config

def run_verification():
    print("⚡ VERIFICATION: Starting Content Generation...")
    
    # Force approval mode to ensure it goes to 'waiting_approval'
    config.APPROVAL_MODE = True
    print(f"📋 Approval Mode: {config.APPROVAL_MODE}")

    # Create content (Publish=False)
    result = create_and_publish(
        publish=False,
        save_to_db=True,
        check_duplicates=False, # Skip for test
        style="emotional",
        niche="tech"
    )

    if result["success"]:
        print(f"\n✅ SUCCESS! Content Generated.")
        print(f"🆔 Content ID: {result['content_id']}")
        print(f"📰 Topic: {result['topic']['title']}")
        print(f"🖼️ Image: {result['image_path']}")
        print("\n👉 Go to the Studio (http://localhost:5000/studio) to approve/reject.")
    else:
        print(f"\n❌ FAILED: {result['error']}")

if __name__ == "__main__":
    run_verification()
