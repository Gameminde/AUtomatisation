"""Check which contents have images."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
import os

client = config.get_supabase_client()

# Check all processed content
result = client.table('processed_content').select('id, hook, image_path, arabic_text, generated_at').order('generated_at', desc=True).limit(20).execute()

print("=== Processed Content with Images ===")
with_image = 0
without_image = 0

for row in result.data:
    image_path = row.get('image_path')
    has_image = image_path and os.path.exists(image_path) if image_path else False
    status = "✅" if has_image else "❌"
    hook = row.get('hook', 'N/A')[:50]
    arabic = row.get('arabic_text', '')[:30] if row.get('arabic_text') else 'NONE'
    
    if has_image:
        with_image += 1
    else:
        without_image += 1
    
    print(f"{status} {row['id'][:8]} | Image: {bool(image_path)} | Arabic: {arabic}")

print(f"\nSummary: {with_image} with images, {without_image} without images")
