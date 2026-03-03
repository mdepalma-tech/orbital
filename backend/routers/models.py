"""POST /v1/projects/{project_id}/run — full deterministic modeling pipeline."""

import hashlib
import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.responses import RunModelResponse
from pipeline.fetch import fetch_project_data
from pipeline.validate import validate_and_prepare, EPSILON
from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
from pipeline.diagnostics import run_diagnostics
from pipeline.matrix import build_design_matrix, get_model_config
from pipeline.modeling import run_model
from pipeline.counterfactual import compute_counterfactual
from pipeline.anomalies import detect_anomalies
from pipeline.confidence import compute_confidence
from pipeline.persist import persist_results
from pipeline.stream import stream_pipeline

router = APIRouter()


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
    X_train, y_train, feature_state = build_design_matrix(
        df_train,
        spend_cols,
        model_mode=model_mode_train,
    )
    result_train = run_model(X_train, y_train, spend_cols)

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

        ss_res = float(np.sum((y_test_vals - y_pred_test) ** 2))
        ss_tot = float(np.sum((y_test_vals - float(result_train.y.mean())) ** 2))
        r2_oos = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None
        rmse_oos = float(np.sqrt(np.mean((y_test_vals - y_pred_test) ** 2)))
        mae_oos = float(np.mean(np.abs(y_test_vals - y_pred_test)))

    # Step 2.75 — Diagnostics (production: full data)
    diagnostics = run_diagnostics(
        df_weekly,
        spend_cols,
        dropped_weekly_constant=dropped_weekly_constant,
    )
    model_mode = diagnostics["model_mode"]

    config = get_model_config(model_mode)
    model_config = {
        "model_mode": model_mode,
        "use_adstock": config["use_adstock"],
        "adstock_alpha": config["adstock_alpha"],
        "use_log_pre_fit": config["use_log"],
    }

    # Step 3 — Build design matrix
    X, y, _ = build_design_matrix(
        df_weekly,
        spend_cols,
        model_mode=model_mode,
        diagnostics=diagnostics,
    )

    # Steps 4–9 — Model fitting + decision tree
    result = run_model(X, y, spend_cols)

    model_config.update({
        "model_type": result.model_type,
        "ridge_applied": result.ridge_applied,
        "ridge_alpha": 1.0 if result.ridge_applied else None,
        "lags_added": result.lags_added,
        "hac_applied": result.hac_applied,
        "log_transform_post_fit": result.log_transform_applied,
    })
    config_hash = hashlib.sha256(
        json.dumps(model_config, sort_keys=True).encode()
    ).hexdigest()

    model_config_with_hash = {
        **model_config,
        "config_hash": config_hash,
    }

    # Step 10 — Counterfactual
    incremental, marginal_roi = compute_counterfactual(result, spend_cols)

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
