"""Schedule one post for immediate publication."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
from datetime import datetime, timezone

client = config.get_supabase_client()

# Get first scheduled post with image
scheduled = client.table('scheduled_posts').select('id, content_id').eq('status', 'scheduled').limit(1).execute()

if scheduled.data:
    post = scheduled.data[0]
    # Update to now
    now = datetime.now(timezone.utc).isoformat()
    client.table('scheduled_posts').update({'scheduled_time': now}).eq('id', post['id']).execute()
    print(f"✅ Updated post {post['id'][:8]} to be due NOW: {now}")
    
    # Get content details
    content = client.table('processed_content').select('hook, arabic_text, image_path').eq('id', post['content_id']).single().execute()
    if content.data:
        print(f"   Hook: {content.data.get('hook', '')[:50]}...")
        print(f"   Arabic: {content.data.get('arabic_text', '')[:50]}...")
        print(f"   Image: {content.data.get('image_path', 'N/A')}")
else:
    print("No scheduled posts found")
