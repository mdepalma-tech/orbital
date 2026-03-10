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
    stability_threshold: float = 0.0
    lags_added: int = 0
    log_transform_applied: bool = False
    log_target_applied: bool = False
    dollar_r2: float = 0.0
    dollar_adj_r2: float = 0.0
    hac_applied: bool = False
    vif_values: Dict[str, float] = field(default_factory=dict)
    dw_stat: float = 0.0
    ljung_box_p: float = 1.0
    breusch_pagan_p: float = 1.0
    negative_spend_cols: list = field(default_factory=list)


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


def fit_ols(X: pd.DataFrame, y: pd.Series, spend_cols: list[str] | None = None) -> ModelResult:
    X = _check_rank(X)
    try:
        model = sm.OLS(y, X).fit()
    except (np.linalg.LinAlgError, ValueError) as exc:
        logger.warning("OLS fit failed (%s), falling back to Ridge", exc)
        return fit_ridge(X, y, spend_cols=spend_cols)
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


_RIDGE_ALPHAS = np.logspace(-2, 4, 200)  # 0.01 → 10 000
_RIDGE_N_SPLITS = 3
_STABILITY_THRESHOLD = 0.01


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


def _select_alpha_stability(
    X_scaled: np.ndarray,
    y: np.ndarray,
    alphas: np.ndarray,
    spend_indices: list[int] = None,
) -> float:
    n_alphas = len(alphas)
    n_features = X_scaled.shape[1]
    coef_matrix = np.empty((n_alphas, n_features))

    for i, a in enumerate(alphas):
        ridge = Ridge(alpha=a, fit_intercept=True)
        ridge.fit(X_scaled, y)
        coef_matrix[i] = ridge.coef_

    # 1. Enforce non-negativity (business logic)
    valid_mask = np.ones(n_alphas, dtype=bool)
    if spend_indices:
        for i in range(n_alphas):
            if np.any(coef_matrix[i, spend_indices] < -1e-4):
                valid_mask[i] = False

    # 2. Check stability (rate of change)
    col_ranges = coef_matrix.max(axis=0) - coef_matrix.min(axis=0)
    col_ranges[col_ranges == 0] = 1.0
    coef_norm = coef_matrix / col_ranges
    deltas = np.abs(np.diff(coef_norm, axis=0))
    max_delta = deltas.max(axis=1)

    # 3. Find the lowest alpha that is BOTH valid and stable
    for i in range(n_alphas - 1):
        if valid_mask[i + 1] and max_delta[i] < _STABILITY_THRESHOLD:
            selected = float(alphas[i + 1])
            logger.info("Stability alpha selected: %.4f (valid and stable)", selected)
            return selected

    # 4. Fallback 1: pick the lowest valid alpha
    valid_indices = np.where(valid_mask)[0]
    if len(valid_indices) > 0:
        selected = float(alphas[valid_indices[0]])
        logger.warning("No alpha stabilized. Falling back to first valid alpha: %.4f", selected)
        return selected

    # 5. Fallback 2: return max alpha
    selected = float(alphas[-1])
    logger.warning("Ridge could not force positive spend coefficients. Using max alpha: %.4f", selected)
    return selected


def fit_ridge(X: pd.DataFrame, y: pd.Series, spend_cols: list[str] | None = None) -> ModelResult:
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
    col_stds[col_stds == 0] = 1.0
    X_scaled = (X_raw - col_means) / col_stds

    y_vals = y.values

    spend_indices: list[int] | None = None
    if spend_cols:
        col_list = list(X_no_const.columns)
        spend_indices = [col_list.index(c) for c in spend_cols if c in col_list]
        if not spend_indices:
            spend_indices = None

    try:
        best_alpha = _select_alpha_stability(X_scaled, y_vals, _RIDGE_ALPHAS, spend_indices)
    except (np.linalg.LinAlgError, ValueError) as exc:
        raise ValueError(
            f"Ridge alpha selection failed on a degenerate design matrix: {exc}. "
            "Check for duplicate or all-zero columns."
        ) from exc

    # Fit on standardized X with raw y
    ridge_scaled = Ridge(alpha=best_alpha, fit_intercept=True)
    ridge_scaled.fit(X_scaled, y_vals)
    logger.info("Ridge alpha selected: %.4f via stability (threshold=%.4f)", best_alpha, _STABILITY_THRESHOLD)

    # Un-standardize coefficients back to original scale:
    #   β_orig = (1 / x_std) * β_scaled
    #   intercept_orig = β0_scaled - Σ(β_orig * x_mean)
    coef_orig = (1.0 / col_stds) * ridge_scaled.coef_
    intercept_orig = float(ridge_scaled.intercept_) - float(np.dot(coef_orig, col_means))

    # Construct a Ridge object that predicts on raw (unscaled) features
    # without a redundant .fit() call.
    ridge = Ridge(alpha=best_alpha, fit_intercept=True)
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
        stability_threshold=_STABILITY_THRESHOLD,
    )


