"""Compatibility alias for the canonical engine.scheduler module."""

import sys

from engine import scheduler as _impl

sys.modules[__name__] = _impl
