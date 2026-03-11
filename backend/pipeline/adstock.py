"""Per-channel adstock alpha selection via time-series cross-validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from pipeline.matrix import build_design_matrix
from pipeline.modeling import fit_ols


def _sweep_channel(
    target_col: str,
    spend_cols: list[str],
    base_alphas: dict[str, float],
    alpha_grid: list[float],
    df_weekly: pd.DataFrame,
    tscv: TimeSeriesSplit,
    model_mode: str,
    diagnostics: dict,
) -> float:
    """Grid-search one channel's adstock alpha, conditioning on base_alphas for all others."""
    best_alpha = 0.0
    best_cv_r2 = -np.inf

    for alpha in alpha_grid:
        channel_alphas = dict(base_alphas)
        channel_alphas[target_col] = alpha

        fold_r2_scores = []

        for train_idx, test_idx in tscv.split(df_weekly):
            df_train_fold = df_weekly.iloc[train_idx]
            df_test_fold = df_weekly.iloc[test_idx]

            X_train, y_train, feature_state = build_design_matrix(
                df_train_fold,
                spend_cols,
                model_mode=model_mode,
                diagnostics=diagnostics,
                channel_alphas=channel_alphas,
            )

            result = fit_ols(X_train, y_train)

            X_test, y_test, _ = build_design_matrix(
                df_test_fold,
                spend_cols,
                model_mode=model_mode,
                diagnostics=diagnostics,
                feature_state=feature_state,
                channel_alphas=channel_alphas,
            )

            fit_cols = result.X.columns
            X_test_aligned = X_test.reindex(columns=fit_cols, fill_value=0.0)

            y_pred = result.model.predict(X_test_aligned)
            y_actual = y_test.values

            ss_res = float(np.sum((y_actual - y_pred) ** 2))
            ss_tot = float(np.sum((y_actual - np.mean(y_actual)) ** 2))
            r2_fold = (1.0 - ss_res / ss_tot) if ss_tot > 0 else -np.inf
            fold_r2_scores.append(r2_fold)

        cv_r2 = float(np.mean(fold_r2_scores))

        if cv_r2 > best_cv_r2:
            best_cv_r2 = cv_r2
            best_alpha = alpha

    return best_alpha


def _run_sweep_round(
    spend_cols: list[str],
    base_alphas: dict[str, float],
    alpha_grid: list[float],
    df_weekly: pd.DataFrame,
    tscv: TimeSeriesSplit,
    model_mode: str,
    diagnostics: dict,
) -> dict[str, float]:
    """Sequential sweep: each channel is conditioned on prior channels' results from this round."""
    selected: dict[str, float] = {}
    current_alphas = dict(base_alphas)

    for col in spend_cols:
        best = _sweep_channel(
            col, spend_cols, current_alphas,
            alpha_grid, df_weekly, tscv, model_mode, diagnostics,
        )
        selected[col] = best
        current_alphas[col] = best

    return selected


def select_adstock_alphas(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: str,
    diagnostics: dict,
    alpha_grid: list[float] | None = None,
    n_splits: int = 3,
    max_rounds: int = 2,
) -> dict[str, float]:
    """
    For each spend channel, grid-search over alpha_grid to find the adstock
    decay rate that maximises cross-validated R² using TimeSeriesSplit.

    Uses coordinated sequential search: when evaluating channel N, all
    previously-selected channels use their current best alphas rather than
    zero. A second refinement pass re-sweeps each channel conditioned on
    all others' Round 1 results. If alphas converge (no changes), the
    second pass is skipped.

    Complexity: O(rounds * C * G * K) where C=channels, G=grid, K=folds.

    Returns a dict mapping each spend column to its selected alpha, e.g.
        {"meta_spend": 0.6, "google_spend": 0.1, "tiktok_spend": 0.3}
    """
    if alpha_grid is None:
        alpha_grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    if len(df_weekly) < 2 * n_splits:
        return {col: 0.0 for col in spend_cols}

    tscv = TimeSeriesSplit(n_splits=n_splits)

    # Round 1: sequential conditioning starting from zero
    selected = _run_sweep_round(
        spend_cols, {col: 0.0 for col in spend_cols},
        alpha_grid, df_weekly, tscv, model_mode, diagnostics,
    )

    # Rounds 2..N: refine conditioned on previous round's results
    for _ in range(1, max_rounds):
        refined = _run_sweep_round(
            spend_cols, selected,
            alpha_grid, df_weekly, tscv, model_mode, diagnostics,
        )
        if refined == selected:
            break
        selected = refined

    return selected
