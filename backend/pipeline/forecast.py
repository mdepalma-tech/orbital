"""
Version-driven forecast engine.

Loads model_version from Supabase (feature_state, coefficients, model_config).
Does NOT rely on in-memory state from /run. Survives restarts and multi-worker setups.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from services.supabase_client import get_supabase
from pipeline.fetch import fetch_project_data
from pipeline.validate import validate_and_prepare, EPSILON, SPEND_COLUMNS
from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
from pipeline.matrix import geometric_adstock

logger = logging.getLogger(__name__)


def get_latest_weekly_row(
    project_id: str,
    spend_cols: List[str],
) -> tuple[int, Dict[str, float]]:
    """
    Fetch latest weekly actual row from DB.
    Returns (last_week_index, {col: spend_value}).
    """
    timeseries, spend, events = fetch_project_data(project_id)
    daily, events_clean, valid_spend_cols = validate_and_prepare(
        timeseries, spend, events
    )
    daily = apply_event_dummies(daily, events_clean)
    df_weekly = aggregate_to_weekly(daily, valid_spend_cols)

    weekly_varying = [
        c for c in valid_spend_cols
        if c in df_weekly.columns and df_weekly[c].std() > EPSILON
    ]
    cols_to_use = [c for c in spend_cols if c in weekly_varying]
    if not cols_to_use:
        cols_to_use = weekly_varying

    if len(df_weekly) == 0:
        raise ValueError("No weekly data after aggregation")

    # Use last row with non-zero spend; if last week has all zeros (spend ended before timeseries), step back
    spend_cols_in_df = [c for c in spend_cols if c in df_weekly.columns]
    last_idx = len(df_weekly) - 1
    while last_idx >= 0:
        row = df_weekly.iloc[last_idx]
        total_spend = sum(float(row.get(c, 0) or 0) for c in spend_cols_in_df)
        if total_spend > EPSILON:
            break
        last_idx -= 1

    if last_idx < 0:
        raise ValueError("No weekly row with non-zero spend found")

    last = df_weekly.iloc[last_idx]
    week_index = int(last["week_index"])
    baseline_spend = {
        col: float(last[col]) if col in last.index else 0.0
        for col in spend_cols
    }
    return week_index, baseline_spend


def get_historical_weekly_revenue(
    project_id: str,
    spend_cols: List[str],
    history_weeks: int = 8,
) -> List[Dict[str, Any]]:
    """
    Fetch last N weeks of (week_start, revenue, week_index) for chart display.
    Returns list of dicts with week_start (ISO date string), revenue, week_index.
    """
    timeseries, spend, events = fetch_project_data(project_id)
    daily, events_clean, valid_spend_cols = validate_and_prepare(
        timeseries, spend, events
    )
    daily = apply_event_dummies(daily, events_clean)
    df_weekly = aggregate_to_weekly(daily, valid_spend_cols)

    if len(df_weekly) == 0:
        return []

    tail = df_weekly.tail(history_weeks)
    result = []
    for _, row in tail.iterrows():
        ws = row["week_start"]
        if hasattr(ws, "strftime"):
            week_start_str = ws.strftime("%Y-%m-%d")
        else:
            week_start_str = str(ws)[:10]
        result.append({
            "week_start": week_start_str,
            "revenue": round(float(row["revenue"]), 2),
            "week_index": int(row["week_index"]),
        })
    return result


@dataclass
class LoadedModelVersion:
    """Model version loaded from DB for forecasting."""

    version_id: str
    model_id: str
    model_type: str
    ridge_applied: bool
    lags_added: int
    coefficients: Dict[str, float]
    feature_names: List[str]
    feature_state: Dict[str, Any]
    model_config: Dict[str, Any]
    spend_cols: List[str]


def load_latest_model_version(
    project_id: str,
    version_id: Optional[str] = None,
) -> LoadedModelVersion:
    """
    Load model_version from Supabase. Version-driven; no in-memory state from /run.

    Args:
        project_id: Project UUID.
        version_id: Specific version UUID. If None, loads the latest.

    Returns:
        LoadedModelVersion with feature_state, coefficients, model_config.

    Raises:
        ValueError: If no model version found.
    """
    sb = get_supabase()

    # Resolve model_id from project
    model_resp = (
        sb.table("models")
        .select("id")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    if not model_resp.data:
        raise ValueError(f"No model found for project {project_id}")

    model_id = model_resp.data[0]["id"]

    # Load model_version (specific or latest)
    if version_id:
        mv_resp = (
            sb.table("model_versions")
            .select("*")
            .eq("id", version_id)
            .eq("model_id", model_id)
            .limit(1)
            .execute()
        )
    else:
        # Latest: order by created_at (add column if missing)
        try:
            mv_resp = (
                sb.table("model_versions")
                .select("*")
                .eq("model_id", model_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception:
            mv_resp = (
                sb.table("model_versions")
                .select("*")
                .eq("model_id", model_id)
                .limit(1)
                .execute()
            )

    if not mv_resp.data:
        raise ValueError(
            f"No model version found for project {project_id}"
            + (f" (version {version_id})" if version_id else "")
        )

    mv = mv_resp.data[0]

    # Load coefficients
    coeff_resp = (
        sb.table("model_coefficients")
        .select("feature_name, coefficient")
        .eq("model_version_id", mv["id"])
        .execute()
    )
    coefficients = {
        row["feature_name"]: float(row["coefficient"])
        for row in (coeff_resp.data or [])
    }

    if not coefficients:
        raise ValueError(f"Model version {mv['id']} has no coefficients")

    # Parse model_config (stored as JSON string)
    model_config: Dict[str, Any] = {}
    if mv.get("model_config"):
        model_config = (
            json.loads(mv["model_config"])
            if isinstance(mv["model_config"], str)
            else mv["model_config"]
        )

    # Normalize use_log for backward compatibility (legacy persisted use_log_pre_fit)
    if "use_log" not in model_config and "use_log_pre_fit" in model_config:
        model_config["use_log"] = bool(model_config["use_log_pre_fit"])

    # feature_state from JSONB (Supabase returns dict)
    feature_state = mv.get("feature_state") or {}
    if isinstance(feature_state, str):
        feature_state = json.loads(feature_state)

    # Derive spend_cols from coefficient names (exclude const, trend, event_*)
    all_features = set(coefficients.keys())
    spend_cols = [
        c
        for c in SPEND_COLUMNS
        if c in all_features
    ]

    # Ridge relies on column order; OLS aligns by name. Use stored training order.
    feature_names = model_config.get("feature_names")
    if not feature_names:
        feature_names = list(coefficients.keys())
        if model_config.get("ridge_applied"):
            logger.warning(
                "Model version %s has ridge_applied but no feature_names in config; "
                "using coefficient keys. Ridge predictions may be wrong for legacy versions.",
                mv["id"],
            )

    return LoadedModelVersion(
        version_id=mv["id"],
        model_id=model_id,
        model_type=mv.get("model_type") or "ols",
        ridge_applied=bool(mv.get("ridge_applied")),
        lags_added=int(mv.get("lags_added") or 0),
        coefficients=coefficients,
        feature_names=feature_names,
        feature_state=feature_state,
        model_config=model_config,
        spend_cols=spend_cols,
    )


def build_X_for_prediction(
    df_weekly: pd.DataFrame,
    spend_cols: List[str],
    model_config: Dict[str, Any],
    feature_state: Dict[str, Any],
) -> pd.DataFrame:
    """
    Build design matrix X for prediction. Uses feature_state and model_config from loaded model_version.

    df_weekly must have: week_index, and columns for spend_cols and optional event_*.
    """
    use_adstock = model_config.get("use_adstock", False)
    use_log = bool(model_config.get("log_transform_post_fit", model_config.get("use_log", False)))
    # Per-channel alphas from feature_state; fall back to model_config for
    # backwards compatibility with older model versions that stored a single alpha.
    channel_alphas = feature_state.get("channel_alphas") or model_config.get("channel_alphas") or {}

    logger.info(
        "build_X_for_prediction: use_adstock=%s channel_alphas=%s use_log=%s trend_mean=%s adstock_last=%s",
        use_adstock,
        channel_alphas,
        use_log,
        feature_state.get("trend_mean"),
        feature_state.get("adstock_last"),
    )
    logger.info(
        "build_X_for_prediction: use_log keys use_log=%s use_log_pre_fit=%s -> resolved use_log=%s",
        model_config.get("use_log"),
        model_config.get("use_log_pre_fit"),
        use_log,
    )

    missing_cols = [c for c in spend_cols if c not in df_weekly.columns]
    if missing_cols:
        logger.warning("build_X_for_prediction: spend_cols missing from df_weekly (will be 0): %s", missing_cols)

    X = pd.DataFrame(index=df_weekly.index)

    X["const"] = 1.0

    trend = df_weekly["week_index"].astype(float)
    trend_mean = feature_state.get("trend_mean")
    if trend_mean is not None:
        trend_mean = float(trend_mean)
    else:
        trend_mean = float(trend.mean())
    X["trend"] = trend - trend_mean

    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    for col in event_cols:
        X[col] = df_weekly[col].astype(float)

    # Adstock carryover must propagate across rows; process row by row
    adstock_last = dict(feature_state.get("adstock_last") or {})
    for col in spend_cols:
        if col not in df_weekly.columns:
            X[col] = 0.0
            continue
        raw = df_weekly[col].astype(float)
        raw_vals = list(raw.values)

        col_alpha = float(channel_alphas.get(col, 0.0))
        if use_adstock and col_alpha > 0.0:
            transformed = []
            for i in range(len(raw)):
                val = raw.iloc[i] if hasattr(raw, "iloc") else raw.iat[i]
                init_value = float(adstock_last.get(col, 0.0))
                out, new_last = geometric_adstock(
                    pd.Series([float(val)]),
                    col_alpha,
                    init_value=init_value,
                )
                adstock_last[col] = new_last
                transformed.append(out.iloc[0])
            raw = pd.Series(transformed, index=raw.index)
            logger.debug(
                "build_X_for_prediction: %s raw_input=%s adstock_init=%s adstocked_output=%s alpha=%s",
                col,
                raw_vals,
                feature_state.get("adstock_last", {}).get(col),
                list(raw.values),
                col_alpha,
            )
        else:
            logger.debug("build_X_for_prediction: %s raw=%s (no adstock)", col, raw_vals)

        if use_log:
            raw = np.log1p(np.maximum(raw, 0.0))

        X[col] = raw

    # Log transformed spend for first/last week (post-log if applicable)
    for col in spend_cols:
        if col in X.columns:
            logger.info(
                "build_X_for_prediction: %s X values (week0=%.4f ... week_last=%.4f)",
                col,
                float(X[col].iloc[0]),
                float(X[col].iloc[-1]) if len(X) > 1 else float(X[col].iloc[0]),
            )
    logger.info("build_X_for_prediction: trend week0=%.4f week_last=%.4f", float(X["trend"].iloc[0]), float(X["trend"].iloc[-1]) if len(X) > 1 else float(X["trend"].iloc[0]))

    return X


def predict_revenue(
    loaded: LoadedModelVersion,
    X: pd.DataFrame,
) -> np.ndarray:
    """
    Apply coefficients to X. y_pred = X @ beta. Handles lag recursion when lags_added > 0.

    OLS and Ridge both use named coefficients; Ridge stores intercept as "const".
    feature_names defines column order for correct alignment.
    """
    # Ridge: intercept stored as coefficients["const"]; feature_names must include it
    if loaded.ridge_applied:
        if "const" not in loaded.feature_names:
            raise ValueError(
                "Ridge model missing 'const' in feature_names; "
                "intercept must be aligned for prediction"
            )
        if "const" not in loaded.coefficients:
            raise ValueError(
                "Ridge model missing 'const' in coefficients; "
                "intercept was not persisted"
            )

    beta = np.array([loaded.coefficients.get(f, 0.0) for f in loaded.feature_names])

    if loaded.lags_added == 0:
        X_aligned = X.reindex(columns=loaded.feature_names, fill_value=0.0)
        preds = X_aligned.values @ beta
        preds_arr = np.asarray(preds, dtype=float)
        # Debug: top coefficient contributors for first row
        row0 = X_aligned.iloc[0]
        contribs = [(f, float(row0.get(f, 0) * loaded.coefficients.get(f, 0))) for f in loaded.feature_names]
        contribs.sort(key=lambda x: abs(x[1]), reverse=True)
        logger.info(
            "predict_revenue: no lags, top5 contributions row0: %s",
            contribs[:5],
        )
    else:
        # Lag recursion: use last actuals from DB, then predicted values
        lag_history = list(loaded.feature_state.get("lag_history") or [])
        if len(lag_history) < loaded.lags_added:
            logger.warning(
                "lag_history has %d values but lags_added=%d; padding with zeros",
                len(lag_history),
                loaded.lags_added,
            )
            lag_history = [0.0] * (loaded.lags_added - len(lag_history)) + lag_history
        else:
            lag_history = lag_history[-loaded.lags_added:]

        lag_coefs = {f: loaded.coefficients.get(f, 0.0) for f in loaded.feature_names if f.startswith("lag_")}
        init_lag1 = lag_history[-1] if loaded.lags_added >= 1 else None
        init_lag2 = lag_history[-2] if loaded.lags_added >= 2 else None
        logger.info(
            "predict_revenue: lags_added=%d lag_history=%s lag_coefficients=%s (init_lag1=%.2f init_lag2=%.2f)",
            loaded.lags_added,
            lag_history,
            lag_coefs,
            (init_lag1 or 0),
            (init_lag2 or 0),
        )

        preds = []
        for i in range(len(X)):
            row = X.iloc[i].copy()
            if loaded.lags_added >= 1:
                row["lag_1"] = lag_history[-1]
            if loaded.lags_added >= 2:
                row["lag_2"] = lag_history[-2]
            row_aligned = row.reindex(loaded.feature_names, fill_value=0.0)
            y_hat = float(row_aligned.values @ beta)
            preds.append(y_hat)
            lag_history.append(y_hat)

        preds_arr = np.array(preds, dtype=float)
        logger.info(
            "predict_revenue: preds (log space)=%s",
            [round(p, 2) for p in preds_arr],
        )

    # Inverse transform if trained on log target
    use_log_target = bool(loaded.model_config.get("use_log_target", False))
    if use_log_target:
        smearing = float(loaded.model_config.get("smearing_factor", 1.0))
        preds_arr = smearing * np.exp(preds_arr) - 1.0

    preds_arr = np.maximum(preds_arr, 0.0)
    logger.info(
        "predict_revenue: final preds (revenue space)=%s",
        [round(p, 2) for p in preds_arr],
    )
    return preds_arr
