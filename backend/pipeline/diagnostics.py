"""Step 2.5 — Deterministic data diagnostics to select modeling track."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def run_diagnostics(
    df_weekly: pd.DataFrame,
    spend_cols: List[str],
    dropped_weekly_constant: List[str] | None = None,
) -> Dict:
    """
    Computes deterministic diagnostics used to select modeling track.

    Args:
        df_weekly: DataFrame with at least a 'revenue' column and any spend columns.
        spend_cols: Explicit list of spend column names present in df_weekly.

    Returns:
    {
        "snapshot": {...},
        "score": int,
        "model_mode": "causal_full" | "causal_cautious" | "diagnostic_stabilized",
        "data_confidence_band": "High" | "Moderate" | "Low",
        "gating_reasons": [...]
    }
    """

    n_obs = len(df_weekly)

    revenue = df_weekly["revenue"]
    total_spend = df_weekly[spend_cols].sum(axis=1) if spend_cols else pd.Series(0, index=df_weekly.index)

    # Spend diagnostics (flightable / zero-heavy aware)
    n_zero_weeks = int((total_spend == 0).sum())
    zero_share = float(n_zero_weeks / n_obs) if n_obs > 0 else 0.0
    n_active_weeks = int((total_spend > 0).sum())
    active_spend = total_spend[total_spend > 0]
    if n_active_weeks < 4:
        cv_active = 0.0
    else:
        mean_active = active_spend.mean()
        std_active = active_spend.std(ddof=1)
        if abs(mean_active) > 1e-8:
            cv_active = float(std_active / mean_active)
        else:
            cv_active = 0.0
    # Legacy metric kept for transparency; not used for scoring
    mean_spend = total_spend.mean()
    std_spend = total_spend.std(ddof=1)
    if abs(mean_spend) > 1e-8:
        cv_spend_total = float(std_spend / mean_spend)
    else:
        cv_spend_total = 0.0

    # Structured revenue signal proxy (rolling-based SNR)
    if n_obs >= 12:
        # 4-week rolling mean captures medium-term structure
        rolling = revenue.rolling(window=4, min_periods=4).mean()
        residual = revenue - rolling

        signal_series = rolling.dropna()
        residual_series = residual.loc[signal_series.index]

        signal_var = float(np.var(signal_series, ddof=1))
        noise_var = float(np.var(residual_series, ddof=1))

        if len(signal_series) >= 4 and noise_var > 1e-8:
            snr = signal_var / noise_var
        else:
            snr = 0.0
    else:
        snr = 0.0

    # Pairwise correlation (kept for explainability; not used for scoring)
    max_corr = 0.0
    if len(spend_cols) > 1:
        corr = df_weekly[spend_cols].corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        vals = upper.stack().values
        if len(vals) > 0:
            max_corr = float(vals.max())

    # Data Sufficiency Score (0–100, smooth additive)
    # 1. Historical depth: full credit at >= 104 weeks
    depth_score = min(n_obs / 104.0, 1.0) * 25.0

    # 2. Coverage: full credit if >= 60% of weeks have active spend
    coverage_ratio = n_active_weeks / n_obs if n_obs > 0 else 0.0
    coverage_score = min(coverage_ratio / 0.6, 1.0) * 20.0

    # 3. Inactivity: linear penalty
    inactivity_score = max(0.0, 10.0 * (1.0 - zero_share))

    # 4. Active CV: full credit at CV >= 0.3
    cv_score = min(cv_active / 0.3, 1.0) * 20.0

    # 5. SNR: log scaling, full credit at SNR ~ 2.0
    snr_score = min(np.log1p(snr) / np.log1p(2.0), 1.0) * 25.0

    total_score = depth_score + coverage_score + inactivity_score + cv_score + snr_score
    score = int(round(total_score))
    score = max(0, min(100, score))

    # Gating reasons (structural failures)
    reasons = []
    if n_obs < 80:
        reasons.append("Limited historical depth")
    if n_active_weeks < 12:
        reasons.append("Limited active spend coverage")
    if zero_share > 0.6:
        reasons.append("Spend frequently inactive")
    if cv_active < 0.12:
        reasons.append("Low active spend variability")
    if snr < 0.9:
        reasons.append("Low signal-to-noise")
    if dropped_weekly_constant:
        reasons.append(
            f"Removed weekly-constant spend channels: {', '.join(dropped_weekly_constant)}"
        )

    if cv_active < 0.12:
        model_mode = "diagnostic_stabilized"
    elif score >= 70:
        model_mode = "causal_full"
    elif score >= 55:
        model_mode = "causal_cautious"
    else:
        model_mode = "diagnostic_stabilized"

    if score >= 75:
        data_confidence = "High"
    elif score >= 55:
        data_confidence = "Moderate"
    else:
        data_confidence = "Low"

    def _safe_round(x, decimals=4):
        v = round(x, decimals)
        return v if np.isfinite(v) else 0.0

    snapshot = {
        "n_obs": n_obs,
        "cv_spend_total": _safe_round(cv_spend_total, 4),
        "zero_share": _safe_round(zero_share, 4),
        "n_active_weeks": n_active_weeks,
        "cv_active": _safe_round(cv_active, 4),
        "snr": _safe_round(snr, 4),
        "max_pairwise_corr": _safe_round(max_corr, 4),
        "depth_score": _safe_round(depth_score, 2),
        "coverage_score": _safe_round(coverage_score, 2),
        "inactivity_score": _safe_round(inactivity_score, 2),
        "cv_score": _safe_round(cv_score, 2),
        "snr_score": _safe_round(snr_score, 2),
    }

    return {
        "snapshot": snapshot,
        "score": score,
        "model_mode": model_mode,
        "data_confidence_band": data_confidence,
        "gating_reasons": reasons,
    }
