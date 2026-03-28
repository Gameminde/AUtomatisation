"""
Root-level compatibility shim — the canonical implementation lives in database/database.py.
Import this module normally; all symbols are re-exported transparently.
"""
from database.database import *  # noqa: F401, F403
from database.database import (  # noqa: F401 – explicit re-export for static analysis
    SQLiteDB,
    SupabaseWrapper,
    get_db,
    get_db_mode,
    get_database_client,
    DB_FILE,
    DB_MODE,
)
SupabaseDB = SupabaseWrapper  # noqa: F401
