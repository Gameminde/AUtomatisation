"""
Root-level compatibility shim — the canonical implementation lives in engine/facebook_oauth.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.facebook_oauth import *  # noqa: F401, F403
