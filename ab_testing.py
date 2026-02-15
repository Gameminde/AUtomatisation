"""A/B Testing for AI prompt variants using Thompson Sampling.

Usage:
    Set AB_TESTING_ENABLED=true in .env to activate.
    Variants are stored in Supabase 'prompt_variants' table.
"""

from __future__ import annotations

import os
import random
from typing import Dict, List, Optional

import config

logger = config.get_logger("ab_testing")

AB_ENABLED = os.environ.get("AB_TESTING_ENABLED", "false").lower() == "true"


# ── Variant Management ────────────────────────────────────

def get_variants() -> List[Dict]:
    """Fetch all prompt variants from Supabase."""
    try:
        client = config.get_supabase_client()
        result = (
            client.table("prompt_variants")
            .select("id, name, template, wins, total_uses, created_at")
            .order("created_at")
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning("Could not fetch prompt variants: %s", e)
        return []


def add_variant(name: str, template: str) -> Optional[Dict]:
    """Insert a new prompt variant."""
    try:
        client = config.get_supabase_client()
        data = {"name": name, "template": template, "wins": 0, "total_uses": 0}
        result = client.table("prompt_variants").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to add variant: %s", e)
        return None


# ── Thompson Sampling ─────────────────────────────────────

def _thompson_score(wins: int, total: int) -> float:
    """Draw from Beta(wins+1, losses+1) distribution."""
    losses = total - wins
    return random.betavariate(wins + 1, losses + 1)


def pick_variant(variants: Optional[List[Dict]] = None) -> Optional[Dict]:
    """
    Select a prompt variant using Thompson Sampling.

    Returns the best variant dict or None if A/B testing is disabled
    or no variants exist.
    """
    if not AB_ENABLED:
        return None

    if variants is None:
        variants = get_variants()

    if not variants:
        logger.debug("No prompt variants available")
        return None

    # Score each variant with Thompson Sampling
    scored = []
    for v in variants:
        score = _thompson_score(v.get("wins", 0), v.get("total_uses", 0))
        scored.append((score, v))

    scored.sort(key=lambda x: x[0], reverse=True)
    winner = scored[0][1]

    # Increment total_uses
    try:
        client = config.get_supabase_client()
        client.table("prompt_variants").update({
            "total_uses": winner.get("total_uses", 0) + 1
        }).eq("id", winner["id"]).execute()
    except Exception as e:
        logger.warning("Could not update variant usage: %s", e)

    logger.info("A/B: selected variant '%s' (wins=%d, uses=%d)",
                winner["name"], winner.get("wins", 0), winner.get("total_uses", 0))
    return winner


def record_result(variant_id: str, engagement_rate: float, baseline: float = 3.0) -> None:
    """
    Record engagement result for a variant.

    If engagement_rate > baseline, count as a win.
    """
    try:
        client = config.get_supabase_client()
        # Fetch current stats
        result = (
            client.table("prompt_variants")
            .select("wins, total_uses")
            .eq("id", variant_id)
            .single()
            .execute()
        )
        if not result.data:
            return

        updates: Dict = {}
        if engagement_rate > baseline:
            updates["wins"] = result.data.get("wins", 0) + 1

        if updates:
            client.table("prompt_variants").update(updates).eq("id", variant_id).execute()
            logger.info("A/B: recorded result for variant %s (engagement=%.2f%%, baseline=%.2f%%)",
                        variant_id, engagement_rate, baseline)
    except Exception as e:
        logger.error("Failed to record A/B result: %s", e)


if __name__ == "__main__":
    print("A/B Testing Status:", "ENABLED" if AB_ENABLED else "DISABLED")
    variants = get_variants()
    print(f"Variants loaded: {len(variants)}")
    for v in variants:
        print(f"  - {v['name']}: {v['wins']}/{v['total_uses']} wins")
