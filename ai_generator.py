"""Compatibility alias for the canonical engine.ai_generator module."""

import sys

from engine import ai_generator as _impl

sys.modules[__name__] = _impl
