
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

# Database setup
DB_PATH = Path("content_factory.db")
TOKEN_FILE = Path("facebook_tokens.json")

def migrate_db():
    print(f"Checking database at {DB_PATH.absolute()}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create managed_pages table
    print("Creating 'managed_pages' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS managed_pages (
            page_id TEXT PRIMARY KEY,
            page_name TEXT NOT NULL,
            access_token TEXT NOT NULL,
            user_id TEXT,
            posts_per_day INTEGER DEFAULT 2,
            language TEXT DEFAULT 'AR',
            status TEXT DEFAULT 'active',
            last_synced_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    print("Table 'managed_pages' created/verified.")
    
    # Sync tokens from json
    if TOKEN_FILE.exists():
        print(f"Found {TOKEN_FILE}, syncing tokens...")
        try:
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
                
            # We need to decrypt tokens if they are encrypted in the file
            # But for this migration, let's assume valid data or use the oauth module to load if needed
            # Actually, let's try to just insert what we have if it matches the structure
            # Or better, let's use the existing decrypt logic if possible, but let's keep it simple for now.
            # If the dashboard uses the same encryption key, we might need to handle that.
            
            # Use the facebook_oauth module to load cleanly if possible, 
            # but to avoid dependency issues in this standalone script, let's just look at the JSON structure.
            
            # Structure usually: { "page_id": "...", "page_name": "...", "access_token": "...", ... }
            # Wait, looking at facebook_oauth.py before (which I saw in previous turn), it handles encryption.
            
            # Let's import the actual logic to be safe
            import sys
            sys.path.append(os.getcwd())
            try:
                from facebook_oauth import load_tokens
                tokens = load_tokens()
                
                if tokens and 'page_id' in tokens and 'page_token' in tokens:
                     print(f"Syncing page: {tokens.get('page_name', 'Unknown')}")
                     
                     cursor.execute("""
                        INSERT OR REPLACE INTO managed_pages 
                        (page_id, page_name, access_token, status, last_synced_at)
                        VALUES (?, ?, ?, 'active', datetime('now'))
                     """, (
                         tokens['page_id'], 
                         tokens.get('page_name', 'Linked Page'), 
                         tokens['page_token']
                     ))
                     conn.commit()
                     print("Successfully synced token to DB.")
                else:
                    print("No valid page tokens found in JSON.")
                    
            except Exception as e:
                print(f"Error loading/syncing tokens via module: {e}")
                # Fallback: Check if file exists and print content (debug)
                # print(data)

        except Exception as e:
            print(f"Error reading token file: {e}")
    else:
        print("No facebook_tokens.json found. Skipping sync.")
        
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
