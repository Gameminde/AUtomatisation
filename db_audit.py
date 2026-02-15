"""Audit the database schema and data integrity."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
from datetime import datetime, timezone

client = config.get_supabase_client()

print("=" * 60)
print("🔍 AUDIT BASE DE DONNÉES - CONTENT FACTORY")
print("=" * 60)

# 1. Check tables
tables = ['raw_articles', 'processed_content', 'scheduled_posts', 'published_posts', 'performance_metrics']

print("\n📊 TABLES ET COMPTEURS:")
print("-" * 40)

for table in tables:
    try:
        result = client.table(table).select('id', count='exact').execute()
        count = result.count if result.count else len(result.data)
        print(f"  ✅ {table:25} : {count} enregistrements")
    except Exception as e:
        print(f"  ❌ {table:25} : ERREUR - {e}")

# 2. Check pipeline flow
print("\n🔄 FLUX DU PIPELINE:")
print("-" * 40)

# Articles non traités
raw = client.table('raw_articles').select('id', count='exact').eq('status', 'pending').execute()
print(f"  📰 Articles en attente      : {raw.count or 0}")

# Contenu généré
processed = client.table('processed_content').select('id', count='exact').eq('status', 'pending').execute()
print(f"  🤖 Contenu généré (pending) : {processed.count or 0}")

# Posts programmés
scheduled = client.table('scheduled_posts').select('id', count='exact').eq('status', 'scheduled').execute()
print(f"  📅 Posts programmés         : {scheduled.count or 0}")

# Posts publiés
published = client.table('published_posts').select('id', count='exact').execute()
print(f"  ✅ Posts publiés            : {published.count or 0}")

# 3. Check content quality
print("\n📋 QUALITÉ DU CONTENU:")
print("-" * 40)

# Content with images
with_image = client.table('processed_content').select('id', count='exact').neq('image_path', None).execute()
print(f"  🖼️  Avec images             : {with_image.count or 0}")

# Content with Arabic
with_arabic = client.table('processed_content').select('id', count='exact').neq('arabic_text', None).execute()
print(f"  🇸🇦 Avec texte arabe        : {with_arabic.count or 0}")

# 4. Check scheduled posts timing
print("\n⏰ TIMING DES POSTS PROGRAMMÉS:")
print("-" * 40)

now = datetime.now(timezone.utc)
scheduled_data = client.table('scheduled_posts').select('scheduled_time').eq('status', 'scheduled').execute()

past_due = 0
future = 0
for row in scheduled_data.data:
    sched_str = row['scheduled_time'].replace('Z', '+00:00')
    if '+' not in sched_str and '-' not in sched_str[10:]:
        sched_str += '+00:00'
    sched_time = datetime.fromisoformat(sched_str)
    if sched_time.tzinfo is None:
        sched_time = sched_time.replace(tzinfo=timezone.utc)
    if sched_time <= now:
        past_due += 1
    else:
        future += 1

print(f"  ⚠️  En retard (à publier)   : {past_due}")
print(f"  ⏳ Futurs                   : {future}")

# 5. Check for orphan records
print("\n🔗 INTÉGRITÉ DES DONNÉES:")
print("-" * 40)

# Scheduled posts without content
scheduled_ids = client.table('scheduled_posts').select('content_id').eq('status', 'scheduled').execute()
orphan_scheduled = 0
for row in scheduled_ids.data:
    content = client.table('processed_content').select('id').eq('id', row['content_id']).execute()
    if not content.data:
        orphan_scheduled += 1

print(f"  {'✅' if orphan_scheduled == 0 else '❌'} Posts sans contenu        : {orphan_scheduled}")

# Processed content without article
processed_ids = client.table('processed_content').select('article_id').limit(50).execute()
orphan_content = 0
for row in processed_ids.data:
    if row['article_id']:
        article = client.table('raw_articles').select('id').eq('id', row['article_id']).execute()
        if not article.data:
            orphan_content += 1

print(f"  {'✅' if orphan_content == 0 else '❌'} Contenu sans article       : {orphan_content}")

# 6. Check for missing fields
print("\n⚠️  CHAMPS MANQUANTS:")
print("-" * 40)

# Content missing critical fields
missing_hook = client.table('processed_content').select('id', count='exact').is_('hook', 'null').execute()
missing_text = client.table('processed_content').select('id', count='exact').is_('generated_text', 'null').execute()

print(f"  Hook manquant              : {missing_hook.count or 0}")
print(f"  Texte généré manquant      : {missing_text.count or 0}")

print("\n" + "=" * 60)
print("✅ AUDIT TERMINÉ")
print("=" * 60)
