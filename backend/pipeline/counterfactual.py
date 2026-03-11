"""Step 10 — Counterfactual impact: zero-out each channel and measure lift."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
from pipeline.modeling import ModelResult


def _predict(result: ModelResult, X: pd.DataFrame) -> np.ndarray:
    if result.ridge_applied:
        X_no_const = X.drop(columns=["const"], errors="ignore")
        return result.model.predict(X_no_const)
    return result.model.predict(X).values


def _to_revenue(pred_log: np.ndarray, smearing: float) -> np.ndarray:
    """Inverse log-target transform with smearing: revenue = smearing * exp(pred) - 1."""
    return np.maximum(smearing * np.exp(pred_log) - 1.0, 0.0)


def compute_counterfactual(
    result: ModelResult,
    spend_cols: list[str],
    use_log_target: bool = False,
    smearing_factor: float = 1.0,
    df_weekly: pd.DataFrame | None = None,
) -> tuple[Dict[str, float], Dict[str, float]]:
    """
    For each spend channel, zero it out and compute:
      incremental = sum(actual_rev - counterfactual_rev)
      marginal_roi = incremental / total_spend

    total_spend uses raw (pre-adstock) spend from df_weekly when provided,
    so ROI is dollars per actual dollar spent. Otherwise falls back to
    result.X[col].sum() (adstocked spend), which understates ROI for high-alpha channels.

    When use_log_target is True, predictions are in log space (semi-elasticities).
    We inverse-transform to revenue space before summing so incremental and ROI
    are interpretable as dollars and dollars-per-dollar.
    """
    actual_pred = result.predicted
    if use_log_target:
        actual_rev = _to_revenue(actual_pred, smearing_factor)
        actual_total = float(np.sum(actual_rev))
    else:
        actual_total = float(np.sum(actual_pred))

    incremental: Dict[str, float] = {}
    marginal_roi: Dict[str, float] = {}

    for col in spend_cols:
        if col not in result.X.columns:
            incremental[col] = 0.0
            marginal_roi[col] = 0.0
            continue

        X_cf = result.X.copy()
        X_cf[col] = 0.0
        cf_pred = _predict(result, X_cf)

        if use_log_target:
            cf_rev = _to_revenue(cf_pred, smearing_factor)
            inc = float(actual_total - np.sum(cf_rev))
        else:
            inc = float(actual_total - np.sum(cf_pred))

        # Use raw spend for ROI denominator when available (avoids adstock inflation)
        if df_weekly is not None and col in df_weekly.columns:
            total_spend = float(df_weekly[col].astype(float).sum())
        else:
            total_spend = float(result.X[col].sum())

        incremental[col] = round(inc, 2)
        marginal_roi[col] = round(inc / total_spend, 4) if total_spend > 0 else 0.0

    return incremental, marginal_roi
