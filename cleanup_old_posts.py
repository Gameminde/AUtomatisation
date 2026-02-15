"""Clean up old posts without images and reschedule with new content."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
import os

client = config.get_supabase_client()

print("=== Cleaning up old posts without images ===\n")

# Get all scheduled posts
scheduled = client.table('scheduled_posts').select('id, content_id').eq('status', 'scheduled').execute()

deleted_count = 0
kept_count = 0

for row in scheduled.data:
    content = client.table('processed_content').select('id, image_path, arabic_text').eq('id', row['content_id']).single().execute()
    if content.data:
        image_path = content.data.get('image_path')
        has_image = image_path and os.path.exists(image_path) if image_path else False
        has_arabic = bool(content.data.get('arabic_text'))
        
        if not has_image or not has_arabic:
            # Delete scheduled post without proper content
            client.table('scheduled_posts').delete().eq('id', row['id']).execute()
            print(f"❌ Deleted scheduled post: {row['id'][:8]} (no image/arabic)")
            deleted_count += 1
        else:
            kept_count += 1
            print(f"✅ Kept: {row['content_id'][:8]}")

print(f"\n=== Summary ===")
print(f"Deleted: {deleted_count} old posts")
print(f"Kept: {kept_count} posts with images")

# Now check remaining
remaining = client.table('scheduled_posts').select('id').eq('status', 'scheduled').execute()
print(f"Remaining scheduled: {len(remaining.data)}")