def compare_alpha_objectives(
    X: pd.DataFrame, y: pd.Series, spend_cols: list[str]
) -> pd.DataFrame:
    """Compare prediction-optimal vs attribution-stable Ridge alpha side by side.

    Selects two alphas — one minimising holdout MSE (prediction objective) and
    one maximising coefficient stability (attribution objective) — then fits
    both and reports R², adjusted R², holdout MSE, and per-channel coefficients
    for each.  This lets the analyst judge whether the stability alpha degrades
    predictive quality materially.

    Args:
        X:          Design matrix (may include a ``const`` column, which is
                    dropped internally).
        y:          Target vector in original units.
        spend_cols: Column names of the spend channels whose coefficients
                    appear as individual columns in the output.

    Returns:
        DataFrame with one row per objective and columns ``objective``,
        ``alpha``, ``r2``, ``adj_r2``, ``holdout_mse``, plus one column per
        spend channel containing the un-standardised coefficient.
    """
    X_no_const = X.drop(columns=["const"], errors="ignore")
    X_raw = X_no_const.values
    col_means = X_raw.mean(axis=0)
    col_stds = X_raw.std(axis=0)
    col_stds[col_stds == 0] = 1.0
    X_scaled = (X_raw - col_means) / col_stds
    y_vals = y.values

    col_list = list(X_no_const.columns)
    spend_indices = [col_list.index(c) for c in spend_cols if c in col_list] or None

    alpha_pred = _select_alpha_tscv(X_scaled, y_vals, _RIDGE_ALPHAS, _RIDGE_N_SPLITS)
    alpha_attr = _select_alpha_stability(X_scaled, y_vals, _RIDGE_ALPHAS, spend_indices)
    logger.info(
        "compare_alpha_objectives: alpha_pred=%.4f  alpha_attr=%.4f",
        alpha_pred, alpha_attr,
    )

    rows: list[dict] = []
    for label, alpha in [("prediction_mse", alpha_pred), ("attribution_stability", alpha_attr)]:
        ridge_s = Ridge(alpha=alpha, fit_intercept=True)
        ridge_s.fit(X_scaled, y_vals)

        coef_orig = (1.0 / col_stds) * ridge_s.coef_
        intercept_orig = float(ridge_s.intercept_) - float(np.dot(coef_orig, col_means))

        predicted = X_no_const.values @ coef_orig + intercept_orig
        residuals = y_vals - predicted
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y_vals - y_vals.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        n, p = X_no_const.shape
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2

        # Holdout MSE on original-scale X and y via TimeSeriesSplit
        n_obs = len(y_vals)
        min_train = X_no_const.shape[1] + 1
        if n_obs >= min_train * (_RIDGE_N_SPLITS + 1):
            tscv = TimeSeriesSplit(n_splits=_RIDGE_N_SPLITS)
            fold_mses: list[float] = []
            for train_idx, test_idx in tscv.split(X_no_const):
                r_fold = Ridge(alpha=alpha, fit_intercept=True)
                r_fold.fit(X_no_const.values[train_idx], y_vals[train_idx])
                y_pred_fold = r_fold.predict(X_no_const.values[test_idx])
                fold_mses.append(float(np.mean((y_vals[test_idx] - y_pred_fold) ** 2)))
            holdout_mse = float(np.mean(fold_mses))
        else:
            holdout_mse = float("nan")

        row: dict = {
            "objective": label,
            "alpha": alpha,
            "r2": round(r2, 6),
            "adj_r2": round(adj_r2, 6),
            "holdout_mse": round(holdout_mse, 4) if np.isfinite(holdout_mse) else None,
        }
        col_names = list(X_no_const.columns)
        for i, col in enumerate(col_names):
            if col in spend_cols:
                row[col] = round(float(coef_orig[i]), 6)
        rows.append(row)

    # Interpreting compare_alpha_objectives output:
    # - r2 drop < 0.02      → attribution alpha is safe to use
    # - r2 drop 0.02–0.05   → meaningful trade-off, judgement call
    # - r2 drop > 0.05      → collinearity too severe for Ridge alone;
    #                          consider budget-share decomposition or
    #                          external calibration (geo experiments)
    # - any spend coef < 0  → red flag regardless of alpha

    return pd.DataFrame(rows)


