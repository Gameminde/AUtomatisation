"""Compatibility alias for the canonical engine.ai_provider module."""

import sys

from engine import ai_provider as _impl

sys.modules[__name__] = _impl
