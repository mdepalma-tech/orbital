"""Step 3 — Build the design matrix X and target vector y."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def get_model_config(model_mode: Optional[str]) -> Dict[str, Any]:
    """
    Deterministic model config from model_mode. No randomness, no tuning.

    Per-channel adstock alphas are now selected externally by
    select_adstock_alphas() and passed into build_design_matrix via
    the channel_alphas parameter.  use_adstock is retained as a boolean
    flag so downstream code (forecast, backtest) knows whether adstock
    was applied.
    """
    if model_mode == "causal_full":
        return {"use_adstock": True, "use_log": False, "use_log_target": False}
    if model_mode == "causal_cautious":
        return {"use_adstock": True, "use_log": False, "use_log_target": False}
    # diagnostic_stabilized or None
    return {"use_adstock": False, "use_log": False, "use_log_target": False}


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

def build_fourier_features(
    week_index: pd.Series,
    best_k: int,
    period: int,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Build Fourier sin/cos columns for a given week_index, k, and period.

    WHY THIS IS A SEPARATE FUNCTION:
    Both build_design_matrix (training) and forecast.py (prediction) need
    to generate identical Fourier columns. Centralising the logic here
    ensures they can never diverge — the forecast will always use the same
    sin/cos formula that was used to train the model.

    HOW FOURIER TERMS WORK:
    Each harmonic i adds two columns:
        sin(2π * i * t / period)
        cos(2π * i * t / period)

    Together they describe one frequency of a repeating wave. k=1 gives
    one broad annual wave. k=2 adds a faster wave on top, allowing the
    model to represent asymmetric or double-peaked seasonal shapes.

    The week_index (t) must be the same scale used during training — i.e.
    the raw week_index from df_weekly, not restarted from 0. This is
    important for forecast consistency: if training used t=[0..103] and
    forecast starts at t=104, the sin/cos values will correctly continue
    the wave rather than restart it.

    Args:
        week_index: Integer series of week indices (from df_weekly["week_index"]).
        best_k:     Number of Fourier harmonics selected by diagnostics.
        period:     Seasonal period in weeks (from diagnostics, typically 52).

    Returns:
        Tuple of (DataFrame of Fourier columns, list of column names).
        Empty DataFrame and [] if best_k == 0.
    """
    if best_k == 0:
        return pd.DataFrame(index=week_index.index), []

    t = week_index.values.astype(float)
    cols = {}
    col_names = []

    for i in range(1, best_k + 1):
        sin_col = f"sin_{i}"
        cos_col = f"cos_{i}"
        cols[sin_col] = np.sin(2 * np.pi * i * t / period)
        cols[cos_col] = np.cos(2 * np.pi * i * t / period)
        col_names.extend([sin_col, cos_col])

    return pd.DataFrame(cols, index=week_index.index), col_names

def build_design_matrix(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    feature_state: Optional[Dict[str, Any]] = None,
    channel_alphas: Optional[Dict[str, float]] = None,
) -> tuple[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """
    Constructs from weekly-aggregated data:
      y = revenue
      X = intercept + centered trend + event dummies + spend columns

    Column order matters for interpretability and VIF inspection:
      1. const          — intercept
      2. trend          — centered linear trend
      3. sin_1, cos_1   — first Fourier harmonic (if best_k >= 1)
         sin_2, cos_2   — second harmonic (if best_k >= 2)  ... etc.
      4. event_*        — pre-baked event dummies
      5. spend cols     — possibly adstocked and/or log-transformed

    WHY FOURIER TERMS SIT BETWEEN TREND AND EVENTS:
    Trend and seasonality are both baseline revenue components — they describe
    what revenue does absent any media or events. Grouping them together makes
    the coefficient table easier to read and makes it clear to the VIF check
    which columns are structural (trend + seasonality) vs. causal (spend).

    Spend transformations (adstock, log) are applied conditionally per model_mode.
    Event dummy columns (event_*) are expected to already exist in df_weekly.
    feature_state enables train/test consistency for trend centering and adstock.

    FORECAST CONSISTENCY:
    best_k and dominant_period are stored in feature_state so that forecast.py
    can call build_fourier_features() with the same parameters and generate
    identical columns for future weeks.
    """
    config = get_model_config(model_mode)
    X = pd.DataFrame(index=df_weekly.index)

    # Intercept
    X["const"] = 1.0

    # Centered trend (reuse trend_mean from feature_state for test consistency)
    # Centering must use training mean, not mean of current slice.

    trend = df_weekly["week_index"].astype(float)
    if feature_state and "trend_mean" in feature_state:
        trend_mean = feature_state["trend_mean"]
    else:
        trend_mean = float(trend.mean())
    X["trend"] = trend - trend_mean

# ------------------------------------------------------------------
    # 3. Fourier seasonality terms
    #
    # Read best_k and dominant_period from diagnostics. If diagnostics is
    # absent (e.g. in tests or legacy calls), skip silently — this keeps
    # the function backwards compatible.
    #
    # We also check feature_state first: if this is a test/forecast call,
    # feature_state carries the values that were used during training.
    # This is critical — using a different k or period for test than train
    # would produce mismatched columns and silently corrupt predictions.
    # ------------------------------------------------------------------
    if feature_state and "seasonality_k" in feature_state:
        # Test or forecast path: use training values exactly
        best_k = feature_state["seasonality_k"]
        dominant_period = feature_state["seasonality_period"]
    elif diagnostics and "seasonality" in diagnostics:
        # Training path: read from diagnostics output
        best_k = diagnostics["seasonality"]["best_k"]
        dominant_period = diagnostics["seasonality"]["dominant_period"]
    else:
        # Fallback: no seasonality (backwards compatible)
        best_k = 0
        dominant_period = 52

    fourier_df, fourier_cols = build_fourier_features(
        week_index=df_weekly["week_index"],
        best_k=best_k,
        period=dominant_period,
    )
    for col in fourier_cols:
        X[col] = fourier_df[col]

    # Event columns (pre-baked into df_weekly by apply_event_dummies + aggregation)
    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    for col in event_cols:
        X[col] = df_weekly[col].astype(float)

    # Resolve per-channel alphas: feature_state (test/forecast) > explicit arg > fallback 0.0
    if feature_state and "channel_alphas" in feature_state:
        resolved_alphas = feature_state["channel_alphas"]
    elif channel_alphas is not None:
        resolved_alphas = channel_alphas
    else:
        resolved_alphas = {}

    # Spend columns: raw -> adstock (per-channel alpha) -> log (if enabled)
    adstock_last_values: Dict[str, float] = {}
    for col in spend_cols:
        raw = df_weekly[col].astype(float)

        col_alpha = resolved_alphas.get(col, 0.0)
        if config["use_adstock"] and col_alpha > 0.0:
            init_value = 0.0
            if feature_state and "adstock_last" in feature_state:
                init_value = feature_state["adstock_last"].get(col, 0.0)

            raw, last_val = geometric_adstock(
                raw,
                col_alpha,
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
        "seasonality_k": best_k,
        "seasonality_period": dominant_period,
        "channel_alphas": resolved_alphas,
    }
    if config["use_adstock"]:
        new_feature_state["adstock_last"] = adstock_last_values

    return X, y, new_feature_state