# ── Step 5: VIF check ───────────────────────────────────────────────────────

def compute_vif(X: pd.DataFrame, spend_cols: list[str]) -> Dict[str, float]:
    # statsmodels VIF *requires* a constant to calculate centered R-squared.
    X_vif = X.copy()
    if "const" not in X_vif.columns:
        X_vif = sm.add_constant(X_vif)

    values = X_vif.values
    vifs = {}
    col_names = list(X_vif.columns)

    for i, col in enumerate(col_names):
        if col == "const":
            continue

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
        ridge_result = fit_ridge(result.X, result.y, spend_cols=spend_cols)
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


def _refit(X: pd.DataFrame, y: pd.Series, use_ridge: bool, spend_cols: list[str] | None = None) -> ModelResult:
    if use_ridge:
        return fit_ridge(X, y, spend_cols=spend_cols)
    return fit_ols(X, y, spend_cols=spend_cols)


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

    new_result = _refit(X, y, use_ridge, spend_cols=spend_cols)
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

    new_result2 = _refit(X2, y2, use_ridge, spend_cols=spend_cols)
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


# ── Step 7: Nonlinearity check (3-way race) ──────────────────────────────────

def _compute_dollar_r2(
    y_original: np.ndarray,
    predicted_log: np.ndarray,
    smearing: float,
) -> tuple[float, np.ndarray]:
    """Back-transform log-space predictions to dollars via Duan's smearing,
    then compute R² in dollar space for fair comparison with linear models."""
    preds_dollar = np.maximum(smearing * np.exp(predicted_log) - 1.0, 0.0)
    ss_res = float(np.sum((y_original - preds_dollar) ** 2))
    ss_tot = float(np.sum((y_original - y_original.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return r2, preds_dollar


def _inherit_flags(source: ModelResult, target: ModelResult) -> None:
    """Copy diagnostic flags from source result to target so downstream
    steps see the correct state after a refit."""
    target.ridge_applied = source.ridge_applied
    target.lags_added = source.lags_added
    target.vif_values = source.vif_values
    target.dw_stat = source.dw_stat
    target.ljung_box_p = source.ljung_box_p
    target.hac_applied = source.hac_applied


def check_nonlinearity(
    result: ModelResult,
    spend_cols: list[str],
    force_log_spend: bool | None = None,
    force_log_target: bool | None = None,
) -> ModelResult:
    """3-way race: Base vs Linear-Log vs Log-Log, compared in dollar space.

    If force_log_spend / force_log_target are set (functional form lock from
    backtest train fold), skip the race and fit the requested form directly.
    """
    present = [c for c in spend_cols if c in result.X.columns]
    if not present:
        result.dollar_r2 = result.r2
        result.dollar_adj_r2 = result.adj_r2
        return result

    use_ridge = result.ridge_applied
    y_original = result.y.values  # always in dollar space (no log target yet)

    # --- Force mode (functional form lock from backtest train fold) ---
    if force_log_spend is not None or force_log_target is not None:
        want_log_spend = bool(force_log_spend)
        want_log_target = bool(force_log_target)

        X_f = result.X.copy()
        y_f = result.y.copy()

        if want_log_spend:
            for col in present:
                X_f[col] = np.log1p(np.maximum(X_f[col], 0.0))
        if want_log_target:
            y_f = np.log1p(np.maximum(y_f, 0.0))

        forced = fit_ridge(X_f, y_f, spend_cols=spend_cols) if use_ridge else fit_ols(X_f, y_f, spend_cols=spend_cols)
        _inherit_flags(result, forced)
        forced.log_transform_applied = want_log_spend
        forced.log_target_applied = want_log_target

        if want_log_target:
            smearing = max(float(np.mean(np.exp(forced.y.values - forced.predicted))), 1e-6)
            dollar_r2, _ = _compute_dollar_r2(y_original, forced.predicted, smearing)
            n, p = forced.X.shape
            forced.dollar_r2 = dollar_r2
            forced.dollar_adj_r2 = 1.0 - (1.0 - dollar_r2) * (n - 1) / (n - p - 1) if n > p + 1 else dollar_r2
        else:
            forced.dollar_r2 = forced.r2
            forced.dollar_adj_r2 = forced.adj_r2

        return forced

    # --- 3-way race ---
    # Candidate 1: Base (current result, linear-linear)
    best = result
    best.dollar_r2 = result.r2
    best.dollar_adj_r2 = result.adj_r2
    best_label = "base"

    # Candidate 2: Linear-Log (log spend, linear target)
    X_log_spend = result.X.copy()
    for col in present:
        X_log_spend[col] = np.log1p(np.maximum(X_log_spend[col], 0.0))

    cand_ls = fit_ridge(X_log_spend, result.y, spend_cols=spend_cols) if use_ridge else fit_ols(X_log_spend, result.y, spend_cols=spend_cols)
    _inherit_flags(result, cand_ls)
    cand_ls.log_transform_applied = True
    cand_ls.dollar_r2 = cand_ls.r2
    cand_ls.dollar_adj_r2 = cand_ls.adj_r2

    if cand_ls.dollar_r2 > best.dollar_r2 + 0.01:
        best = cand_ls
        best_label = "linear-log"

    # Candidate 3: Log-Log (log spend, log target)
    y_log = np.log1p(np.maximum(result.y, 0.0))
    cand_ll = fit_ridge(X_log_spend, y_log, spend_cols=spend_cols) if use_ridge else fit_ols(X_log_spend, y_log, spend_cols=spend_cols)
    _inherit_flags(result, cand_ll)
    cand_ll.log_transform_applied = True
    cand_ll.log_target_applied = True

    # Evaluate log-log in dollar space via Duan's smearing
    residuals_ll = cand_ll.y.values - cand_ll.predicted
    smearing_ll = max(float(np.mean(np.exp(residuals_ll))), 1e-6)
    dollar_r2_ll, _ = _compute_dollar_r2(y_original, cand_ll.predicted, smearing_ll)
    n, p = cand_ll.X.shape
    cand_ll.dollar_r2 = dollar_r2_ll
    cand_ll.dollar_adj_r2 = 1.0 - (1.0 - dollar_r2_ll) * (n - 1) / (n - p - 1) if n > p + 1 else dollar_r2_ll

    if cand_ll.dollar_r2 > best.dollar_r2 + 0.01:
        best = cand_ll
        best_label = "log-log"

    logger.info(
        "Nonlinearity 3-way race: base=%.4f linear-log=%.4f log-log=%.4f (dollar R²) → winner=%s",
        result.r2, cand_ls.dollar_r2, cand_ll.dollar_r2, best_label,
    )

    return best


# ── Step 8: Heteroskedasticity check ────────────────────────────────────────

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


# ── Orchestrator: run full modeling pipeline ─────────────────────────────────

def run_model(
    X: pd.DataFrame, y: pd.Series, spend_cols: list[str]
) -> ModelResult:
    # Step 4: Base OLS
    result = fit_ols(X, y, spend_cols=spend_cols)

    # Step 5: VIF → maybe Ridge
    result = check_vif(result, spend_cols)

    # Step 6: Autocorrelation → maybe lags / HAC
    result = check_autocorrelation(result, spend_cols)

    # Step 7: Nonlinearity → maybe log(spend)
    result = check_nonlinearity(result, spend_cols)

    # Step 8: Heteroskedasticity → maybe HAC
    result = check_heteroskedasticity(result)

    # Step 9: Final model state is ready
    result.residual_std = float(np.std(result.residuals, ddof=1))

    # Flag negative spend coefficients
    neg = [c for c in spend_cols
           if c in result.coefficients.index and float(result.coefficients[c]) < 0]
    if neg:
        result.negative_spend_cols = neg
        logger.warning("Negative spend coefficients detected: %s", neg)

    return result
