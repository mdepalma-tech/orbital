"""Step 13 — Persist model results to Supabase."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List

logger = logging.getLogger(__name__)

import numpy as np
from services.supabase_client import get_supabase
from pipeline.modeling import ModelResult


def _to_native(val):
    """Coerce numpy types to native Python for JSONB compatibility."""
    if hasattr(val, "item"):
        return val.item()
    if isinstance(val, dict):
        return {k: _to_native(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_native(v) for v in val]
    return val


def _correlation_matrix(X, spend_cols: list[str]) -> dict:
    cols = [c for c in spend_cols if c in X.columns]
    if not cols:
        return {}
    corr = X[cols].corr()
    return {
        row: {col: round(float(corr.loc[row, col]), 6) for col in corr.columns}
        for row in corr.index
    }


def persist_results(
    project_id: str,
    result: ModelResult,
    spend_cols: list[str],
    incremental: Dict[str, float],
    marginal_roi: Dict[str, float],
    anomalies: List[Dict],
    confidence_level: str,
    n_obs: int,
    diagnostics: Dict | None = None,
    model_config: Dict | None = None,
    config_hash: str | None = None,
    oos_metrics: Dict | None = None,
    feature_state: Dict | None = None,
) -> str:
    logger.info("persist_results called for project_id=%s", project_id)
    sb = get_supabase()

    # ── models ───────────────────────────────────────────────────────────
    existing = (
        sb.table("models")
        .select("id")
        .eq("project_id", project_id)
        .execute()
    )
    if existing.data:
        model_id = existing.data[0]["id"]
    else:
        model_id = str(uuid.uuid4())
        sb.table("models").insert(
            {
                "id": model_id,
                "project_id": project_id,
                "name": "Revenue Model",
                "target_metric": "revenue",
            }
        ).execute()

    # ── model_versions ───────────────────────────────────────────────────
    version_id = str(uuid.uuid4())
    version_row = {
        "id": version_id,
        "model_id": model_id,
        "model_type": result.model_type,
        "modeling_frequency": "weekly",
        "log_transform": result.log_transform_applied,
        "lags_added": result.lags_added,
        "ridge_applied": result.ridge_applied,
        "hac_applied": result.hac_applied,
        "r2": round(result.r2, 6),
        "adjusted_r2": round(result.adj_r2, 6),
        "confidence_level": confidence_level,
    }
    if config_hash is not None:
        version_row["config_hash"] = config_hash
    if model_config is not None:
        version_row["model_config"] = json.dumps(model_config)
    if feature_state is not None:
        version_row["feature_state"] = _to_native(feature_state)

    if diagnostics:
        version_row["data_strength_score"] = diagnostics["score"]
        version_row["model_mode"] = diagnostics["model_mode"]
        version_row["confidence_band"] = diagnostics["data_confidence_band"]
        version_row["diagnostics_snapshot"] = json.dumps(diagnostics["snapshot"])
        version_row["gating_reasons"] = json.dumps(diagnostics["gating_reasons"])

    if oos_metrics is not None:
        # Coerce to native Python types for JSON/PostgREST compatibility
        oos_n = oos_metrics.get("oos_n_obs")
        version_row["oos_n_obs"] = int(oos_n) if oos_n is not None else None
        oos_r2 = oos_metrics.get("oos_r2")
        version_row["oos_r2"] = round(float(oos_r2), 6) if oos_r2 is not None else None
        oos_rmse = oos_metrics.get("oos_rmse")
        version_row["oos_rmse"] = round(float(oos_rmse), 6) if oos_rmse is not None else None
        oos_mae = oos_metrics.get("oos_mae")
        version_row["oos_mae"] = round(float(oos_mae), 6) if oos_mae is not None else None
        oos_ratio = oos_metrics.get("oos_split_ratio")
        version_row["oos_split_ratio"] = float(oos_ratio) if oos_ratio is not None else None
        oos_mode = oos_metrics.get("oos_model_mode")
        version_row["oos_model_mode"] = str(oos_mode) if oos_mode is not None else None
        logger.info(
            "Persisting OOS metrics: oos_n_obs=%s oos_r2=%s oos_rmse=%s oos_mae=%s",
            version_row.get("oos_n_obs"),
            version_row.get("oos_r2"),
            version_row.get("oos_rmse"),
            version_row.get("oos_mae"),
        )

    sb.table("model_versions").insert(version_row).execute()

    # ── model_coefficients ───────────────────────────────────────────────
    coeff_rows = []
    for name, value in result.coefficients.items():
        p_val = None
        std_err = None
        if not result.ridge_applied and hasattr(result.model, "pvalues"):
            if name in result.model.pvalues.index:
                p_val = round(float(result.model.pvalues[name]), 8)
            if name in result.model.bse.index:
                std_err = round(float(result.model.bse[name]), 8)

        coeff_rows.append(
            {
                "model_version_id": version_id,
                "feature_name": str(name),
                "coefficient": round(float(value), 8),
                "p_value": p_val,
                "std_error": std_err,
            }
        )

    if coeff_rows:
        sb.table("model_coefficients").insert(coeff_rows).execute()

    # ── model_diagnostics ────────────────────────────────────────────────
    max_vif = round(max(result.vif_values.values()), 4) if result.vif_values else None
    corr_matrix = _correlation_matrix(result.X, spend_cols)

    sb.table("model_diagnostics").insert(
        {
            "model_version_id": version_id,
            "max_vif": max_vif,
            "ljung_box_p": round(result.ljung_box_p, 8),
            "breusch_pagan_p": round(result.breusch_pagan_p, 8),
            "durbin_watson": round(result.dw_stat, 6),
            "residual_std": round(result.residual_std, 6),
            "correlation_matrix": json.dumps(corr_matrix),
        }
    ).execute()

    # ── model_anomalies ──────────────────────────────────────────────────
    if anomalies:
        anomaly_rows = [
            {
                "model_version_id": version_id,
                "ts": a["ts"],
                "actual_value": a["actual"],
                "predicted_value": a["predicted"],
                "residual": a["residual"],
                "z_score": a["z_score"],
                "direction": a["direction"],
            }
            for a in anomalies
        ]
        sb.table("model_anomalies").insert(anomaly_rows).execute()

    return version_id
