"""SSE streaming wrapper — yields reasoning + result events for each pipeline step."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Dict, Generator

from pipeline.fetch import fetch_project_data
from pipeline.validate import validate_and_prepare, EPSILON
from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
from pipeline.diagnostics import run_diagnostics
from pipeline.adstock import select_adstock_alphas
from pipeline.matrix import build_design_matrix, get_model_config
from pipeline.modeling import (
    ModelResult,
    compare_alpha_objectives,
    fit_ols,
    check_vif,
    check_autocorrelation,
    check_heteroskedasticity,
    check_nonlinearity,
    run_model,
)
from pipeline.counterfactual import compute_counterfactual
from pipeline.anomalies import detect_anomalies
from pipeline.confidence import compute_confidence
from pipeline.persist import persist_results

import numpy as np
import pandas as pd


def _is_bad_float(val) -> bool:
    """True if value is NaN or Inf (invalid in JSON for JS parse)."""
    try:
        if isinstance(val, (int, str, bool, type(None))):
            return False
        f = float(val) if not isinstance(val, float) else val
        return math.isnan(f) or math.isinf(f)
    except (TypeError, ValueError):
        return False


def _sanitize_for_json(obj):
    """Recursively sanitize so JSON is valid (no NaN/Inf, JS-parseable)."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, "item"):
        val = obj.item()
        return _sanitize_for_json(val)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (int, float)) and _is_bad_float(obj):
        return None
    return obj


def _json_serializer(obj):
    """Convert numpy/pandas types for JSON. Return None for NaN/Inf (JS-invalid)."""
    if hasattr(obj, "item"):
        val = obj.item()
        return None if _is_bad_float(val) else val
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _sse(data: dict) -> str:
    sanitized = _sanitize_for_json(data)
    out = json.dumps(sanitized, default=_json_serializer)
    # Replace NaN/Inf (invalid for JS JSON.parse) with null in all contexts
    out = re.sub(r":\s*NaN\b", ": null", out)
    out = re.sub(r",\s*NaN\b", ", null", out)
    out = re.sub(r"\[\s*NaN\b", "[ null", out)
    out = re.sub(r":\s*-?Infinity\b", ": null", out)
    out = re.sub(r",\s*-?Infinity\b", ", null", out)
    return f"data: {out}\n\n"


