"""
Root-level compatibility shim — the canonical implementation lives in engine/ban_detector.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.ban_detector import *  # noqa: F401, F403
