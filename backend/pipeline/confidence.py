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
    # Start at High (3), downgrade progressively based on failures
    confidence_level = 3
    n_for_volume = n_obs if n_obs_effective is None else n_obs_effective

    # --- 1. Goodness of Fit (Adjusted R-squared in dollar space) ---
    # Use dollar_adj_r2 so log-target models are evaluated fairly.
    adj_r2 = result.dollar_adj_r2 if result.dollar_adj_r2 > 0 else result.adj_r2
    if adj_r2 < 0.5:
        confidence_level = min(confidence_level, 1)
    elif adj_r2 < 0.7:
        confidence_level = min(confidence_level, 2)

    # --- 2. Data Volume ---
    # Use effective row count (post lag-drops) so e.g. 53 weeks − 2 lags = 51 rows
    # correctly triggers the < 52 low-confidence rule.
    if n_for_volume < 52:
        confidence_level = min(confidence_level, 1)
    elif n_for_volume < 104:
        confidence_level = min(confidence_level, 2)

    # --- 3. Collinearity (VIF) ---
    if result.vif_values:
        max_vif = max(result.vif_values.values())
        if max_vif > 20: 
            confidence_level = min(confidence_level, 1) # Severe collinearity
        elif max_vif > 10:
            confidence_level = min(confidence_level, 2) # Moderate collinearity

    # --- 4. Residual Diagnostics (The "Under the Hood" checks) ---
    # Durbin-Watson checks for autocorrelation. ~2.0 is ideal. 
    # < 1.0 or > 3.0 means the model is likely missing a major seasonal trend.
    if result.dw_stat:
        if result.dw_stat < 1.0 or result.dw_stat > 3.0:
            confidence_level = min(confidence_level, 1)
        elif result.dw_stat < 1.5 or result.dw_stat > 2.5:
            confidence_level = min(confidence_level, 2)

    # Ljung-Box / Breusch-Pagan
    # If p < 0.01, the residuals still have strong patterns or heteroskedasticity 
    # even after the pipeline tried to apply lags/HAC.
    if result.ljung_box_p < 0.01 or result.breusch_pagan_p < 0.01:
        confidence_level = min(confidence_level, 2)

    # --- 5. Negative Spend Coefficients ---
    if result.negative_spend_cols:
        confidence_level = min(confidence_level, 1)

    # --- 6. Out of Sample (OOS) Reality Check ---
    if oos_metrics:
        oos_n_obs = oos_metrics.get("oos_n_obs")
        oos_r2 = oos_metrics.get("oos_r2")

        if oos_n_obs and oos_r2 and oos_n_obs >= 8:
            # If OOS R2 is negative, the model predicts worse than a flat average line.
            if oos_r2 < 0.0:
                confidence_level = min(confidence_level, 1)
            elif oos_r2 < 0.4:
                confidence_level = min(confidence_level, 2)

    # --- Final Translation ---
    if confidence_level == 3:
        return "high"
    if confidence_level == 2:
        return "medium"
    return "low"
