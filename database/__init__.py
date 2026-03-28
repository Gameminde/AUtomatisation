"""
database package — The canonical database implementation lives in database/database.py.

All existing callsites continue to work unchanged:
    from database import get_db, SQLiteDB
"""
import sys
import os as _os

# Ensure project root is on sys.path so database.database can import `config`
_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database.database import (  # noqa: E402, F401
    SQLiteDB,
    SupabaseWrapper,
    get_db,
    get_db_mode,
    get_database_client,
    DB_FILE,
    DB_MODE,
)

# Alias for code that imports `SupabaseDB`
SupabaseDB = SupabaseWrapper  # noqa: F401

__all__ = [
    "SQLiteDB",
    "SupabaseWrapper",
    "SupabaseDB",
    "get_db",
    "get_db_mode",
    "get_database_client",
    "DB_FILE",
    "DB_MODE",
]
