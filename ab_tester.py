"""Compatibility alias for the canonical engine.ab_tester module."""

import sys

from engine import ab_tester as _impl

sys.modules[__name__] = _impl
