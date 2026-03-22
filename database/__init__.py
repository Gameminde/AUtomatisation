"""
database package — Phase-1 structural home for the database layer.

Python packages take precedence over same-name modules, so this `__init__.py`
loads the implementation from `database.py` at the project root using
importlib (by absolute file path) to avoid circular-import issues.

All existing callsites continue to work unchanged:
    from database import get_db, SQLiteDB
"""

import importlib.util
import sys
from pathlib import Path

_db_path = Path(__file__).parent.parent / "database.py"
_spec = importlib.util.spec_from_file_location("_database_impl", _db_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_database_impl", _module)
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

SQLiteDB = _module.SQLiteDB
SupabaseWrapper = _module.SupabaseWrapper
get_db = _module.get_db
DB_FILE = _module.DB_FILE
DB_MODE = _module.DB_MODE

# Alias for code that imports `SupabaseDB`
SupabaseDB = SupabaseWrapper

__all__ = ["SQLiteDB", "SupabaseWrapper", "SupabaseDB", "get_db", "DB_FILE", "DB_MODE"]
