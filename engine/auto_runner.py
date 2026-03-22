"""
auto_runner — Public API for the multi-tenant background pipeline.

This module is the entry-point that dashboard routes and wsgi/dashboard_app
call.  The heavy implementation lives in tasks/runner.py (APScheduler +
ThreadPoolExecutor + distributed lock).  This module re-exports the key
functions for backward-compatibility and provides a simple facade.
"""

from __future__ import annotations

from typing import Dict, Optional

import config

logger = config.get_logger("auto_runner")


def run_pipeline(user_id: Optional[str] = None) -> Dict:
    """
    Run the pipeline for a single user or all active users.

    Parameters
    ----------
    user_id : str | None
        When provided, run only for that user.
        When None, run for all active users.

    Returns
    -------
    dict
        Pipeline result(s).
    """
    from tasks.runner import run_all_users, _run_pipeline_for_user
    from user_config import UserConfig

    if user_id:
        return _run_pipeline_for_user(UserConfig.from_db(user_id))
    return run_all_users()


def run_all_users() -> Dict:
    """Delegate to tasks.runner.run_all_users (APScheduler implementation)."""
    from tasks.runner import run_all_users as _impl
    return _impl()
