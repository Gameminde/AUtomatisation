"""
Root-level compatibility shim — the canonical implementation lives in engine/scraper.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.scraper import *  # noqa: F401, F403
