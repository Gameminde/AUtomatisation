"""
Root-level compatibility shim — the canonical implementation lives in engine/ai_generator.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.ai_generator import *  # noqa: F401, F403
