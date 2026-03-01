"""SSE streaming wrapper — yields reasoning + result events for each pipeline step."""

from __future__ import annotations

import json
from typing import Dict, Generator

from pipeline.fetch import fetch_project_data
from pipeline.validate import validate_and_prepare
from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
from pipeline.diagnostics import run_diagnostics
from pipeline.matrix import build_design_matrix
from pipeline.modeling import (
    ModelResult,
    fit_ols,
    check_vif,
    check_autocorrelation,
    check_heteroskedasticity,
    check_nonlinearity,
)
from pipeline.counterfactual import compute_counterfactual
from pipeline.anomalies import detect_anomalies
from pipeline.confidence import compute_confidence
from pipeline.persist import persist_results

import numpy as np
import pandas as pd


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


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
    n_obs = len(df_weekly)

    yield _sse({
        "type": "result",
        "id": "aggregate",
        "title": "Weekly Aggregation",
        "status": "pass",
        "metrics": {
            "daily_rows": len(daily),
            "weekly_rows": n_obs,
            "week_range": f"{df_weekly['week_start'].iloc[0].date()} to {df_weekly['week_start'].iloc[-1].date()}",
        },
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

    diagnostics = run_diagnostics(df_weekly, spend_cols)
    model_mode = diagnostics["model_mode"]

    yield _sse({
        "type": "result",
        "id": "diagnostics",
        "title": "Data Diagnostics",
        "status": "pass" if model_mode == "causal_full" else "warn",
        "metrics": {
            "score": diagnostics["score"],
            "model_mode": model_mode,
            "data_confidence_band": diagnostics["data_confidence_band"],
            "snapshot": diagnostics["snapshot"],
            "gating_reasons": diagnostics["gating_reasons"],
        },
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

    X, y = build_design_matrix(
        df_weekly,
        spend_cols,
        model_mode=model_mode,
        diagnostics=diagnostics,
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

    yield _sse({
        "type": "result",
        "id": "vif",
        "title": "VIF Test",
        "status": "pass" if vif_passed else "action",
        "metrics": {
            "vif_values": {k: round(v, 2) for k, v in result.vif_values.items()},
            "max_vif": max_vif,
            "threshold": 10,
            "ridge_applied": result.ridge_applied,
            "decision": "No multicollinearity detected" if vif_passed else f"Max VIF = {max_vif} > 10 → switched to Ridge regression",
        },
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

    # ── Step 7: Heteroskedasticity ───────────────────────────────────────
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

    # ── Step 8: Nonlinearity ─────────────────────────────────────────────
    pre_r2 = result.r2

    yield _sse({
        "type": "step",
        "id": "nonlinearity",
        "title": "Testing nonlinearity",
        "reasoning": (
            "Comparing the current model's R² with a log-transformed spend model. "
            "If log(spend+1) improves R² by more than 0.01, we adopt the log transform "
            "to capture diminishing returns in advertising spend."
        ),
    })

    result = check_nonlinearity(result, spend_cols)
    result.residual_std = float(np.std(result.residuals, ddof=1))

    log_applied = result.log_transform_applied
    r2_diff = round(result.r2 - pre_r2, 6) if log_applied else 0.0

    yield _sse({
        "type": "result",
        "id": "nonlinearity",
        "title": "Nonlinearity Test",
        "status": "action" if log_applied else "pass",
        "metrics": {
            "log_transform_applied": log_applied,
            "r2_improvement": r2_diff,
            "final_r_squared": round(result.r2, 6),
            "final_adjusted_r_squared": round(result.adj_r2, 6),
            "decision": f"Log transform improved R² by {r2_diff}" if log_applied else "Linear model is adequate",
        },
    })

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

    incremental, marginal_roi = compute_counterfactual(result, spend_cols)

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

    confidence = compute_confidence(result, n_obs)

    yield _sse({
        "type": "result",
        "id": "confidence",
        "title": "Confidence Score",
        "status": "pass" if confidence == "high" else ("warn" if confidence == "medium" else "fail"),
        "metrics": {
            "confidence_level": confidence,
            "r_squared": round(result.r2, 6),
            "observations": n_obs,
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
        )
    except Exception as e:
        yield _sse({"type": "error", "id": "persist", "message": str(e)})
        return

    yield _sse({
        "type": "result",
        "id": "persist",
        "title": "Results Saved",
        "status": "pass",
        "metrics": {"persisted": True},
    })

    # ── Complete ─────────────────────────────────────────────────────────
    yield _sse({
        "type": "complete",
        "id": "complete",
        "title": "Pipeline Complete",
        "summary": {
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
        },
    })
