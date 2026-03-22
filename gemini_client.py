"""
Root-level compatibility shim — the canonical implementation lives in engine/gemini_client.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.gemini_client import *  # noqa: F401, F403
