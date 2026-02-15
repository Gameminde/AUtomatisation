"""Check scheduled posts with images."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
import os

client = config.get_supabase_client()

# Get scheduled posts
scheduled = client.table('scheduled_posts').select('id, content_id, status').eq('status', 'scheduled').limit(20).execute()

print("=== Scheduled Posts with Image Status ===")
text_with_image = 0
text_without_image = 0

for row in scheduled.data:
    content = client.table('processed_content').select('id, post_type, hook, image_path, arabic_text').eq('id', row['content_id']).single().execute()
    if content.data:
        c = content.data
        post_type = c.get('post_type')
        image_path = c.get('image_path')
        has_image = image_path and os.path.exists(image_path) if image_path else False
        arabic = c.get('arabic_text', '')[:30] if c.get('arabic_text') else 'NO ARABIC'
        hook = c.get('hook', '')[:40]
        
        if post_type == 'text':
            if has_image:
                text_with_image += 1
                status = "IMG"
            else:
                text_without_image += 1
                status = "NO-IMG"
            print(f"[{status}] {c['id'][:8]} | {post_type:4} | Arabic: {arabic}")

print(f"\nText posts: {text_with_image} with images, {text_without_image} without images")
