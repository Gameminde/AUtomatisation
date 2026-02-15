"""Check actual database columns."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config

client = config.get_supabase_client()

tables = ['raw_articles', 'published_posts']

for table in tables:
    print(f"\n📋 {table} - Colonnes réelles:")
    print("-" * 50)
    result = client.table(table).select('*').limit(1).execute()
    if result.data:
        for key, value in result.data[0].items():
            val_type = type(value).__name__
            val_preview = str(value)[:40] if value else "NULL"
            print(f"  {key:25} | {val_type:8} | {val_preview}")
    else:
        print("  (table vide)")
