"""Debug content details."""
import config

client = config.get_supabase_client()

# Check published content
result = client.table('published_posts').select('content_id, facebook_post_id').limit(5).execute()
print("=== Published Posts ===")
for row in result.data:
    content_id = row.get('content_id')
    fb_id = row.get('facebook_post_id')
    print(f"Content: {content_id[:8]}... -> FB: {fb_id}")
    
    # Get content details
    content = client.table('processed_content').select('*').eq('id', content_id).single().execute()
    if content.data:
        print(f"  - Hook: {content.data.get('hook', 'N/A')[:60]}...")
        print(f"  - Image path: {content.data.get('image_path', 'NONE')}")
        print(f"  - Arabic text: {content.data.get('arabic_text', 'NONE')}")
        print(f"  - Post type: {content.data.get('post_type')}")
        print()