def stream_pipeline(project_id: str) -> Generator[str, None, None]:
    """Generator that runs the full pipeline, yielding SSE events at each step."""

    # ── Step 1: Fetch ────────────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "fetch",
        "title": "Fetching project data",
        "reasoning": "Querying project_timeseries, project_spend, and project_events tables from Supabase for this project...",
    })

    try:
        timeseries, spend, events = fetch_project_data(project_id)
    except Exception as e:
        yield _sse({"type": "error", "id": "fetch", "message": str(e)})
        return

    n_ts = len(timeseries)
    n_spend = len(spend)
    n_events = len(events)
    date_min = str(timeseries["ts"].min()) if n_ts else "N/A"
    date_max = str(timeseries["ts"].max()) if n_ts else "N/A"

    yield _sse({
        "type": "result",
        "id": "fetch",
        "title": "Data Fetched",
        "status": "pass",
        "metrics": {
            "timeseries_rows": n_ts,
            "spend_rows": n_spend,
            "event_count": n_events,
            "date_range": f"{date_min[:10]} to {date_max[:10]}",
        },
    })

    # ── Step 2: Validate ─────────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "validate",
        "title": "Validating data integrity",
        "reasoning": (
            "Checking for continuous daily date index, filling any missing dates with zeros, "
            "validating that the revenue target has sufficient variance, and removing any "
            "spend channels with zero variance..."
        ),
    })

    try:
        daily, events_clean, spend_cols = validate_and_prepare(
            timeseries, spend, events
        )
    except ValueError as e:
        yield _sse({"type": "error", "id": "validate", "message": str(e)})
        return

    n_obs = len(daily)

    # Detect spend coverage gap for the result card
    spend_gap_days = 0
    if not spend.empty and n_ts > 0:
        ts_min = pd.to_datetime(timeseries["ts"]).min()
        sp_min = pd.to_datetime(spend["ts"]).min()
        if sp_min > ts_min:
            spend_gap_days = (sp_min - ts_min).days

    validate_status = "warn" if spend_gap_days > 0 else "pass"
    validate_metrics: Dict = {
        "observations": n_obs,
        "spend_channels_kept": spend_cols,
        "events_loaded": len(events_clean) if not events_clean.empty else 0,
    }
    if spend_gap_days > 0:
        validate_metrics["spend_coverage_gap_days"] = spend_gap_days
        validate_metrics["decision"] = (
            f"Spend data starts {spend_gap_days} day(s) after revenue data. "
            "Early period filled with spend=0, which may weaken coefficient estimates."
        )

    yield _sse({
        "type": "result",
        "id": "validate",
        "title": "Data Validated",
        "status": validate_status,
        "metrics": validate_metrics,
    })

    # ── Step 2.5: Weekly aggregation ─────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "aggregate",
        "title": "Aggregating to weekly frequency",
        "reasoning": (
            "Applying event dummy flags to the daily data, then aggregating "
            "revenue, orders, and spend to weekly totals (W-MON boundary). "
            "Event flags propagate via max. Weekly frequency reduces noise "
            "and stabilizes coefficient estimates."
        ),
    })

    daily = apply_event_dummies(daily, events_clean)
    df_weekly = aggregate_to_weekly(daily, spend_cols)

    # Remove weekly-constant spend columns
    weekly_varying_spend_cols = [
        c for c in spend_cols
        if c in df_weekly.columns and df_weekly[c].std() > EPSILON
    ]
    dropped_weekly_constant = [
        c for c in spend_cols
        if c not in weekly_varying_spend_cols
    ]
    spend_cols = weekly_varying_spend_cols

    if not spend_cols:
        yield _sse({
            "type": "error",
            "id": "aggregate",
            "message": "All spend channels are constant at weekly level; cannot estimate channel effects.",
        })
        return

    n_obs = len(df_weekly)

    if n_obs == 0:
        yield _sse({
            "type": "error",
            "id": "aggregate",
            "message": "No weekly observations after aggregation. Need at least one complete week of revenue and spend data.",
        })
        return

    week_range = f"{df_weekly['week_start'].iloc[0].date()} to {df_weekly['week_start'].iloc[-1].date()}"
    yield _sse({
        "type": "result",
        "id": "aggregate",
        "title": "Weekly Aggregation",
        "status": "pass",
        "metrics": {
            "daily_rows": len(daily),
            "weekly_rows": n_obs,
            "week_range": week_range,
        },
    })

    # ── Step 2.6: Out-of-sample backtest ──────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "backtest",
        "title": "Out-of-Sample Backtest",
        "reasoning": (
            "Splitting data 80/20 by time. Training on the first 80% and "
            "evaluating R², RMSE, and MAE on the held-out 20% to assess "
            "model generalization."
        ),
    })

    # --- Backtest split (80/20 time-based) ---
    split_idx = int(len(df_weekly) * 0.8)
    df_train = df_weekly.iloc[:split_idx]
    df_test = df_weekly.iloc[split_idx:]
    n_oos = len(df_test)

    # --- Backtest model (train only) ---
    diagnostics_train = run_diagnostics(df_train, spend_cols)
    model_mode_train = diagnostics_train["model_mode"]
    config_train = get_model_config(model_mode_train)

    # Per-channel adstock selection on the backtest train fold
    if config_train["use_adstock"]:
        channel_alphas_train = select_adstock_alphas(
            df_train, spend_cols, model_mode_train, diagnostics_train,
        )
    else:
        channel_alphas_train = {col: 0.0 for col in spend_cols}

    X_train, y_train, feature_state = build_design_matrix(
        df_train,
        spend_cols,
        model_mode=model_mode_train,
        diagnostics=diagnostics_train,
        channel_alphas=channel_alphas_train,
    )
    result_train = run_model(X_train, y_train, spend_cols)

    # Smearing from training fold only (result_train fit on df_train)
    use_log_target_train = getattr(result_train, "log_target_applied", False)
    smearing_train = 1.0
    if use_log_target_train:
        residuals_train = result_train.y.values - result_train.predicted
        smearing_train = float(np.mean(np.exp(residuals_train)))
        smearing_train = max(smearing_train, 1e-6)

    # --- Build test matrix with feature_state for consistency ---
    X_test, y_test, _ = build_design_matrix(
        df_test,
        spend_cols,
        model_mode=model_mode_train,
        feature_state=feature_state,
    )
    r2_oos = None
    rmse_oos = None
    mae_oos = None
    if n_oos >= 8:
        y_test_vals = y_test.values if hasattr(y_test, "values") else y_test
        if getattr(result_train, "lags_added", 0) == 0:
            if result_train.ridge_applied:
                X_pred = X_test.drop(columns=["const"], errors="ignore")
            else:
                X_pred = X_test
            y_pred_test = result_train.model.predict(X_pred)
        else:
            lags_added = int(result_train.lags_added)
            history = list(result_train.y.values)
            y_pred_list = []
            for i in range(len(X_test)):
                row = X_test.iloc[i].copy()
                if lags_added >= 1:
                    row["lag_1"] = history[-1]
                if lags_added >= 2:
                    row["lag_2"] = history[-2]
                row_df = pd.DataFrame([row])
                if result_train.ridge_applied:
                    row_df = row_df.drop(columns=["const"], errors="ignore")
                y_hat = float(result_train.model.predict(row_df)[0])
                y_pred_list.append(y_hat)
                history.append(y_hat)
            y_pred_test = np.array(y_pred_list, dtype=float)

        # OOS metrics always in revenue space (inverse-transform if use_log_target)
        if use_log_target_train:
            y_actual_rev = np.expm1(np.asarray(y_test_vals, dtype=float))
            y_pred_rev = np.maximum(smearing_train * np.exp(y_pred_test) - 1.0, 0.0)
        else:
            y_actual_rev = np.asarray(y_test_vals, dtype=float)
            y_pred_rev = np.asarray(y_pred_test, dtype=float)

        ss_res = float(np.sum((y_actual_rev - y_pred_rev) ** 2))
        ss_tot = float(np.sum((y_actual_rev - float(np.mean(y_actual_rev))) ** 2))
        r2_oos = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None
        rmse_oos = float(np.sqrt(np.mean((y_actual_rev - y_pred_rev) ** 2)))
        mae_oos = float(np.mean(np.abs(y_actual_rev - y_pred_rev)))

    oos_metrics = {
        "oos_n_obs": n_oos,
        "oos_r2": r2_oos if n_oos >= 8 else None,
        "oos_rmse": rmse_oos if n_oos >= 8 else None,
        "oos_mae": mae_oos if n_oos >= 8 else None,
        "oos_split_ratio": 0.8,
        "oos_model_mode": model_mode_train,
    }

    # Yield backtest result for Test Results panel
    oos_result_metrics: Dict = {
        "oos_n_obs": n_oos,
        "oos_split_ratio": 0.8,
        "oos_model_mode": model_mode_train,
    }
    if n_oos >= 8 and r2_oos is not None:
        oos_result_metrics["oos_r2"] = round(r2_oos, 6)
        oos_result_metrics["oos_rmse"] = round(rmse_oos, 4)
        oos_result_metrics["oos_mae"] = round(mae_oos, 4)
    else:
        oos_result_metrics["note"] = f"OOS metrics require ≥8 holdout observations (had {n_oos})"
    yield _sse({
        "type": "result",
        "id": "backtest",
        "title": "Out-of-Sample Backtest",
        "status": "pass" if n_oos >= 8 else "info",
        "metrics": oos_result_metrics,
    })

    # ── Step 2.75: Diagnostics ───────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "diagnostics",
        "title": "Running data diagnostics",
        "reasoning": (
            "Computing a data strength score based on weekly observation depth, "
            "spend variability, signal-to-noise ratio, and channel collinearity. "
            "This determines whether the pipeline runs in causal_full mode "
            "(full econometric testing) or diagnostic_stabilized mode "
            "(regularized estimation with relaxed gating)."
        ),
    })

    try:
        diagnostics = run_diagnostics(
            df_weekly,
            spend_cols,
            dropped_weekly_constant=dropped_weekly_constant,
        )
    except Exception as e:
        yield _sse({"type": "error", "id": "diagnostics", "message": str(e)})
        return

    model_mode = diagnostics["model_mode"]

    config = get_model_config(model_mode)

    # ── Step 2.8: Adstock alpha selection ────────────────────────────────
    if config["use_adstock"]:
        yield _sse({
            "type": "step",
            "id": "adstock_selection",
            "title": "Selecting per-channel adstock alphas",
            "reasoning": (
                "Grid-searching over decay rates [0.0 – 0.9] for each spend "
                "channel independently. For each candidate alpha, we adstock "
                "only that channel, fit OLS on the first 80% of weeks, and "
                "evaluate R² on the held-out 20%. The alpha that maximises "
                "out-of-sample R² is selected for each channel."
            ),
        })

        channel_alphas = select_adstock_alphas(
            df_weekly, spend_cols, model_mode, diagnostics,
        )

        yield _sse({
            "type": "result",
            "id": "adstock_selection",
            "title": "Adstock Alphas Selected",
            "status": "pass",
            "metrics": {
                "channel_alphas": channel_alphas,
            },
        })
    else:
        channel_alphas = {col: 0.0 for col in spend_cols}

    model_config = {
        "model_mode": model_mode,
        "use_adstock": config["use_adstock"],
        "channel_alphas": channel_alphas,
        "use_log": config["use_log"],
        "use_log_target": config.get("use_log_target", False),
    }

    # Ensure all metrics are JSON-serializable (no numpy types, no NaN/Inf)
    def _to_native(val):
        if hasattr(val, "item"):
            val = val.item()
        if isinstance(val, (int, float)) and _is_bad_float(val):
            return None
        return val

    diag_metrics = {
        "score": _to_native(diagnostics["score"]),
        "model_mode": model_mode,
        "data_confidence_band": diagnostics["data_confidence_band"],
        "snapshot": {k: _to_native(v) for k, v in diagnostics["snapshot"].items()},
        "gating_reasons": list(diagnostics["gating_reasons"]),
    }

    yield _sse({
        "type": "result",
        "id": "diagnostics",
        "title": "Data Diagnostics",
        "status": "pass" if model_mode == "causal_full" else "warn",
        "metrics": diag_metrics,
    })

    # ── Seasonality result ──────────────────────────────────────────────
    seasonality = diagnostics.get("seasonality") or {}
    n_obs = diagnostics.get("snapshot", {}).get("n_obs", 0)
    best_k = seasonality.get("best_k", 0)
    insufficient = n_obs < 104
    if insufficient:
        seasonality_status = "warn"
    elif best_k > 0:
        seasonality_status = "pass"
    else:
        seasonality_status = "info"

    seasonality_metrics = {
        "best_k": _to_native(seasonality.get("best_k")),
        "dominant_period": _to_native(seasonality.get("dominant_period")),
        "acf_confirmed": bool(seasonality.get("acf_confirmed", False)),
        "strength": _to_native(seasonality.get("strength")),
        "n_obs": _to_native(n_obs),
        "insufficient_data": insufficient,
    }
    aic_by_k = seasonality.get("aic_by_k")
    if isinstance(aic_by_k, dict):
        seasonality_metrics["aic_by_k"] = {
            str(k): _to_native(v) for k, v in aic_by_k.items()
        }
    else:
        seasonality_metrics["aic_by_k"] = {}

    yield _sse({
        "type": "result",
        "id": "seasonality",
        "title": "Seasonality",
        "status": seasonality_status,
        "metrics": seasonality_metrics,
    })

    # ── Step 3: Design matrix ────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "matrix",
        "title": "Building design matrix",
        "reasoning": (
            "Constructing the feature matrix X with intercept, linear trend, "
            "event dummy columns, and spend columns from weekly data. "
            "Target vector y = weekly revenue."
        ),
    })

    X, y, feature_state = build_design_matrix(
        df_weekly,
        spend_cols,
        model_mode=model_mode,
        diagnostics=diagnostics,
        channel_alphas=channel_alphas,
    )

    yield _sse({
        "type": "result",
        "id": "matrix",
        "title": "Design Matrix Built",
        "status": "pass",
        "metrics": {
            "rows": int(X.shape[0]),
            "features": int(X.shape[1]),
            "feature_names": list(X.columns),
        },
    })

    # ── Step 4: Base OLS ─────────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "ols",
        "title": "Fitting base OLS regression",
        "reasoning": (
            "Running Ordinary Least Squares regression on the full design matrix. "
            "This gives us the baseline model to test for multicollinearity, "
            "autocorrelation, heteroskedasticity, and nonlinearity."
        ),
    })

    result = fit_ols(X, y)

    yield _sse({
        "type": "result",
        "id": "ols",
        "title": "Base OLS Fitted",
        "status": "pass",
        "metrics": {
            "r_squared": round(result.r2, 6),
            "adjusted_r_squared": round(result.adj_r2, 6),
            "residual_std": round(result.residual_std, 2),
        },
    })

    # ── Step 5: VIF ──────────────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "vif",
        "title": "Testing multicollinearity (VIF)",
        "reasoning": (
            "Computing the Variance Inflation Factor for each spend channel. "
            "If any VIF exceeds 10, the spend channels are highly correlated and "
            "we switch from OLS to Ridge regression to stabilize coefficients."
        ),
    })

    result = check_vif(result, spend_cols)
    max_vif = round(max(result.vif_values.values()), 4) if result.vif_values else 0
    vif_passed = max_vif <= 10

    vif_metrics = {
        "vif_values": {k: round(v, 2) for k, v in result.vif_values.items()},
        "max_vif": max_vif,
        "threshold": 10,
        "ridge_applied": result.ridge_applied,
    }
    if result.ridge_applied:
        vif_metrics["vif_note"] = "pre-regularization (Ridge addresses collinearity via coefficient shrinkage)"
        vif_metrics["ridge_alpha"] = round(result.ridge_alpha, 4)
        vif_metrics["stability_threshold"] = result.stability_threshold
        # Show per-channel Ridge coefficients so user can see the regularization outcome
        spend_coefs = {}
        for col in spend_cols:
            if col in result.coefficients.index:
                spend_coefs[col] = round(float(result.coefficients[col]), 6)
        if spend_coefs:
            vif_metrics["ridge_coefficients"] = spend_coefs
            neg_coefs = [c for c, v in spend_coefs.items() if v < 0]
            if neg_coefs:
                vif_metrics["negative_spend_warning"] = neg_coefs
        try:
            alpha_comp_df = compare_alpha_objectives(result.X, result.y, spend_cols)
            vif_metrics["alpha_comparison"] = alpha_comp_df.replace({np.nan: None}).to_dict(orient="records")
        except Exception:
            vif_metrics["alpha_comparison"] = []
    vif_metrics["decision"] = "No multicollinearity detected" if vif_passed else f"Max VIF = {max_vif} > 10 → switched to Ridge regression"

    yield _sse({
        "type": "result",
        "id": "vif",
        "title": "VIF Test",
        "status": "pass" if vif_passed else "action",
        "metrics": vif_metrics,
    })

    # ── Step 6: Autocorrelation ──────────────────────────────────────────
    pre_lags = result.lags_added
    pre_hac = result.hac_applied

    yield _sse({
        "type": "step",
        "id": "autocorrelation",
        "title": "Testing autocorrelation",
        "reasoning": (
            "Computing the Durbin-Watson statistic and Ljung-Box test on residuals. "
            "If significant autocorrelation is detected (p < 0.05), we add lagged "
            "dependent variables (up to 2 lags). If still significant, we apply "
            "HAC-robust standard errors."
        ),
    })

    result = check_autocorrelation(result, spend_cols)
    lb_passed = result.ljung_box_p >= 0.05

    decision_parts = []
    if result.lags_added > pre_lags:
        decision_parts.append(f"Added {result.lags_added} lag(s)")
    if result.hac_applied and not pre_hac:
        decision_parts.append("Applied HAC robust standard errors")
    if not decision_parts:
        decision_parts.append("No autocorrelation detected")

    yield _sse({
        "type": "result",
        "id": "autocorrelation",
        "title": "Autocorrelation Test",
        "status": "pass" if lb_passed else "action",
        "metrics": {
            "durbin_watson": round(result.dw_stat, 4),
            "ljung_box_p": round(result.ljung_box_p, 6),
            "threshold": 0.05,
            "lags_added": result.lags_added,
            "hac_applied": result.hac_applied,
            "decision": "; ".join(decision_parts),
        },
    })

    # ── Step 7: Nonlinearity (3-way race) ──────────────────────────────
    pre_r2 = result.r2

    yield _sse({
        "type": "step",
        "id": "nonlinearity",
        "title": "Testing nonlinearity",
        "reasoning": (
            "Running a 3-way race: Base (linear) vs Linear-Log (log spend) vs "
            "Log-Log (log spend + log target). All candidates are compared in "
            "dollar-space R² using Duan's smearing estimator for fair comparison. "
            "Winner must beat current best by > 0.01."
        ),
    })

    result = check_nonlinearity(result, spend_cols)
    log_applied = result.log_transform_applied
    log_target = getattr(result, "log_target_applied", False)
    r2_diff = round(result.dollar_r2 - pre_r2, 6) if (log_applied or log_target) else 0.0

    if log_target:
        nl_decision = f"Log-Log selected (dollar R² = {round(result.dollar_r2, 4)})"
    elif log_applied:
        nl_decision = f"Linear-Log selected (R² improved by {r2_diff})"
    else:
        nl_decision = "Linear model is adequate"

    yield _sse({
        "type": "result",
        "id": "nonlinearity",
        "title": "Nonlinearity Test",
        "status": "action" if (log_applied or log_target) else "pass",
        "metrics": {
            "log_transform_applied": log_applied,
            "log_target_applied": log_target,
            "dollar_r2": round(result.dollar_r2, 6),
            "r2_improvement": r2_diff,
            "final_r_squared": round(result.r2, 6),
            "final_adjusted_r_squared": round(result.adj_r2, 6),
            "decision": nl_decision,
        },
    })

    # ── Step 8: Heteroskedasticity ───────────────────────────────────────
    pre_hac = result.hac_applied

    yield _sse({
        "type": "step",
        "id": "heteroskedasticity",
        "title": "Testing heteroskedasticity",
        "reasoning": (
            "Running the Breusch-Pagan test to check if the residual variance "
            "changes systematically across observations. If significant (p < 0.05), "
            "we apply HAC-robust standard errors to correct inference."
        ),
    })

    result = check_heteroskedasticity(result)
    bp_passed = result.breusch_pagan_p >= 0.05

    bp_decision = "No heteroskedasticity detected"
    if not bp_passed and result.hac_applied and not pre_hac:
        bp_decision = f"BP p = {round(result.breusch_pagan_p, 6)} < 0.05 → Applied HAC robust standard errors"
    elif not bp_passed and result.ridge_applied:
        bp_decision = "Skipped (Ridge regression in use)"
    elif not bp_passed:
        bp_decision = f"BP p = {round(result.breusch_pagan_p, 6)} < 0.05 (HAC already applied)"

    yield _sse({
        "type": "result",
        "id": "heteroskedasticity",
        "title": "Heteroskedasticity Test",
        "status": "pass" if bp_passed else "action",
        "metrics": {
            "breusch_pagan_p": round(result.breusch_pagan_p, 6),
            "threshold": 0.05,
            "hac_applied": result.hac_applied,
            "decision": bp_decision,
        },
    })

    # Flag negative spend coefficients on the final model
    result.residual_std = float(np.std(result.residuals, ddof=1))
    neg = [c for c in spend_cols
           if c in result.coefficients.index and float(result.coefficients[c]) < 0]
    if neg:
        result.negative_spend_cols = neg

    use_log_target = getattr(result, "log_target_applied", False)
    smearing_factor = 1.0
    if use_log_target:
        # Recompute Duan's smearing on post-HAC residuals
        residuals = result.y.values - result.predicted
        smearing_factor = max(float(np.mean(np.exp(residuals))), 1e-6)
        # Recompute dollar_r2 with post-HAC residuals
        y_original = np.expm1(result.y.values)
        preds_dollar = np.maximum(smearing_factor * np.exp(result.predicted) - 1.0, 0.0)
        ss_res = float(np.sum((y_original - preds_dollar) ** 2))
        ss_tot = float(np.sum((y_original - y_original.mean()) ** 2))
        result.dollar_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        n, p = result.X.shape
        result.dollar_adj_r2 = 1.0 - (1.0 - result.dollar_r2) * (n - 1) / (n - p - 1) if n > p + 1 else result.dollar_r2
    else:
        result.dollar_r2 = result.r2
        result.dollar_adj_r2 = result.adj_r2

    model_config_updates: Dict = {
        "model_type": result.model_type,
        "ridge_applied": result.ridge_applied,
        "ridge_alpha": result.ridge_alpha if result.ridge_applied else None,
        "lags_added": result.lags_added,
        "hac_applied": result.hac_applied,
        "log_transform_post_fit": result.log_transform_applied,
        "feature_names": list(result.X.columns),
        "use_log_target": use_log_target,
        "smearing_factor": smearing_factor,
        "negative_spend_cols": result.negative_spend_cols,
    }
    if result.ridge_applied and vif_metrics.get("alpha_comparison"):
        model_config_updates["alpha_comparison"] = vif_metrics["alpha_comparison"]
    model_config.update(model_config_updates)
    model_config = _sanitize_for_json(model_config)
    config_hash = hashlib.sha256(
        json.dumps(model_config, sort_keys=True).encode()
    ).hexdigest()

    model_config_with_hash = {
        **model_config,
        "config_hash": config_hash,
    }

    # ── Step 9: Counterfactual ───────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "counterfactual",
        "title": "Computing counterfactual impact",
        "reasoning": (
            "For each spend channel, we zero out its values and re-predict. "
            "The difference between actual and counterfactual predictions gives us "
            "the incremental revenue attributable to each channel, and dividing by "
            "total spend gives the marginal ROI."
        ),
    })

    incremental, marginal_roi = compute_counterfactual(
        result,
        spend_cols,
        use_log_target=use_log_target,
        smearing_factor=smearing_factor,
        df_weekly=df_weekly,
    )

    yield _sse({
        "type": "result",
        "id": "counterfactual",
        "title": "Counterfactual Impact",
        "status": "info",
        "metrics": {
            "incremental_revenue": incremental,
            "marginal_roi": marginal_roi,
        },
    })

    # ── Step 10: Anomalies ───────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "anomalies",
        "title": "Detecting residual anomalies",
        "reasoning": (
            "Scanning all residuals for anomalous weeks where the z-score exceeds "
            "±2.5 standard deviations. These are weeks where actual revenue deviated "
            "significantly from what the model predicted."
        ),
    })

    anomalies = detect_anomalies(result, df_weekly["week_start"])

    top_anomalies = sorted(anomalies, key=lambda a: abs(a["z_score"]), reverse=True)[:5]

    yield _sse({
        "type": "result",
        "id": "anomalies",
        "title": "Anomaly Detection",
        "status": "info" if not anomalies else "warn",
        "metrics": {
            "anomaly_count": len(anomalies),
            "z_threshold": 2.5,
            "top_anomalies": top_anomalies,
        },
    })

    # ── Step 11: Confidence ──────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "confidence",
        "title": "Computing confidence score",
        "reasoning": (
            "Evaluating model confidence using deterministic rules: "
            "R² thresholds, observation count, VIF levels, and spend variation. "
            "Returns high, medium, or low."
        ),
    })

    # Use effective row count for data volume checks (after lag drops in check_autocorrelation)
    n_obs_effective = int(result.X.shape[0])
    confidence = compute_confidence(
        result, n_obs, oos_metrics=oos_metrics, n_obs_effective=n_obs_effective
    )

    yield _sse({
        "type": "result",
        "id": "confidence",
        "title": "Confidence Score",
        "status": "pass" if confidence == "high" else ("warn" if confidence == "medium" else "fail"),
        "metrics": {
            "confidence_level": confidence,
            "r_squared": round(result.r2, 6),
            "observations": n_obs_effective,
            "model_type": result.model_type,
        },
    })

    # ── Step 12: Persist ─────────────────────────────────────────────────
    yield _sse({
        "type": "step",
        "id": "persist",
        "title": "Saving results to database",
        "reasoning": (
            "Persisting the final model, version, coefficients, diagnostics, and "
            "anomalies to Supabase. A config_hash is generated for versioning."
        ),
    })

    # For lag models: persist last N actuals for recursive forecast
    feature_state_to_persist = dict(feature_state) if feature_state else {}
    if result.lags_added > 0:
        last_actuals = list(result.y.values)[-result.lags_added:]
        feature_state_to_persist["lag_history"] = [
            float(y) for y in last_actuals
        ]

    try:
        persist_results(
            project_id=project_id,
            result=result,
            spend_cols=spend_cols,
            incremental=incremental,
            marginal_roi=marginal_roi,
            anomalies=anomalies,
            confidence_level=confidence,
            n_obs=n_obs,
            diagnostics=diagnostics,
            model_config=model_config_with_hash,
            config_hash=config_hash,
            oos_metrics=oos_metrics,
            feature_state=feature_state_to_persist,
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        err_msg = f"Persist failed: {type(e).__name__}: {str(e)}"
        print(err_msg, flush=True)
        print(tb, flush=True)
        yield _sse({"type": "error", "id": "persist", "message": err_msg})
        return

    yield _sse({
        "type": "result",
        "id": "persist",
        "title": "Results Saved",
        "status": "pass",
        "metrics": {"persisted": True},
    })

    # ── Complete ─────────────────────────────────────────────────────────
    summary: Dict = {
        "model_type": result.model_type,
        "model_mode": model_mode,
        "lags_added": result.lags_added,
        "log_transform": result.log_transform_applied,
        "hac_applied": result.hac_applied,
        "r2": round(result.r2, 6),
        "adjusted_r2": round(result.adj_r2, 6),
        "confidence_level": confidence,
        "incremental_impact": incremental,
        "marginal_roi": marginal_roi,
        "anomaly_count": len(anomalies),
    }
    if result.negative_spend_cols:
        summary["negative_spend_warning"] = result.negative_spend_cols
    if oos_metrics:
        summary["oos_n_obs"] = oos_metrics.get("oos_n_obs")
        summary["oos_r2"] = round(oos_metrics["oos_r2"], 6) if oos_metrics.get("oos_r2") is not None else None
        summary["oos_rmse"] = round(oos_metrics["oos_rmse"], 4) if oos_metrics.get("oos_rmse") is not None else None
        summary["oos_mae"] = round(oos_metrics["oos_mae"], 4) if oos_metrics.get("oos_mae") is not None else None
    yield _sse({
        "type": "complete",
        "id": "complete",
        "title": "Pipeline Complete",
        "summary": summary,
    })
