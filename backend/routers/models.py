"""POST /v1/projects/{project_id}/run — full deterministic modeling pipeline."""

import hashlib
import json

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

    # Step 2.75 — Diagnostics
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
    X, y = build_design_matrix(
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

    # Step 12 — Confidence
    confidence = compute_confidence(result, n_obs)

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
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to persist results: {e}"
        )

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
