import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

DB_PATH = 'content_factory.db'

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. processed_content: Add 'status' and 'rejected_reason'
        logger.info("Checking 'processed_content'...")
        cursor.execute("PRAGMA table_info(processed_content)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'status' not in cols:
            logger.info("Adding 'status' to processed_content...")
            cursor.execute("ALTER TABLE processed_content ADD COLUMN status TEXT DEFAULT 'drafted'")
        
        if 'rejected_reason' not in cols:
            logger.info("Adding 'rejected_reason' to processed_content...")
            cursor.execute("ALTER TABLE processed_content ADD COLUMN rejected_reason TEXT")

        # 2. published_posts: Add 'status' (just in case)
        logger.info("Checking 'published_posts'...")
        cursor.execute("PRAGMA table_info(published_posts)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'status' not in cols:
            logger.info("Adding 'status' to published_posts...")
            cursor.execute("ALTER TABLE published_posts ADD COLUMN status TEXT DEFAULT 'published'")

        # 3. managed_pages: Add 'status' if missing
        logger.info("Checking 'managed_pages'...")
        cursor.execute("PRAGMA table_info(managed_pages)")
        cols = [col[1] for col in cursor.fetchall()]

        if 'status' not in cols:
             logger.info("Adding 'status' to managed_pages...")
             cursor.execute("ALTER TABLE managed_pages ADD COLUMN status TEXT DEFAULT 'active'")

        conn.commit()
        logger.info("✅ Migration completed successfully.")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
