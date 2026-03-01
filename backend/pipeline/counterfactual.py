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


def compute_counterfactual(
    result: ModelResult, spend_cols: list[str]
) -> tuple[Dict[str, float], Dict[str, float]]:
    """
    For each spend channel, zero it out and compute:
      incremental = sum(actual_pred - counterfactual_pred)
      marginal_roi = incremental / total_spend
    """
    actual_pred = result.predicted
    actual_total = float(np.sum(actual_pred))

    incremental: Dict[str, float] = {}
    marginal_roi: Dict[str, float] = {}

    for col in spend_cols:
        if col not in result.X.columns:
            continue

        X_cf = result.X.copy()
        X_cf[col] = 0.0
        cf_pred = _predict(result, X_cf)

        inc = float(actual_total - np.sum(cf_pred))
        total_spend = float(result.X[col].sum())

        incremental[col] = round(inc, 2)
        marginal_roi[col] = round(inc / total_spend, 4) if total_spend > 0 else 0.0

    return incremental, marginal_roi
