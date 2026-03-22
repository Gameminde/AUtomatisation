"""
Root-level compatibility shim — the canonical implementation lives in engine/randomization.py.
Import this module normally; all symbols are re-exported transparently.
"""
from engine.randomization import *  # noqa: F401, F403
