"""
Test Publication Complète - Article RÉEL + Image sur Facebook
Publie le dernier contenu généré depuis Supabase
"""

import os
from dotenv import load_dotenv

load_dotenv()

from publisher import publish_photo_post
from pathlib import Path
import config

# Récupérer le dernier contenu RÉEL depuis Supabase
print("📥 Récupération du dernier contenu généré...")

client = config.get_supabase_client()
result = (
    client.table("processed_content")
    .select("hook, generated_text, hashtags, call_to_action, image_path, arabic_text")
    .order("id", desc=True)
    .limit(1)
    .execute()
)

if not result.data:
    print("❌ Aucun contenu trouvé dans Supabase !")
    exit(1)

content = result.data[0]

# Construire le message
hook = content.get("hook", "")
body = content.get("generated_text", "")
cta = content.get("call_to_action", "")
hashtags = " ".join(content.get("hashtags", [])) if content.get("hashtags") else ""
image_path = content.get("image_path", "")

message = f"{hook}\n\n{body}\n\n{cta}\n\n{hashtags}"

print(f"\n📷 Image: {image_path}")
print(f"\n📝 Contenu RÉEL à publier:")
print("-" * 50)
print(message[:500] + "..." if len(message) > 500 else message)
print("-" * 50)

if not image_path or not os.path.exists(image_path):
    print(f"❌ Image introuvable: {image_path}")
    exit(1)

print("\n🚀 Publication en cours...")

try:
    post_id = publish_photo_post(message, image_path)
    print(f"\n✅ SUCCÈS ! Post ID: {post_id}")
    print(f"\n🔗 Voir le post: https://facebook.com/{post_id}")
except Exception as e:
    print(f"\n❌ Erreur: {e}")
