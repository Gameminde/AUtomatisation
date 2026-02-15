import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v3")

DB_PATH = 'content_factory.db'

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check processed_content for content_hash
        logger.info("Checking 'processed_content' for 'content_hash'...")
        cursor.execute("PRAGMA table_info(processed_content)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'content_hash' not in cols:
            logger.info("Adding 'content_hash' to processed_content...")
            cursor.execute("ALTER TABLE processed_content ADD COLUMN content_hash TEXT")
            
            # Add index
            logger.info("Adding index idx_unique_content_hash...")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_content_hash ON processed_content(content_hash) WHERE content_hash IS NOT NULL")
        else:
             logger.info("✅ 'content_hash' already exists.")

        conn.commit()
        logger.info("✅ Migration V3 completed successfully.")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
