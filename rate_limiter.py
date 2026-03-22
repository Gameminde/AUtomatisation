"""
Root-level compatibility shim — the canonical implementation lives in engine/rate_limiter.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.rate_limiter import *  # noqa: F401, F403
