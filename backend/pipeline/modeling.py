"""Steps 4–9 — Base OLS, decision tree (VIF, autocorrelation,
heteroskedasticity, nonlinearity), and final model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import Ridge
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson


@dataclass
class ModelResult:
    model_type: str  # "ols" | "ridge"
    model: Any
    X: pd.DataFrame
    y: pd.Series
    coefficients: pd.Series
    residuals: np.ndarray
    predicted: np.ndarray
    residual_std: float
    r2: float
    adj_r2: float
    ridge_applied: bool = False
    lags_added: int = 0
    log_transform_applied: bool = False
    hac_applied: bool = False
    vif_values: Dict[str, float] = field(default_factory=dict)
    dw_stat: float = 0.0
    ljung_box_p: float = 1.0
    breusch_pagan_p: float = 1.0


# ── Step 4: Base OLS ────────────────────────────────────────────────────────

def fit_ols(X: pd.DataFrame, y: pd.Series) -> ModelResult:
    model = sm.OLS(y, X).fit()
    resid = model.resid.values
    return ModelResult(
        model_type="ols",
        model=model,
        X=X,
        y=y,
        coefficients=model.params,
        residuals=resid,
        predicted=model.fittedvalues.values,
        residual_std=float(np.std(resid, ddof=1)),
        r2=float(model.rsquared),
        adj_r2=float(model.rsquared_adj),
    )


def fit_ridge(X: pd.DataFrame, y: pd.Series) -> ModelResult:
    X_no_const = X.drop(columns=["const"], errors="ignore")
    ridge = Ridge(alpha=1.0, fit_intercept=True)
    ridge.fit(X_no_const, y)

    predicted = ridge.predict(X_no_const)
    residuals = y.values - predicted
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y.values - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    n, p = X_no_const.shape
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2

    coefs = pd.Series(ridge.coef_, index=X_no_const.columns)
    coefs["const"] = float(ridge.intercept_)

    return ModelResult(
        model_type="ridge",
        model=ridge,
        X=X,
        y=y,
        coefficients=coefs,
        residuals=residuals,
        predicted=predicted,
        residual_std=float(np.std(residuals, ddof=1)),
        r2=r2,
        adj_r2=adj_r2,
        ridge_applied=True,
    )


# ── Step 5: VIF check ───────────────────────────────────────────────────────

def compute_vif(X: pd.DataFrame, spend_cols: list[str]) -> Dict[str, float]:
    if "const" in X.columns:
        X_no_const = X.drop(columns=["const"])
    else:
        X_no_const = X.copy()

    values = X_no_const.values
    vifs = {}

    for i, col in enumerate(X_no_const.columns):
        vif = float(variance_inflation_factor(values, i))
        if col in spend_cols:
            vifs[col] = round(vif, 4)

    return vifs


def check_vif(result: ModelResult, spend_cols: list[str]) -> ModelResult:
    vifs = compute_vif(result.X, spend_cols)
    result.vif_values = vifs
    if vifs and max(vifs.values()) > 10:
        ridge_result = fit_ridge(result.X, result.y)
        ridge_result.vif_values = vifs
        return ridge_result
    return result


# ── Step 6: Autocorrelation check ───────────────────────────────────────────

def _ljungbox_pvalue(residuals: np.ndarray, lags: int = 5) -> float:
    try:
        lb = acorr_ljungbox(residuals, lags=[lags], return_df=True)
        return float(lb["lb_pvalue"].iloc[0])
    except Exception:
        return 1.0


def _refit(X: pd.DataFrame, y: pd.Series, use_ridge: bool) -> ModelResult:
    if use_ridge:
        return fit_ridge(X, y)
    return fit_ols(X, y)


def check_autocorrelation(
    result: ModelResult, spend_cols: list[str]
) -> ModelResult:
    result.dw_stat = float(durbin_watson(result.residuals))
    result.ljung_box_p = _ljungbox_pvalue(result.residuals)
    use_ridge = result.ridge_applied

    if result.ljung_box_p >= 0.05:
        return result

    # Add lag 1
    X = result.X.copy()
    y = result.y.copy()
    X["lag_1"] = y.shift(1)
    mask = X["lag_1"].notna()
    X = X[mask].reset_index(drop=True)
    y = y[mask].reset_index(drop=True)

    new_result = _refit(X, y, use_ridge)
    new_result.lags_added = 1
    new_result.ridge_applied = use_ridge
    new_result.vif_values = result.vif_values
    new_result.dw_stat = float(durbin_watson(new_result.residuals))
    new_result.ljung_box_p = _ljungbox_pvalue(new_result.residuals)

    if new_result.ljung_box_p >= 0.05:
        return new_result

    # Add lag 2
    X2 = new_result.X.copy()
    y2 = new_result.y.copy()
    X2["lag_2"] = y2.shift(1)
    mask2 = X2["lag_2"].notna()
    X2 = X2[mask2].reset_index(drop=True)
    y2 = y2[mask2].reset_index(drop=True)

    new_result2 = _refit(X2, y2, use_ridge)
    new_result2.lags_added = 2
    new_result2.ridge_applied = use_ridge
    new_result2.vif_values = result.vif_values
    new_result2.dw_stat = float(durbin_watson(new_result2.residuals))
    new_result2.ljung_box_p = _ljungbox_pvalue(new_result2.residuals)

    if new_result2.ljung_box_p >= 0.05:
        return new_result2

    # Still significant — apply HAC (OLS only)
    if not use_ridge:
        hac_model = sm.OLS(y2, X2).fit(
            cov_type="HAC", cov_kwds={"maxlags": 1}
        )
        new_result2.model = hac_model
        new_result2.coefficients = hac_model.params
        new_result2.hac_applied = True

    return new_result2


# ── Step 7: Heteroskedasticity check ────────────────────────────────────────

def check_heteroskedasticity(result: ModelResult) -> ModelResult:
    if result.ridge_applied:
        return result

    try:
        _, p_val, _, _ = het_breuschpagan(result.residuals, result.X)
        result.breusch_pagan_p = float(p_val)
        if p_val < 0.05 and not result.hac_applied:
            hac_model = sm.OLS(result.y, result.X).fit(
                cov_type="HAC", cov_kwds={"maxlags": 1}
            )
            result.model = hac_model
            result.coefficients = hac_model.params
            result.hac_applied = True
    except Exception:
        pass
    return result


# ── Step 8: Nonlinearity check ──────────────────────────────────────────────

def check_nonlinearity(
    result: ModelResult, spend_cols: list[str]
) -> ModelResult:
    present = [c for c in spend_cols if c in result.X.columns]
    if not present:
        return result

    # Compare R² with log-transformed spend vs current
    X_log = result.X.copy()
    for col in present:
        X_log[col] = np.log1p(X_log[col])

    if result.ridge_applied:
        test = fit_ridge(X_log, result.y)
    else:
        test = fit_ols(X_log, result.y)

    if test.r2 > result.r2 + 0.01:
        test.log_transform_applied = True
        test.ridge_applied = result.ridge_applied
        test.lags_added = result.lags_added
        test.hac_applied = result.hac_applied
        test.vif_values = result.vif_values
        test.dw_stat = result.dw_stat
        return test

    return result


# ── Orchestrator: run full modeling pipeline ─────────────────────────────────

def run_model(
    X: pd.DataFrame, y: pd.Series, spend_cols: list[str]
) -> ModelResult:
    # Step 4: Base OLS
    result = fit_ols(X, y)

    # Step 5: VIF → maybe Ridge
    result = check_vif(result, spend_cols)

    # Step 6: Autocorrelation → maybe lags / HAC
    result = check_autocorrelation(result, spend_cols)

    # Step 7: Heteroskedasticity → maybe HAC
    result = check_heteroskedasticity(result)

    # Step 8: Nonlinearity → maybe log(spend)
    result = check_nonlinearity(result, spend_cols)

    # Step 9: Final model state is ready
    result.residual_std = float(np.std(result.residuals, ddof=1))
    return result
