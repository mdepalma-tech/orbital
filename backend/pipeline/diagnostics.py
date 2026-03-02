"""Step 2.5 — Deterministic data diagnostics to select modeling track."""

from typing import Dict, List

import numpy as np
import pandas as pd


def run_diagnostics(df_weekly: pd.DataFrame, spend_cols: List[str]) -> Dict:
    """
    Computes deterministic diagnostics used to select modeling track.

    Args:
        df_weekly: DataFrame with at least a 'revenue' column and any spend columns.
        spend_cols: Explicit list of spend column names present in df_weekly.

    Returns:
    {
        "snapshot": {...},
        "score": int,
        "model_mode": "causal_full" | "diagnostic_stabilized",
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

    # Pairwise correlation
    max_corr = 0
    if len(spend_cols) > 1:
        corr = df_weekly[spend_cols].astype(float).corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        vals = upper.stack().values
        if len(vals) > 0:
            max_corr = float(np.nanmax(vals))

    score = 0
    reasons = []

    if n_obs >= 120: score += 20
    elif n_obs >= 80: score += 10
    else: reasons.append("Limited historical depth")

    # Spend identifiability scoring (smooth additive; total max = 20 points)

    # --- 1. Coverage score (0–10 points) ---
    # Full credit at >= 20 active weeks
    coverage_score = min(n_active_weeks / 20.0, 1.0) * 10.0
    score += coverage_score

    if n_active_weeks < 12:
        reasons.append("Limited active spend coverage")

    # --- 2. Inactivity score (0–5 points) ---
    # Full credit if zero_share <= 0.4
    # Linearly declines to 0 at zero_share = 1.0
    if zero_share <= 0.4:
        inactivity_score = 5.0
    else:
        inactivity_score = max(0.0, 5.0 * (1.0 - (zero_share - 0.4) / 0.6))

    score += inactivity_score

    if zero_share > 0.6:
        reasons.append("Spend frequently inactive")

    # --- 3. Active CV score (0–5 points) ---
    if cv_active >= 0.25:
        cv_score = 5.0
    elif cv_active >= 0.15:
        cv_score = 2.5
    else:
        cv_score = 0.0
        reasons.append("Low active spend variability")

    score += cv_score

    if snr >= 1.2: score += 20
    elif snr >= 0.9: score += 10
    else: reasons.append("Low signal-to-noise")

    if max_corr <= 0.85: score += 20
    else: reasons.append("High channel collinearity")

    score = max(0, int(round(score)))

    if score >= 60:
        model_mode = "causal_full"
    else:
        model_mode = "diagnostic_stabilized"

    if score >= 65:
        data_confidence = "High"
    elif score >= 50:
        data_confidence = "Moderate"
    else:
        data_confidence = "Low"

    snapshot = {
        "n_obs": n_obs,
        "cv_spend_total": round(cv_spend_total, 4),
        "zero_share": round(zero_share, 4),
        "n_active_weeks": n_active_weeks,
        "cv_active": round(cv_active, 4),
        "snr": round(snr, 4),
        "max_pairwise_corr": round(max_corr, 4),
    }

    return {
        "snapshot": snapshot,
        "score": score,
        "model_mode": model_mode,
        "data_confidence_band": data_confidence,
        "gating_reasons": reasons,
    }
