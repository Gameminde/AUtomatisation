import sqlite3
import re
import os

DB_PATH = 'content_factory.db'
APP_PATH = 'dashboard_app.py'

def get_db_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    schema = {}
    for t in tables:
        table_name = t[0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        schema[table_name] = columns
    
    conn.close()
    return schema

def scan_app_for_columns():
    with open(APP_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex to find .select('col1, col2') or .select('*')
    # This is a heuristic, not a full AST parser, but good enough for common calls
    selects = re.findall(r"\.select\(['\"](.*?)['\"]", content)
    
    # Also look for direct usage in comments or other strings if needed
    return selects

def audit():
    print("=== SYSTEM AUDIT ===")
    
    if not os.path.exists(DB_PATH):
        print(f"CRITICAL: Database file {DB_PATH} not found!")
        return

    schema = get_db_schema()
    print(f"Found {len(schema)} tables in DB.")
    
    # Check for known critical columns based on recent errors
    critical_checks = {
        'processed_content': ['status', 'rejected_reason', 'content_hash'],
        'scheduled_posts': ['status'],
        'published_posts': ['status'],
        'managed_pages': ['status', 'content_hash'] # Checking if content_hash is erroneously expected here
    }
    
    print("\n--- Critical Column Check ---")
    for table, required_cols in critical_checks.items():
        if table not in schema:
            print(f"❌ Missing Table: {table}")
            continue
            
        existing = schema[table]
        for col in required_cols:
            if col in existing:
                print(f"✅ {table}.{col} exists")
            else:
                print(f"❌ {table}.{col} MISSING")

    # Analyze Code for usage
    print("\n--- Code Usage Analysis ---")
    selects = scan_app_for_columns()
    print("Columns requested in .select() calls:")
    for s in selects:
        print(f"  - {s}")

if __name__ == "__main__":
    audit()
