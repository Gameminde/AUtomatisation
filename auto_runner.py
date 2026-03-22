"""
auto_runner — Pipeline runner stub.
Full implementation arrives in Phase 4 (Engine multi-tenancy).
"""
import config

logger = config.get_logger("auto_runner")


def run_pipeline(user_id: str = None) -> dict:
    """Run the content automation pipeline for a user (stub)."""
    logger.info("auto_runner: run_pipeline called (stub, user_id=%s)", user_id)
    return {"success": False, "reason": "Pipeline not yet implemented"}
