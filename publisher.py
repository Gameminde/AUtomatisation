"""Compatibility alias for the canonical engine.publisher module."""

import sys

from engine import publisher as _impl

sys.modules[__name__] = _impl
