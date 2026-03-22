"""
Root-level compatibility shim — the canonical implementation lives in engine/scheduler.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.scheduler import *  # noqa: F401, F403
