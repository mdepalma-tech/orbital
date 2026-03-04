"""Step 3 — Build the design matrix X and target vector y."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def get_model_config(model_mode: Optional[str]) -> Dict[str, Any]:
    """
    Deterministic model config from model_mode. No randomness, no tuning.
    """
    if model_mode == "causal_full":
        return {"use_adstock": True, "adstock_alpha": 0.5, "use_log": True, "use_log_target": True}
    if model_mode == "causal_cautious":
        return {"use_adstock": True, "adstock_alpha": 0.4, "use_log": True, "use_log_target": True}
    # diagnostic_stabilized or None
    return {"use_adstock": False, "adstock_alpha": None, "use_log": False, "use_log_target": False}


def geometric_adstock(
    series: pd.Series,
    alpha: float,
    init_value: float = 0.0,
) -> tuple[pd.Series, float]:
    """
    Forward recursion: A_t = Spend_t + alpha * A_{t-1}, with A_{-1} = init_value.
    Preserves index. Returns (transformed series, final carryover value).
    """
    vals = series.values.astype(float)
    if len(vals) == 0:
        return pd.Series(dtype=float, index=series.index), init_value
    out = np.empty(len(vals), dtype=float)
    out[0] = vals[0] + alpha * init_value
    for i in range(1, len(vals)):
        out[i] = vals[i] + alpha * out[i - 1]
    return pd.Series(out, index=series.index), float(out[-1])


def build_design_matrix(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    feature_state: Optional[Dict[str, Any]] = None,
) -> tuple[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """
    Constructs from weekly-aggregated data:
      y = revenue
      X = intercept + centered trend + event dummies + spend columns

    Spend transformations (adstock, log) are applied conditionally per model_mode.
    Event dummy columns (event_*) are expected to already exist in df_weekly,
    applied at daily granularity and propagated through weekly aggregation.
    feature_state enables train/test consistency for trend centering and adstock.
    """
    config = get_model_config(model_mode)
    X = pd.DataFrame(index=df_weekly.index)

    # Intercept
    X["const"] = 1.0

    # Centered trend (reuse trend_mean from feature_state for test consistency)
    trend = df_weekly["week_index"].astype(float)
    if feature_state and "trend_mean" in feature_state:
        trend_mean = feature_state["trend_mean"]
    else:
        trend_mean = float(trend.mean())
    X["trend"] = trend - trend_mean

    # Event columns (pre-baked into df_weekly by apply_event_dummies + aggregation)
    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    for col in event_cols:
        X[col] = df_weekly[col].astype(float)

    # Spend columns: raw -> adstock (if enabled) -> log (if enabled)
    adstock_last_values: Dict[str, float] = {}
    for col in spend_cols:
        raw = df_weekly[col].astype(float)

        if config["use_adstock"] and config["adstock_alpha"] is not None:
            init_value = 0.0
            if feature_state and "adstock_last" in feature_state:
                init_value = feature_state["adstock_last"].get(col, 0.0)

            raw, last_val = geometric_adstock(
                raw,
                config["adstock_alpha"],
                init_value=init_value,
            )
            adstock_last_values[col] = last_val

        if config["use_log"]:
            raw = np.log1p(np.maximum(raw, 0.0))

        X[col] = raw

    y_raw = df_weekly["revenue"].astype(float)
    if config.get("use_log_target", False):
        y = np.log1p(np.maximum(y_raw, 0.0))
    else:
        y = y_raw
    y.index = X.index

    # Final sanity: no NaN
    assert X.isna().sum().sum() == 0, "Design matrix contains NaN"
    assert y.isna().sum() == 0, "Target vector contains NaN"

    new_feature_state: Dict[str, Any] = {
        "trend_mean": trend_mean,
    }
    if config["use_adstock"]:
        new_feature_state["adstock_last"] = adstock_last_values

    return X, y, new_feature_state
