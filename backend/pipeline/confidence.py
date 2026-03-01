"""Step 12 — Rule-based confidence scoring."""

from __future__ import annotations

from pipeline.modeling import ModelResult


def compute_confidence(result: ModelResult, n_obs: int) -> str:
    """
    Returns 'high', 'medium', or 'low' based on deterministic rules.
    """
    level = "high"

    # Downgrade to medium
    if result.r2 < 0.3:
        level = "medium"
    if result.vif_values and max(result.vif_values.values()) > 10:
        level = "medium"
    if 60 <= n_obs <= 90:
        level = "medium"

    # Downgrade to low
    if result.r2 < 0.15:
        level = "low"
    if n_obs < 90 and result.r2 < 0.3:
        level = "low"

    # Check spend variation via VIF as proxy for low variation
    if result.vif_values:
        min_vif = min(result.vif_values.values())
        if min_vif < 1.01:
            level = "low"

    return level
