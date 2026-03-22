"""
Root-level compatibility shim — the canonical implementation lives in engine/instagram_publisher.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.instagram_publisher import *  # noqa: F401, F403
