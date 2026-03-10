"""Steps 4–9 — Base OLS, decision tree (VIF, autocorrelation,
heteroskedasticity, nonlinearity), and final model."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

logger = logging.getLogger(__name__)


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
    ridge_alpha: float = 0.0
    lags_added: int = 0
    log_transform_applied: bool = False
    hac_applied: bool = False
    vif_values: Dict[str, float] = field(default_factory=dict)
    dw_stat: float = 0.0
    ljung_box_p: float = 1.0
    breusch_pagan_p: float = 1.0


# ── Step 4: Base OLS ────────────────────────────────────────────────────────

def _check_rank(X: pd.DataFrame) -> pd.DataFrame:
    """Drop rank-deficient columns and warn. Returns cleaned X."""
    rank = np.linalg.matrix_rank(X.values)
    if rank >= X.shape[1]:
        return X
    # Greedy forward selection: add columns while they increase rank
    keep_cols: list[str] = []
    for col in X.columns:
        candidate = keep_cols + [col]
        if np.linalg.matrix_rank(X[candidate].values) > len(keep_cols):
            keep_cols.append(col)
        if len(keep_cols) == rank:
            break
    drop_cols = [c for c in X.columns if c not in keep_cols]
    logger.warning(
        "Design matrix is rank-deficient (rank %d < %d columns). "
        "Dropping redundant columns: %s",
        rank, X.shape[1], drop_cols,
    )
    return X[keep_cols]


def fit_ols(X: pd.DataFrame, y: pd.Series) -> ModelResult:
    X = _check_rank(X)
    try:
        model = sm.OLS(y, X).fit()
    except (np.linalg.LinAlgError, ValueError) as exc:
        logger.warning("OLS fit failed (%s), falling back to Ridge", exc)
        return fit_ridge(X, y)
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


_RIDGE_ALPHAS = np.logspace(-2, 4, 50)  # 0.01 → 10 000
_RIDGE_N_SPLITS = 3


def _select_alpha_tscv(
    X: np.ndarray, y: np.ndarray, alphas: np.ndarray, n_splits: int
) -> float:
    """Select Ridge alpha via TimeSeriesSplit CV (respects temporal order)."""
    n = len(y)
    min_train = X.shape[1] + 1  # need at least p+1 obs to fit
    if n < min_train * (n_splits + 1):
        # Not enough data for time-series CV — fall back to middle of grid
        logger.warning(
            "Insufficient data for TimeSeriesSplit alpha selection (n=%d, splits=%d). "
            "Using median alpha from grid.",
            n, n_splits,
        )
        return float(alphas[len(alphas) // 2])

    tscv = TimeSeriesSplit(n_splits=n_splits)
    best_alpha = alphas[0]
    best_mse = float("inf")

    for alpha in alphas:
        ridge = Ridge(alpha=alpha, fit_intercept=True)
        scores = cross_val_score(
            ridge, X, y, cv=tscv, scoring="neg_mean_squared_error"
        )
        mse = -float(np.mean(scores))
        if mse < best_mse:
            best_mse = mse
            best_alpha = alpha

    return float(best_alpha)


def fit_ridge(X: pd.DataFrame, y: pd.Series) -> ModelResult:
    X_no_const = X.drop(columns=["const"], errors="ignore")
    if X_no_const.shape[1] == 0:
        raise ValueError(
            "Design matrix has no feature columns after dropping const. "
            "Check that at least one spend or control variable is present."
        )

    # Standardize features so alpha operates on a normalized scale.
    # Without this, channels with large absolute values (e.g. $500K spend)
    # receive less relative shrinkage than channels with small values.
    X_raw = X_no_const.values
    col_means = X_raw.mean(axis=0)
    col_stds = X_raw.std(axis=0)
    col_stds[col_stds == 0] = 1.0  # avoid division by zero for constant cols
    X_scaled = (X_raw - col_means) / col_stds

    y_vals = y.values
    y_mean = float(y_vals.mean())
    y_std = float(y_vals.std())
    if y_std == 0:
        y_std = 1.0
    y_scaled = (y_vals - y_mean) / y_std

    try:
        best_alpha = _select_alpha_tscv(
            X_scaled, y_scaled, _RIDGE_ALPHAS, _RIDGE_N_SPLITS
        )
    except (np.linalg.LinAlgError, ValueError) as exc:
        raise ValueError(
            f"Ridge alpha selection failed on a degenerate design matrix: {exc}. "
            "Check for duplicate or all-zero columns."
        ) from exc

    # Fit on standardized data
    ridge_scaled = Ridge(alpha=best_alpha, fit_intercept=True)
    ridge_scaled.fit(X_scaled, y_scaled)
    logger.info("Ridge alpha selected: %.4f via TimeSeriesSplit(n_splits=%d)", best_alpha, _RIDGE_N_SPLITS)

    # Un-standardize coefficients back to original scale:
    #   β_orig = (y_std / x_std) * β_scaled
    #   intercept_orig = y_mean + y_std * β0_scaled - Σ(β_orig * x_mean)
    coef_orig = (y_std / col_stds) * ridge_scaled.coef_
    intercept_orig = y_mean + y_std * ridge_scaled.intercept_ - float(np.dot(coef_orig, col_means))

    # Refit a Ridge on original scale with the selected alpha so the stored
    # model object produces correct predictions on raw (unscaled) features.
    ridge = Ridge(alpha=best_alpha, fit_intercept=True)
    ridge.fit(X_no_const, y)
    # Override with the properly un-standardized coefficients
    ridge.coef_ = coef_orig
    ridge.intercept_ = intercept_orig

    predicted = ridge.predict(X_no_const.values)
    residuals = y_vals - predicted
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y_vals - y_vals.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    n, p = X_no_const.shape
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2

    coefs = pd.Series(coef_orig, index=X_no_const.columns)
    coefs["const"] = intercept_orig

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
        ridge_alpha=best_alpha,
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
        try:
            vif = float(variance_inflation_factor(values, i))
        except (np.linalg.LinAlgError, ValueError):
            vif = float("inf")
        if not np.isfinite(vif):
            logger.warning("VIF for '%s' is non-finite (inf/nan) — perfect collinearity likely", col)
            vif = float("inf")
        if col in spend_cols:
            vifs[col] = round(vif, 4) if np.isfinite(vif) else float("inf")

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

    # Add lag 1: lag_1 = y_{t-1}, preserve original index
    X = result.X.copy()
    y = result.y.copy()
    X["lag_1"] = y.shift(1)
    mask = X["lag_1"].notna()
    X = X.loc[mask]
    y = y.loc[mask]

    new_result = _refit(X, y, use_ridge)
    new_result.lags_added = 1
    new_result.ridge_applied = use_ridge
    new_result.vif_values = result.vif_values
    new_result.dw_stat = float(durbin_watson(new_result.residuals))
    new_result.ljung_box_p = _ljungbox_pvalue(new_result.residuals)

    if new_result.ljung_box_p >= 0.05:
        return new_result

    # Add lag 2: lag_2 = y_{t-2} (use original result.y)
    X2 = new_result.X.copy()
    y2 = new_result.y.copy()
    X2["lag_2"] = result.y.shift(2)
    mask2 = X2[["lag_1", "lag_2"]].notna().all(axis=1)
    X2 = X2.loc[mask2]
    y2 = y2.loc[mask2]

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
        new_result2.predicted = hac_model.fittedvalues.values
        new_result2.residuals = hac_model.resid.values
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
            result.predicted = hac_model.fittedvalues.values
            result.residuals = hac_model.resid.values
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
        # If HAC was applied to current model, refit log model with HAC for consistent p-values/bse
        if result.hac_applied and not result.ridge_applied:
            hac_model = sm.OLS(test.y, test.X).fit(
                cov_type="HAC", cov_kwds={"maxlags": 1}
            )
            test.model = hac_model
            test.coefficients = hac_model.params
            test.predicted = hac_model.fittedvalues.values
            test.residuals = hac_model.resid.values
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
