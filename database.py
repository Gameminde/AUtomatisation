"""
Database Layer - Unified interface supporting SQLite (local) and Supabase (cloud).

Content Factory v2.0 Gumroad Edition:
- SQLite by default (zero config, works out of the box)
- Supabase optional (for users who want cloud sync)

Usage:
    from database import get_db
    
    db = get_db()  # Auto-selects SQLite or Supabase
    db.insert("raw_articles", {...})
    rows = db.select("raw_articles", status="pending")
"""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import config

logger = config.get_logger("database")

# Database file location
DB_FILE = Path(__file__).parent / "content_factory.db"

# Database mode: "sqlite" or "supabase"
DB_MODE = os.getenv("DB_MODE", "sqlite").lower()


class SQLiteDB:
    """
    SQLite database wrapper with Supabase-like API.
    
    Provides familiar insert/select/update/delete methods
    that match the Supabase client interface.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize SQLite connection."""
        self.db_path = db_path or str(DB_FILE)
        self._ensure_tables()
        logger.info(f"✅ SQLite database: {self.db_path}")
    
    @contextmanager
    def _get_conn(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # raw_articles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_articles (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    content TEXT,
                    published_date TEXT,
                    keywords TEXT,
                    virality_score INTEGER DEFAULT 0,
                    scraped_at TEXT DEFAULT (datetime('now')),
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            # processed_content (v2.1.1: State Machine + Anti Double-Publish)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_content (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    article_id TEXT,
                    post_type TEXT NOT NULL,
                    generated_text TEXT NOT NULL,
                    hashtags TEXT,
                    hook TEXT,
                    call_to_action TEXT,
                    target_audience TEXT DEFAULT 'AR',
                    image_path TEXT,
                    arabic_text TEXT,
                    generated_at TEXT DEFAULT (datetime('now')),
                    status TEXT DEFAULT 'drafted',
                    content_hash TEXT,
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    last_error_at TEXT,
                    fb_post_id TEXT,
                    publish_attempt_id TEXT,
                    next_retry_at TEXT,
                    rejected_reason TEXT,
                    FOREIGN KEY (article_id) REFERENCES raw_articles(id)
                )
            """)
            
            # scheduled_posts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    content_id TEXT,
                    scheduled_time TEXT NOT NULL,
                    timezone TEXT DEFAULT 'America/New_York',
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'scheduled',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (content_id) REFERENCES processed_content(id)
                )
            """)
            
            # published_posts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS published_posts (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    content_id TEXT,
                    facebook_post_id TEXT UNIQUE,
                    published_at TEXT DEFAULT (datetime('now')),
                    likes INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    reach INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    FOREIGN KEY (content_id) REFERENCES processed_content(id)
                )
            """)
            
            # managed_pages (Added for Content Factory v2.0 Dashboard)
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
            
            # v2.1: System Status (Observability)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON raw_articles(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_posts(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_time ON scheduled_posts(scheduled_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_status ON processed_content(status)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_content_hash ON processed_content(content_hash) WHERE content_hash IS NOT NULL")
            
            logger.debug("✅ Database tables ready")
    
    def table(self, name: str) -> "SQLiteTable":
        """Get a table interface (Supabase-compatible)."""
        return SQLiteTable(self, name)
    
    def execute(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute raw SQL and return results."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            return []


class SQLiteTable:
    """
    Table interface that mimics Supabase client API.
    
    Supports chained methods like:
        db.table("raw_articles").select("*").eq("status", "pending").execute()
    """
    
    def __init__(self, db: SQLiteDB, table_name: str):
        self.db = db
        self.table_name = table_name
        self._select_cols = "*"
        self._where = []
        self._order = None
        self._limit = None
        self._single = False
    
    def select(self, columns: str = "*", count: str = None) -> "SQLiteTable":
        """Select columns."""
        self._select_cols = columns
        return self
    
    def insert(self, data: Dict) -> "SQLiteTable":
        """Insert data."""
        self._insert_data = data
        return self
    
    def update(self, data: Dict) -> "SQLiteTable":
        """Update data."""
        self._update_data = data
        return self
    
    def delete(self) -> "SQLiteTable":
        """Delete rows."""
        self._delete = True
        return self
    
    def eq(self, column: str, value: Any) -> "SQLiteTable":
        """Where column equals value."""
        self._where.append((column, "=", value))
        return self
    
    def neq(self, column: str, value: Any) -> "SQLiteTable":
        """Where column not equals value."""
        self._where.append((column, "!=", value))
        return self
    
    def gt(self, column: str, value: Any) -> "SQLiteTable":
        """Where column greater than value."""
        self._where.append((column, ">", value))
        return self
    
    def gte(self, column: str, value: Any) -> "SQLiteTable":
        """Where column greater than or equal to value."""
        self._where.append((column, ">=", value))
        return self
    
    def lt(self, column: str, value: Any) -> "SQLiteTable":
        """Where column less than value."""
        self._where.append((column, "<", value))
        return self
    
    def lte(self, column: str, value: Any) -> "SQLiteTable":
        """Where column less than or equal to value."""
        self._where.append((column, "<=", value))
        return self
    
    def in_(self, column: str, values: List) -> "SQLiteTable":
        """Where column in list of values."""
        self._where.append((column, "IN", values))
        return self
    
    def order(self, column: str, desc: bool = False) -> "SQLiteTable":
        """Order by column."""
        self._order = (column, desc)
        return self
    
    def limit(self, count: int) -> "SQLiteTable":
        """Limit results."""
        self._limit = count
        return self
    
    def single(self) -> "SQLiteTable":
        """Expect single result."""
        self._single = True
        self._limit = 1
        return self
    
    def execute(self) -> "SQLiteResult":
        """Execute the query and return result."""
        with self.db._get_conn() as conn:
            cursor = conn.cursor()
            
            # Handle INSERT
            if hasattr(self, '_insert_data'):
                data = self._insert_data
                # Handle arrays (hashtags, keywords)
                for key, value in data.items():
                    if isinstance(value, list):
                        data[key] = json.dumps(value)
                
                # Generate ID if not provided
                if 'id' not in data:
                    import uuid
                    data['id'] = str(uuid.uuid4())
                
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(data.values()))
                
                # Return inserted row
                cursor.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", (data['id'],))
                rows = [self._row_to_dict(row) for row in cursor.fetchall()]
                return SQLiteResult(rows)
            
            # Handle UPDATE
            if hasattr(self, '_update_data'):
                data = self._update_data
                for key, value in data.items():
                    if isinstance(value, list):
                        data[key] = json.dumps(value)
                
                set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                where_clause, where_params = self._build_where()
                sql = f"UPDATE {self.table_name} SET {set_clause}"
                if where_clause:
                    sql += f" WHERE {where_clause}"
                
                cursor.execute(sql, tuple(data.values()) + where_params)
                
                # Return updated rows
                select_sql = f"SELECT * FROM {self.table_name}"
                if where_clause:
                    select_sql += f" WHERE {where_clause}"
                cursor.execute(select_sql, where_params)
                rows = [self._row_to_dict(row) for row in cursor.fetchall()]
                return SQLiteResult(rows)
            
            # Handle DELETE
            if hasattr(self, '_delete') and self._delete:
                where_clause, where_params = self._build_where()
                sql = f"DELETE FROM {self.table_name}"
                if where_clause:
                    sql += f" WHERE {where_clause}"
                cursor.execute(sql, where_params)
                return SQLiteResult([])
            
            # Handle SELECT
            sql = f"SELECT {self._select_cols} FROM {self.table_name}"
            where_clause, where_params = self._build_where()
            if where_clause:
                sql += f" WHERE {where_clause}"
            
            if self._order:
                col, desc = self._order
                sql += f" ORDER BY {col} {'DESC' if desc else 'ASC'}"
            
            if self._limit:
                sql += f" LIMIT {self._limit}"
            
            cursor.execute(sql, where_params)
            rows = [self._row_to_dict(row) for row in cursor.fetchall()]
            
            if self._single:
                return SQLiteResult(rows[0] if rows else None, single=True)
            return SQLiteResult(rows)
    
    def _build_where(self) -> tuple:
        """Build WHERE clause and parameters."""
        if not self._where:
            return "", ()
        
        clauses = []
        params = []
        
        for col, op, val in self._where:
            if op == "IN":
                placeholders = ', '.join(['?' for _ in val])
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(val)
            else:
                clauses.append(f"{col} {op} ?")
                params.append(val)
        
        return " AND ".join(clauses), tuple(params)
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert SQLite row to dict, parsing JSON fields."""
        d = dict(row)
        # Parse JSON arrays
        for key in ['hashtags', 'keywords']:
            if key in d and d[key]:
                try:
                    d[key] = json.loads(d[key])
                except:
                    pass
        return d


