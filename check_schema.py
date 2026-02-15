"""Check database schema completeness."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config

client = config.get_supabase_client()

print("=" * 60)
print("📐 VÉRIFICATION DU SCHÉMA - CONTENT FACTORY")
print("=" * 60)

# Expected schema for each table
EXPECTED_SCHEMA = {
    'raw_articles': [
        'id', 'url', 'title', 'content', 'source', 'scraped_at', 
        'status', 'score', 'image_url', 'published_date'
    ],
    'processed_content': [
        'id', 'article_id', 'post_type', 'generated_text', 'script_for_reel',
        'hook', 'call_to_action', 'hashtags', 'target_audience', 
        'generated_at', 'image_path', 'arabic_text', 'status'
    ],
    'scheduled_posts': [
        'id', 'content_id', 'scheduled_time', 'status', 'created_at'
    ],
    'published_posts': [
        'id', 'content_id', 'facebook_post_id', 'published_at', 
        'engagement_synced_at'
    ],
    'performance_metrics': [
        'id', 'content_id', 'likes', 'comments', 'shares', 'reach',
        'impressions', 'cpm', 'synced_at'
    ]
}

for table, expected_columns in EXPECTED_SCHEMA.items():
    print(f"\n📋 Table: {table}")
    print("-" * 40)
    
    try:
        # Get one row to check columns
        result = client.table(table).select('*').limit(1).execute()
        
        if result.data:
            actual_columns = set(result.data[0].keys())
            expected_set = set(expected_columns)
            
            # Check missing columns
            missing = expected_set - actual_columns
            extra = actual_columns - expected_set
            
            if missing:
                print(f"  ❌ Colonnes MANQUANTES: {missing}")
            else:
                print(f"  ✅ Toutes les colonnes attendues présentes")
            
            if extra:
                print(f"  ℹ️  Colonnes supplémentaires: {extra}")
        else:
            print(f"  ⚠️  Table vide - impossible de vérifier le schéma")
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}")

print("\n" + "=" * 60)
print("✅ VÉRIFICATION TERMINÉE")
print("=" * 60)
