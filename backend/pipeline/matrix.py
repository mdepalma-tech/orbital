"""Step 3 — Build the design matrix X and target vector y."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def get_model_config(model_mode: Optional[str]) -> Dict[str, Any]:
    """
    Deterministic model config from model_mode. No randomness, no tuning.
    """
    if model_mode == "causal_full":
        return {"use_adstock": True, "adstock_alpha": 0.5, "use_log": True}
    if model_mode == "causal_cautious":
        return {"use_adstock": True, "adstock_alpha": 0.4, "use_log": True}
    # diagnostic_stabilized or None
    return {"use_adstock": False, "adstock_alpha": None, "use_log": False}


def geometric_adstock(series: pd.Series, alpha: float) -> pd.Series:
    """
    Forward recursion: A_t = Spend_t + alpha * A_{t-1}, with A_{-1} = 0.
    Preserves index.
    """
    vals = series.values.astype(float)
    if len(vals) == 0:
        return pd.Series(dtype=float, index=series.index)
    out = np.empty(len(vals), dtype=float)
    out[0] = vals[0]
    for i in range(1, len(vals)):
        out[i] = vals[i] + alpha * out[i - 1]
    return pd.Series(out, index=series.index)


def build_design_matrix(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Constructs from weekly-aggregated data:
      y = revenue
      X = intercept + centered trend + event dummies + spend columns

    Spend transformations (adstock, log) are applied conditionally per model_mode.
    Event dummy columns (event_*) are expected to already exist in df_weekly,
    applied at daily granularity and propagated through weekly aggregation.
    """
    config = get_model_config(model_mode)
    X = pd.DataFrame(index=df_weekly.index)

    # Intercept
    X["const"] = 1.0

    # Centered trend
    trend = df_weekly["week_index"].astype(float)
    X["trend"] = trend - trend.mean()

    # Event columns (pre-baked into df_weekly by apply_event_dummies + aggregation)
    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    for col in event_cols:
        X[col] = df_weekly[col].astype(float)

    # Spend columns: raw -> adstock (if enabled) -> log (if enabled)
    for col in spend_cols:
        raw = df_weekly[col].astype(float)
        if config["use_adstock"] and config["adstock_alpha"] is not None:
            raw = geometric_adstock(raw, config["adstock_alpha"])
        if config["use_log"]:
            raw = np.log1p(np.maximum(raw, 0.0))
        X[col] = raw

    y = df_weekly["revenue"].astype(float)
    y.index = X.index

    # Final sanity: no NaN
    assert X.isna().sum().sum() == 0, "Design matrix contains NaN"
    assert y.isna().sum() == 0, "Target vector contains NaN"

    return X, y
