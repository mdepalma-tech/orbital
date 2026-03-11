"""Step 2.5 — Deterministic data diagnostics to select modeling track."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.signal import periodogram
from statsmodels.tsa.stattools import acf

# ---------------------------------------------------------------------------
# SEASONALITY SELECTION — THREE-STEP PROCESS
# ---------------------------------------------------------------------------
#
# We use three steps in sequence, where each step gates the next:
#
#   Step 1 — PERIODOGRAM: find the candidate period
#   Step 2 — ACF: confirm the candidate period is statistically real
#   Step 3 — AIC SWEEP: select how many Fourier harmonics (k) to use
#
# WHY THREE STEPS INSTEAD OF JUST AIC:
#
# AIC alone can select k > 0 even when the improvement is trivial (e.g. AIC
# drops by 1.2). The ACF test acts as a hard gate — if the series is not
# significantly autocorrelated at the candidate period, we skip the sweep
# entirely and set best_k=0. This prevents adding Fourier columns that
# compete with spend variables for variance they should not explain.
#
# WHY FOURIER TERMS (sin/cos) INSTEAD OF MONTH DUMMIES:
#
# Month dummies (12 binary columns) assume seasonality jumps sharply between
# months. Fourier terms model it as a smooth continuous wave, which is more
# realistic for most revenue patterns and uses far fewer degrees of freedom.
# k=1 captures one broad annual wave. k=2 adds a faster wave on top of it,
# allowing the model to represent asymmetric or double-peaked seasonal shapes.
#
# WHY RAW REVENUE (not log) FOR THE SWEEP:
#
# The AIC sweep detects the shape of seasonality in the raw signal.
# The log transform in matrix.py is about stabilising variance for regression,
# not about seasonality detection — applying it here would distort peak
# amplitudes and could mask or exaggerate patterns.


# Minimum AIC improvement over k=0 to justify adding Fourier terms.
# From information theory: AIC difference < 2 means models are essentially
# equivalent. We use 2.0 as the threshold to avoid adding columns for
# marginal gains.
_MIN_AIC_IMPROVEMENT = 10.0

# ACF confidence band multiplier. The standard 95% band is 2/sqrt(n).
# Any ACF value beyond this threshold is statistically significant.
_ACF_CONFIDENCE_MULTIPLIER = 2.0

def _candidate_period(y: pd.Series) -> int:
    freqs, power = periodogram(y.values)

    #skip index 0(DC component/zero frequency)
    peak_idx = int(np.argmax(power[1:])) + 1
    dominant_freq = freqs[peak_idx]

    if dominant_freq > 0:
        period = round(1.0 / dominant_freq)
        # Sanity bounds: at least monthly (4w), at most 2 years (104w)
        if 4 <= period <= 104:
            return int(period)

    return 52  # default for weekly data

def _acf_confirms_period(y: pd.Series, period: int) -> bool:
    """
    STEP 2 — ACF: confirm the candidate period is statistically significant.

    The ACF (autocorrelation function) measures how correlated the series is
    with a lagged version of itself. A spike at lag=period means the series
    reliably repeats every `period` weeks — genuine seasonality.

    The 95% confidence band for ACF is 2/sqrt(n). Any value beyond this is
    statistically significant at the 5% level. Values inside the band could
    plausibly be noise.

    We compute ACF up to period + 4 lags (a small buffer) to ensure we
    capture the lag of interest without requesting an excessive number of lags.

    Returns True if seasonality at this period is confirmed, False otherwise.
    """
    n = len(y)
    # Need enough observations to compute ACF at this lag reliably
    if n < period + 4:
        return False

    acf_values = acf(y.values, nlags=period + 4, fft=True)

    # Standard 95% confidence threshold: 2 / sqrt(n)
    threshold = _ACF_CONFIDENCE_MULTIPLIER / np.sqrt(n)
    acf_at_period = abs(acf_values[period])

    return bool(acf_at_period > threshold)

def _select_fourier_order(
    y: pd.Series,
    period: int,
    max_k: int = 4,
) -> Dict:
    """
    STEP 3 — AIC SWEEP: given a confirmed period, select how many Fourier
    harmonics (k) best capture the seasonal shape.

    Fits OLS(revenue ~ trend + Fourier terms) for k=0..max_k and picks the
    k with the lowest AIC, subject to a minimum improvement threshold.

    AIC = n * ln(RSS/n) + 2p
      - RSS: residual sum of squares (fit quality)
      - p:   number of parameters (complexity penalty)

    Each additional k adds 2 parameters (sin + cos). AIC only rewards adding
    them if the RSS reduction is large enough to outweigh the penalty.

    We walk forward k=1..max_k and accept each k only if the marginal AIC gain
    from the previous k meets _MIN_AIC_IMPROVEMENT (10.0). We stop at the first
    k whose marginal gain is below the threshold. This prevents accepting higher
    harmonics that only add a trivial improvement over the previous k.

    Args:
        y:      Revenue series (raw, not log-transformed).
        period: Confirmed seasonal period in weeks.
        max_k:  Maximum harmonics to consider (default 4).

    Returns:
        {
            "best_k": int,        # 0 = no seasonality; >0 = harmonics to use
            "aic_by_k": dict,     # full AIC table for transparency
            "strength": float,    # total AIC improvement from k=0 to best_k
        }
    """
    t = np.arange(len(y))
    aic_by_k = {}

    for k in range(0, max_k + 1):
        # k=0: just trend (intercept + t), no Fourier terms
        # k=1: trend + sin(2πt/P) + cos(2πt/P)
        # k=2: above + sin(4πt/P) + cos(4πt/P)  ... and so on
        cols = [t]
        for i in range(1, k + 1):
            cols.append(np.sin(2 * np.pi * i * t / period))
            cols.append(np.cos(2 * np.pi * i * t / period))

        X = sm.add_constant(np.column_stack(cols))
        model = sm.OLS(y.values, X).fit()
        aic_by_k[k] = round(float(model.aic), 4)

    # Walk forward and accept each k only if the marginal AIC gain
    # from the previous k meets the minimum threshold.
    # Stop as soon as a step fails — no point checking higher k.
    best_k = 0
    for k in range(1, max_k + 1):
        marginal_gain = aic_by_k[k - 1] - aic_by_k[k]
        if marginal_gain >= _MIN_AIC_IMPROVEMENT:
            best_k = k
        else:
            break

    # Apply minimum improvement threshold.
    # If total AIC gain is trivial, treat as no seasonality needed.
    aic_improvement = aic_by_k[0] - aic_by_k[best_k]

    return {
        "best_k": best_k,
        "aic_by_k": aic_by_k,
        "strength": round(float(aic_improvement), 4),
    }

def _detect_seasonality(y: pd.Series) -> Dict:
    period = _candidate_period(y)
    confirmed = _acf_confirms_period(y, period)
    if not confirmed:
        # ACF gate failed — period is not statistically significant.
        # Return best_k=0: no Fourier terms will be added to X.
        return {
            "best_k": 0,
            "aic_by_k": {},
            "strength": 0.0,
            "dominant_period": period,
            "acf_confirmed": False,
        }

    # ACF confirmed — run AIC sweep at the validated period
    result = _select_fourier_order(y, period=period, max_k=4)

    return {
        **result,
        "dominant_period": period,
        "acf_confirmed": True,
    }


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
        sub = df_weekly[spend_cols].astype(float)
        corr = sub.corr()
        if corr.shape[0] > 1:
            i_upper, j_upper = np.triu_indices(corr.shape[0], k=1)
            vals = corr.values[i_upper, j_upper]
            vals = np.abs(np.asarray(vals, dtype=float))
            vals = vals[np.isfinite(vals)]
            if len(vals) > 0:
                max_corr = float(np.max(vals))

    if n_obs >= 104:
        seasonality_result = _detect_seasonality(revenue)
    else:
        seasonality_result = {
            "best_k": 1,
            "aic_by_k": {},
            "strength": 0.0,
            "dominant_period": 52,
            "acf_confirmed": False,
        }

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
        "seasonality": seasonality_result,
        "gating_reasons": reasons
    }
