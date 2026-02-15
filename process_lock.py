"""
Process Lock Module - Prevents multiple instances from running simultaneously.

v2.1.1: Thread Safety for Content Factory.

Features:
- File-based lock for single process
- DB-based lock for distributed systems
- Automatic stale lock cleanup
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows compatibility

import config

logger = config.get_logger("process_lock")

LOCK_FILE = Path(__file__).parent / "content_factory.lock"
STALE_LOCK_TIMEOUT_MINUTES = 30  # Consider lock stale after 30 minutes


class ProcessLock:
    """
    Dual-mode process lock (file + DB).
    
    Usage:
        with ProcessLock() as lock:
            if lock.acquired:
                # Do work
            else:
                print("Another instance is running")
    """
    
    def __init__(self):
        self.file_lock = None
        self.acquired = False
        self.lock_id = f"{os.getpid()}_{int(time.time())}"
    
    def acquire(self) -> bool:
        """Try to acquire the lock."""
        # Try file lock first (if available)
        if fcntl:
            try:
                self.file_lock = open(LOCK_FILE, 'w')
                fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.file_lock.write(f"{self.lock_id}\n{datetime.now().isoformat()}")
                self.file_lock.flush()
                logger.debug(f"🔒 File lock acquired: {self.lock_id}")
            except (IOError, OSError, BlockingIOError):
                # File lock failed, check if stale
                if self._is_stale_lock():
                    logger.warning("⚠️ Stale lock detected, forcing acquisition")
                    self._force_release()
                    return self.acquire()
                logger.warning("❌ File lock failed - another instance running")
                return False
        else:
            logger.debug("📝 fcntl not available (Windows), using DB lock only")
        
        # Also set DB flag (for distributed visibility)
        try:
            self._acquire_db_lock()
        except Exception as e:
            logger.warning(f"DB lock failed (non-fatal): {e}")
        
        self.acquired = True
        logger.info(f"🔒 Process lock acquired: {self.lock_id}")
        return True
    
    def release(self) -> None:
        """Release the lock."""
        if self.file_lock and fcntl:
            try:
                fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_UN)
                self.file_lock.close()
                LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass
        elif self.file_lock:
            # Windows: just close the file
            try:
                self.file_lock.close()
                LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass
        
        try:
            self._release_db_lock()
        except Exception as e:
            logger.warning(f"DB lock release failed: {e}")
        
        self.acquired = False
        logger.info(f"🔓 Process lock released: {self.lock_id}")
    
    def _acquire_db_lock(self) -> None:
        """Set running flag in system_status."""
        client = config.get_supabase_client()
        now = datetime.now().isoformat()
        
        # CAS: Only set if not already running
        # Check current state first
        result = client.table("system_status").select("value").eq("key", "running").execute()
        if result.data and result.data[0].get("value") == "true":
            # Check if stale
            since_result = client.table("system_status").select("value").eq("key", "running_since").execute()
            if since_result.data:
                running_since = since_result.data[0].get("value")
                if running_since:
                    since_dt = datetime.fromisoformat(running_since)
                    if datetime.now() - since_dt > timedelta(minutes=STALE_LOCK_TIMEOUT_MINUTES):
                        logger.warning("⚠️ DB lock is stale, overriding")
                    else:
                        raise RuntimeError("Another process is running")
        
        client.table("system_status").upsert({"key": "running", "value": "true", "updated_at": now}).execute()
        client.table("system_status").upsert({"key": "running_since", "value": now, "updated_at": now}).execute()
    
    def _release_db_lock(self) -> None:
        """Clear running flag in system_status."""
        client = config.get_supabase_client()
        now = datetime.now().isoformat()
        client.table("system_status").upsert({"key": "running", "value": "false", "updated_at": now}).execute()
        client.table("system_status").upsert({"key": "running_since", "value": None, "updated_at": now}).execute()
    
    def _is_stale_lock(self) -> bool:
        """Check if existing lock file is stale."""
        try:
            if not LOCK_FILE.exists():
                return False
            
            with open(LOCK_FILE, 'r') as f:
                content = f.read().strip().split('\n')
                if len(content) >= 2:
                    lock_time = datetime.fromisoformat(content[1])
                    if datetime.now() - lock_time > timedelta(minutes=STALE_LOCK_TIMEOUT_MINUTES):
                        return True
        except Exception:
            pass
        return False
    
    def _force_release(self) -> None:
        """Force release a stale lock."""
        try:
            LOCK_FILE.unlink(missing_ok=True)
            self._release_db_lock()
        except Exception:
            pass
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


@contextmanager
def process_lock():
    """Context manager for process lock."""
    lock = ProcessLock()
    try:
        lock.acquire()
        yield lock
    finally:
        lock.release()


def is_running() -> bool:
    """Check if another instance is running (without acquiring lock)."""
    try:
        client = config.get_supabase_client()
        result = client.table("system_status").select("value").eq("key", "running").execute()
        return result.data and result.data[0].get("value") == "true"
    except Exception:
        return LOCK_FILE.exists()


# Singleton lock for module-level use
_global_lock: Optional[ProcessLock] = None


def acquire_global_lock() -> bool:
    """Acquire the global process lock."""
    global _global_lock
    if _global_lock is None:
        _global_lock = ProcessLock()
    return _global_lock.acquire()


def release_global_lock() -> None:
    """Release the global process lock."""
    global _global_lock
    if _global_lock:
        _global_lock.release()
        _global_lock = None
