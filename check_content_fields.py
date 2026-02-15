"""Check all content fields."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config

client = config.get_supabase_client()

# Get first scheduled post
scheduled = client.table('scheduled_posts').select('id, content_id').eq('status', 'scheduled').limit(1).execute()

if scheduled.data:
    content_id = scheduled.data[0]['content_id']
    print(f"Scheduled post: {scheduled.data[0]['id'][:8]}")
    print(f"Content ID: {content_id}")
    
    content = client.table('processed_content').select('*').eq('id', content_id).single().execute()
    
    if content.data:
        print(f"\n=== Content Fields ===\n")
        for key, value in content.data.items():
            if value:
                display = str(value)[:100] + "..." if len(str(value)) > 100 else value
                print(f"{key:20} | {display}")
else:
    print("No scheduled posts found")
