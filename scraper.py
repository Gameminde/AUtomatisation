"""
Root-level compatibility shim — the canonical implementation lives in engine/scraper.py.
Import this module normally; all symbols are re-exported transparently.
"""

import sys

from engine import scraper as _impl

sys.modules[__name__] = _impl
