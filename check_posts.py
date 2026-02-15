"""Check scheduled posts status."""
import config

client = config.get_supabase_client()

# Count scheduled posts by type
result = client.table('scheduled_posts').select('id, content_id, status, scheduled_time').eq('status', 'scheduled').limit(20).execute()
print(f"Posts scheduled: {len(result.data)}")

text_count = 0
reel_count = 0

for row in result.data:
    content = client.table('processed_content').select('post_type, hook').eq('id', row['content_id']).single().execute()
    if content.data:
        post_type = content.data['post_type']
        hook = content.data.get('hook', '')[:50]
        if post_type == 'text':
            text_count += 1
        else:
            reel_count += 1
        print(f"  - {row['content_id'][:8]}: {post_type:4} | {hook}...")

print(f"\nSummary: {text_count} text posts, {reel_count} reels")