class SQLiteResult:
    """
    Result wrapper that mimics Supabase response.
    """
    
    def __init__(self, data: Any, single: bool = False):
        if single:
            self.data = data
        else:
            self.data = data if data else []
        self.count = len(self.data) if isinstance(self.data, list) else (1 if self.data else 0)


class SupabaseWrapper:
    """
    Wrapper around Supabase client to provide same interface as SQLiteDB.
    """
    
    def __init__(self):
        from supabase import create_client
        url = config.require_env("SUPABASE_URL")
        key = config.require_env("SUPABASE_KEY")
        self._client = create_client(url, key)
        logger.info("✅ Supabase database connected")
    
    def table(self, name: str):
        """Get table interface."""
        return self._client.table(name)


# Global database instance
_db_instance = None


def get_db():
    """
    Get database instance.
    
    Auto-selects based on configuration:
    - If SUPABASE_URL is set and DB_MODE != "sqlite": use Supabase
    - Otherwise: use SQLite (default)
    
    Returns:
        Database instance (SQLiteDB or SupabaseWrapper)
    """
    global _db_instance
    
    if _db_instance is not None:
        return _db_instance
    
    # Check if Supabase is configured and desired
    use_supabase = (
        DB_MODE == "supabase" and 
        config.SUPABASE_URL and 
        config.SUPABASE_KEY
    )
    
    if use_supabase:
        try:
            _db_instance = SupabaseWrapper()
            logger.info("📡 Using Supabase (cloud)")
        except Exception as e:
            logger.warning(f"Supabase failed, falling back to SQLite: {e}")
            _db_instance = SQLiteDB()
    else:
        _db_instance = SQLiteDB()
        logger.info("💾 Using SQLite (local)")
    
    return _db_instance


