"""Step 12 — Rule-based confidence scoring."""

from __future__ import annotations

from pipeline.modeling import ModelResult


def compute_confidence(
    result: ModelResult,
    n_obs: int,
    oos_metrics: dict | None = None,
    n_obs_effective: int | None = None,
) -> str:
    """
    Returns 'high', 'medium', or 'low' based on deterministic rules.
    OOS metrics can only downgrade, never upgrade.

    n_obs: original weekly count (e.g. from aggregation)
    n_obs_effective: rows after lag drops in check_autocorrelation; if provided,
        used for data volume checks (60-90 range, < 90 + low r2). Defaults to n_obs.
    """
    base_confidence = "high"
    n_for_volume = n_obs if n_obs_effective is None else n_obs_effective

    # Downgrade to medium
    if result.r2 < 0.3:
        base_confidence = "medium"
    if result.vif_values and max(result.vif_values.values()) > 10:
        base_confidence = "medium"
    if 60 <= n_for_volume <= 90:
        base_confidence = "medium"

    # Downgrade to low
    if result.r2 < 0.15:
        base_confidence = "low"
    if n_for_volume < 90 and result.r2 < 0.3:
        base_confidence = "low"

    # Check spend variation via VIF as proxy for low variation
    if result.vif_values:
        min_vif = min(result.vif_values.values())
        if min_vif < 1.01:
            base_confidence = "low"

    if oos_metrics:
        oos_n_obs = oos_metrics.get("oos_n_obs")
        oos_r2 = oos_metrics.get("oos_r2")

        # Ignore if insufficient OOS data
        if oos_n_obs is not None and oos_r2 is not None:

            # Do nothing if fewer than 8 OOS observations
            if oos_n_obs >= 8:

                # Severe degradation if strongly negative
                if oos_n_obs >= 16 and oos_r2 < -0.5:
                    return "low"

                # Moderate degradation
                if oos_n_obs >= 16 and oos_r2 < 0.0:
                    if base_confidence == "high":
                        return "medium"
                    if base_confidence == "medium":
                        return "low"

                # Mild degradation for smaller OOS window
                if 8 <= oos_n_obs < 16 and oos_r2 < -0.5:
                    if base_confidence == "high":
                        return "medium"
                    if base_confidence == "medium":
                        return "low"

    return base_confidence
