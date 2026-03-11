"""POST /v1/projects/{project_id}/run — full deterministic modeling pipeline."""

import hashlib
import json
import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.responses import RunModelResponse
from pipeline.adstock import select_adstock_alphas
from pipeline.fetch import fetch_project_data
from pipeline.validate import validate_and_prepare, EPSILON
from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
from pipeline.diagnostics import run_diagnostics
from pipeline.matrix import build_design_matrix, get_model_config
from pipeline.modeling import compare_alpha_objectives, run_model
from pipeline.counterfactual import compute_counterfactual
from pipeline.anomalies import detect_anomalies
from pipeline.confidence import compute_confidence
from pipeline.persist import persist_results
from pipeline.stream import stream_pipeline
from pipeline.forecast import (
    load_latest_model_version,
    get_latest_weekly_row,
    get_historical_weekly_revenue,
    build_X_for_prediction,
    predict_revenue,
)
from services.supabase_client import get_supabase

from schemas.responses import (
    ForecastRequest,
    ForecastResponse,
    ForecastScenarioCreate,
    ForecastScenarioUpdate,
)

from pipeline.tree_builder import build_pipeline_tree

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_latest_model_version_id(project_id: str) -> str:
    """Resolve project_id -> latest model_version id. Raises ValueError if not found."""
    sb = get_supabase()
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
    try:
        mv_resp = (
            sb.table("model_versions")
            .select("id")
            .eq("model_id", model_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        mv_resp = (
            sb.table("model_versions")
            .select("id")
            .eq("model_id", model_id)
            .limit(1)
            .execute()
        )
    if not mv_resp.data:
        raise ValueError(f"No model version found for project {project_id}")
    return mv_resp.data[0]["id"]


@router.post("/projects/{project_id}/forecast", response_model=ForecastResponse)
def forecast(project_id: str, body: ForecastRequest):
    """Version-driven forecast: loads model_version from DB, uses feature_state. No in-memory state from /run."""
    try:
        loaded = load_latest_model_version(
            project_id, version_id=body.version_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    logger.info(
        "forecast: loaded model_version=%s spend_cols=%s use_adstock=%s channel_alphas=%s lags_added=%d",
        loaded.version_id,
        loaded.spend_cols,
        loaded.model_config.get("use_adstock", False),
        loaded.feature_state.get("channel_alphas") or loaded.model_config.get("channel_alphas"),
        loaded.lags_added,
    )

    try:
        last_week_index, baseline_spend = get_latest_weekly_row(
            project_id, loaded.spend_cols
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "forecast: baseline last_week_index=%d baseline_spend=%s",
        last_week_index,
        baseline_spend,
    )

    mult = body.spend_multiplier

    if body.weeks and len(body.weeks) > 0:
        df = pd.DataFrame([
            {
                "week_index": w.week_index,
                "meta_spend": w.meta_spend,
                "google_spend": w.google_spend,
                "tiktok_spend": w.tiktok_spend,
            }
            for w in body.weeks
        ])
        for col in loaded.spend_cols:
            if col not in df.columns:
                df[col] = baseline_spend.get(col, 0.0) * mult
    else:
        df = pd.DataFrame([
            {
                "week_index": last_week_index + i,
                **{col: baseline_spend.get(col, 0.0) * mult for col in loaded.spend_cols},
            }
            for i in range(1, body.horizon + 1)
        ])

    # Guarantee all spend_cols exist; never rely on build_X fallback to zero
    for col in loaded.spend_cols:
        if col not in df.columns:
            df[col] = baseline_spend.get(col, 0.0) * mult

    event_cols = [c for c in loaded.coefficients if c.startswith("event_")]
    for col in event_cols:
        df[col] = 0.0

    if len(df) == 0:
        historical = get_historical_weekly_revenue(
            project_id, loaded.spend_cols, body.history_weeks
        )
        return ForecastResponse(
            version_id=loaded.version_id,
            predictions=[],
            historical=historical,
        )

    logger.info(
        "forecast: df columns=%s df_spend_sample=%s",
        list(df.columns),
        {c: list(df[c].values) for c in loaded.spend_cols if c in df.columns},
    )

    # Steady-state adstock when spend is constant: A_ss = spend / (1 - alpha)
    use_adstock = loaded.model_config.get("use_adstock", False)
    channel_alphas = loaded.feature_state.get("channel_alphas") or loaded.model_config.get("channel_alphas") or {}
    if use_adstock and channel_alphas:
        steady_state = {}
        for col in loaded.spend_cols:
            col_alpha = float(channel_alphas.get(col, 0.0))
            if col_alpha > 0.0 and col_alpha < 1.0:
                denom = 1.0 - col_alpha
                steady_state[col] = round(baseline_spend.get(col, 0.0) * mult / denom, 2)
            else:
                steady_state[col] = round(baseline_spend.get(col, 0.0) * mult, 2)
        logger.info(
            "forecast: steady_state_adstock channel_alphas=%s steady_state=%s",
            channel_alphas,
            steady_state,
        )

    X = build_X_for_prediction(
        df,
        loaded.spend_cols,
        loaded.model_config,
        loaded.feature_state,
    )
    preds = predict_revenue(loaded, X)
    pred_list = [round(float(p), 2) for p in preds]
    week_deltas = (
        [round(pred_list[i] - pred_list[i - 1], 2) for i in range(1, len(pred_list))]
        if len(pred_list) > 1
        else []
    )
    logger.info(
        "forecast: predictions=%s week_over_week_delta=%s",
        pred_list,
        week_deltas,
    )
    historical = get_historical_weekly_revenue(
        project_id, loaded.spend_cols, body.history_weeks
    )

    return ForecastResponse(
        version_id=loaded.version_id,
        predictions=pred_list,
        last_week_index=last_week_index,
        spend_cols=loaded.spend_cols,
        baseline_spend=baseline_spend,
        historical=historical,
    )


# ── Forecast Scenarios CRUD ───────────────────────────────────────────────


@router.get("/projects/{project_id}/forecast/scenarios")
def list_forecast_scenarios(project_id: str):
    """List saved forecast scenarios for the project's latest model version."""
    try:
        mv_id = _get_latest_model_version_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sb = get_supabase()
    resp = (
        sb.table("forecast_scenarios")
        .select("id, model_version_id, name, last_week_index, spend_cols, weeks, created_at")
        .eq("model_version_id", mv_id)
        .order("created_at", desc=True)
        .execute()
    )
    items = [
        {
            "id": r["id"],
            "model_version_id": r["model_version_id"],
            "name": r["name"],
            "last_week_index": r["last_week_index"],
            "spend_cols": r["spend_cols"] or [],
            "weeks": r["weeks"] or [],
            "created_at": r.get("created_at"),
        }
        for r in (resp.data or [])
    ]
    return {"scenarios": items}


@router.post("/projects/{project_id}/forecast/scenarios")
def create_forecast_scenario(project_id: str, body: ForecastScenarioCreate):
    """Save a new forecast scenario."""
    try:
        mv_id = _get_latest_model_version_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sb = get_supabase()
    weeks_json = [w.model_dump() for w in body.weeks]
    row = {
        "model_version_id": mv_id,
        "name": body.name,
        "last_week_index": body.last_week_index,
        "spend_cols": body.spend_cols,
        "weeks": weeks_json,
    }
    resp = sb.table("forecast_scenarios").insert(row).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create scenario")
    created = resp.data[0]
    return {
        "id": created["id"],
        "model_version_id": created["model_version_id"],
        "name": created["name"],
        "last_week_index": created["last_week_index"],
        "spend_cols": created["spend_cols"],
        "weeks": created["weeks"],
        "created_at": created.get("created_at"),
    }


@router.get("/projects/{project_id}/forecast/scenarios/{scenario_id}")
def get_forecast_scenario(project_id: str, scenario_id: str):
    """Get a single forecast scenario by id."""
    try:
        mv_id = _get_latest_model_version_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sb = get_supabase()
    resp = (
        sb.table("forecast_scenarios")
        .select("*")
        .eq("id", scenario_id)
        .eq("model_version_id", mv_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Scenario not found")
    r = resp.data[0]
    return {
        "id": r["id"],
        "model_version_id": r["model_version_id"],
        "name": r["name"],
        "last_week_index": r["last_week_index"],
        "spend_cols": r["spend_cols"] or [],
        "weeks": r["weeks"] or [],
        "created_at": r.get("created_at"),
    }


@router.patch("/projects/{project_id}/forecast/scenarios/{scenario_id}")
def update_forecast_scenario(project_id: str, scenario_id: str, body: ForecastScenarioUpdate):
    """Update a forecast scenario (name and/or weeks)."""
    try:
        mv_id = _get_latest_model_version_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sb = get_supabase()
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.weeks is not None:
        updates["weeks"] = [w.model_dump() for w in body.weeks]
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    resp = (
        sb.table("forecast_scenarios")
        .update(updates)
        .eq("id", scenario_id)
        .eq("model_version_id", mv_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Scenario not found")
    r = resp.data[0]
    return {
        "id": r["id"],
        "model_version_id": r["model_version_id"],
        "name": r["name"],
        "last_week_index": r["last_week_index"],
        "spend_cols": r["spend_cols"],
        "weeks": r["weeks"],
        "created_at": r.get("created_at"),
    }


@router.delete("/projects/{project_id}/forecast/scenarios/{scenario_id}")
def delete_forecast_scenario(project_id: str, scenario_id: str):
    """Delete a forecast scenario."""
    try:
        mv_id = _get_latest_model_version_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sb = get_supabase()
    resp = (
        sb.table("forecast_scenarios")
        .delete()
        .eq("id", scenario_id)
        .eq("model_version_id", mv_id)
        .execute()
    )
    return {"deleted": True}


@router.get("/pipeline/tree")
def get_pipeline_tree(force: bool = False):
    """Return the pipeline tree as JSON. Rebuilds if source has changed."""
    tree = build_pipeline_tree(force_rebuild=force)
    return tree.to_dict()


@router.get("/projects/{project_id}/run/stream")
def run_pipeline_stream(project_id: str):
    return StreamingResponse(
        stream_pipeline(project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/projects/{project_id}/run",
    response_model=RunModelResponse,
)
def run_pipeline(project_id: str):
    # Step 1 — Fetch
    try:
        timeseries, spend, events = fetch_project_data(project_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Step 2 — Validate & prepare
    try:
        daily, events_clean, spend_cols = validate_and_prepare(
            timeseries, spend, events
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 2.5 — Weekly aggregation
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
        raise HTTPException(
            status_code=400,
            detail="All spend channels are constant at weekly level; cannot estimate channel effects.",
        )

    n_obs = len(df_weekly)

    # --- Backtest split (80/20 time-based split) ---
    split_idx = int(len(df_weekly) * 0.8)
    df_train = df_weekly.iloc[:split_idx]
    df_test = df_weekly.iloc[split_idx:]
    n_oos = len(df_test)

    # --- Backtest model (train only) ---
    diagnostics_train = run_diagnostics(df_train, spend_cols)
    model_mode_train = diagnostics_train["model_mode"]
    config_train = get_model_config(model_mode_train)

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
    use_log_target_train = config_train.get("use_log_target", False)
    smearing_train = 1.0
    if use_log_target_train:
        residuals_train = result_train.y.values - result_train.predicted
        smearing_train = float(np.mean(np.exp(residuals_train)))
        smearing_train = max(smearing_train, 1e-6)

    # --- Build test matrix using same model_mode and feature_state ---
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

        # Direct prediction if no lag terms were added during training
        if getattr(result_train, "lags_added", 0) == 0:
            if result_train.ridge_applied:
                X_pred = X_test.drop(columns=["const"], errors="ignore")
            else:
                X_pred = X_test
            y_pred_test = result_train.model.predict(X_pred)

        else:
            # Recursive prediction for lag models (lag_1 = y_{t-1}, lag_2 = y_{t-2})
            lags_added = int(result_train.lags_added)

            # Initialize history with *training actuals* (not predictions)
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

                # Recursive: next step uses predicted value
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

    # Step 2.75 — Diagnostics (production: full data)
    diagnostics = run_diagnostics(
        df_weekly,
        spend_cols,
        dropped_weekly_constant=dropped_weekly_constant,
    )
    model_mode = diagnostics["model_mode"]

    config = get_model_config(model_mode)

    # Per-channel adstock selection
    if config["use_adstock"]:
        channel_alphas = select_adstock_alphas(
            df_weekly, spend_cols, model_mode, diagnostics,
        )
    else:
        channel_alphas = {col: 0.0 for col in spend_cols}

    model_config = {
        "model_mode": model_mode,
        "use_adstock": config["use_adstock"],
        "channel_alphas": channel_alphas,
        "use_log": config["use_log"],
        "use_log_target": config.get("use_log_target", False),
    }

    # Step 3 — Build design matrix
    X, y, feature_state = build_design_matrix(
        df_weekly,
        spend_cols,
        model_mode=model_mode,
        diagnostics=diagnostics,
        channel_alphas=channel_alphas,
    )

    # Steps 4–9 — Model fitting + decision tree
    result = run_model(X, y, spend_cols)

    use_log_target = config.get("use_log_target", False)
    smearing_factor = 1.0
    if use_log_target:
        residuals = y.values - result.predicted
        smearing_factor = float(np.mean(np.exp(residuals)))
        smearing_factor = max(smearing_factor, 1e-6)

    model_config_updates = {
        "model_type": result.model_type,
        "ridge_applied": result.ridge_applied,
        "ridge_alpha": result.ridge_alpha if result.ridge_applied else None,
        "lags_added": result.lags_added,
        "hac_applied": result.hac_applied,
        "log_transform_post_fit": result.log_transform_applied,
        "feature_names": list(result.X.columns),
        "use_log_target": use_log_target,
        "smearing_factor": smearing_factor,
    }
    if result.ridge_applied:
        try:
            alpha_comp_df = compare_alpha_objectives(result.X, result.y, spend_cols)
            model_config_updates["alpha_comparison"] = (
                alpha_comp_df.replace({np.nan: None}).to_dict(orient="records")
            )
        except Exception:
            model_config_updates["alpha_comparison"] = []
    model_config.update(model_config_updates)
    config_hash = hashlib.sha256(
        json.dumps(model_config, sort_keys=True).encode()
    ).hexdigest()

    model_config_with_hash = {
        **model_config,
        "config_hash": config_hash,
    }

    # Step 10 — Counterfactual
    incremental, marginal_roi = compute_counterfactual(
        result,
        spend_cols,
        use_log_target=use_log_target,
        smearing_factor=smearing_factor,
        df_weekly=df_weekly,
    )

    # Step 11 — Anomalies
    anomalies = detect_anomalies(result, df_weekly["week_start"])

    # Build OOS metrics for confidence and persist
    # Always include oos_n_obs, oos_split_ratio, oos_model_mode to distinguish
    # "no OOS window" vs "OOS window too small to evaluate"
    oos_metrics = {
        "oos_n_obs": n_oos,
        "oos_r2": r2_oos if n_oos >= 8 else None,
        "oos_rmse": rmse_oos if n_oos >= 8 else None,
        "oos_mae": mae_oos if n_oos >= 8 else None,
        "oos_split_ratio": 0.8,
        "oos_model_mode": model_mode_train,
    }

    # Step 12 — Confidence
    confidence = compute_confidence(result, n_obs, oos_metrics=oos_metrics)

    # For lag models: persist last N actuals for recursive forecast
    feature_state_to_persist = dict(feature_state) if feature_state else {}
    if result.lags_added > 0:
        last_actuals = list(result.y.values)[-result.lags_added:]
        feature_state_to_persist["lag_history"] = [
            float(y) for y in last_actuals
        ]

    # Step 13 — Persist
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
        raise HTTPException(
            status_code=500, detail=f"Failed to persist results: {e}"
        )

    # Temporary debug: OOS backtest metrics
    print("OOS observations:", n_oos)
    print("OOS R2:", r2_oos)
    print("OOS RMSE:", rmse_oos)
    print("OOS MAE:", mae_oos)

    # Step 14 — Response
    return RunModelResponse(
        model_type=result.model_type,
        lags_added=result.lags_added,
        log_transform=result.log_transform_applied,
        hac_applied=result.hac_applied,
        r2=round(result.r2, 6),
        adjusted_r2=round(result.adj_r2, 6),
        confidence_level=confidence,
        incremental_impact=incremental,
        marginal_roi=marginal_roi,
        anomaly_count=len(anomalies),
    )