def get_supabase_client():
    """
    Backward compatibility function.
    Returns database instance that works like Supabase client.
    """
    return get_db()


# Convenience functions
def insert(table: str, data: Dict) -> Dict:
    """Insert data into table."""
    result = get_db().table(table).insert(data).execute()
    return result.data[0] if result.data else None


def select(table: str, **where) -> List[Dict]:
    """Select from table with optional where clauses."""
    query = get_db().table(table).select("*")
    for col, val in where.items():
        query = query.eq(col, val)
    return query.execute().data


def update(table: str, data: Dict, **where) -> List[Dict]:
    """Update table with where clauses."""
    query = get_db().table(table).update(data)
    for col, val in where.items():
        query = query.eq(col, val)
    return query.execute().data


if __name__ == "__main__":
    print("🗄️ Database Test\n")
    
    db = get_db()
    print(f"Mode: {'SQLite' if isinstance(db, SQLiteDB) else 'Supabase'}")
    print(f"Path: {DB_FILE if isinstance(db, SQLiteDB) else 'Cloud'}")
    
    # Test insert
    print("\n📝 Testing insert...")
    result = db.table("raw_articles").insert({
        "source_name": "test",
        "title": "Test Article",
        "url": f"https://test.com/{datetime.now().timestamp()}",
        "content": "Test content",
        "status": "pending"
    }).execute()
    print(f"Inserted: {result.data[0]['id'][:8] if result.data else 'Failed'}")
    
    # Test select
    print("\n📖 Testing select...")
    result = db.table("raw_articles").select("*").eq("status", "pending").limit(5).execute()
    print(f"Found: {len(result.data)} pending articles")
    
    # Test count
    result = db.table("raw_articles").select("*").execute()
    print(f"Total articles: {len(result.data)}")
    
    print("\n✅ Database tests passed!")
