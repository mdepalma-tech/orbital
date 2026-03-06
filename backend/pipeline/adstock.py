"""Per-channel adstock alpha selection via time-series cross-validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from pipeline.matrix import build_design_matrix
from pipeline.modeling import fit_ols


def select_adstock_alphas(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: str,
    diagnostics: dict,
    alpha_grid: list[float] | None = None,
    n_splits: int = 3,
) -> dict[str, float]:
    """
    For each spend channel, grid-search over alpha_grid to find the adstock
    decay rate that maximises cross-validated R² using TimeSeriesSplit.

    Uses time-based cross-validation with n_splits folds. Each fold trains on
    earlier data and tests on later data, respecting the temporal order.

    Each channel is evaluated independently — all other channels are held at
    alpha=0.0 during that channel's sweep. This keeps the search O(C * G)
    rather than O(G^C).

    Returns a dict mapping each spend column to its selected alpha, e.g.
        {"meta_spend": 0.6, "google_spend": 0.1, "tiktok_spend": 0.3}
    """
    if alpha_grid is None:
        alpha_grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    if len(df_weekly) < 2 * n_splits:
        # Not enough data for n_splits — fall back to no adstock
        return {col: 0.0 for col in spend_cols}

    tscv = TimeSeriesSplit(n_splits=n_splits)
    selected: dict[str, float] = {}

    for target_col in spend_cols:
        best_alpha = 0.0
        best_cv_r2 = -np.inf

        for alpha in alpha_grid:
            # Build channel_alphas: only the target channel gets the candidate alpha
            channel_alphas = {col: 0.0 for col in spend_cols}
            channel_alphas[target_col] = alpha

            # Collect R² scores across all CV folds
            fold_r2_scores = []

            for train_idx, test_idx in tscv.split(df_weekly):
                df_train_fold = df_weekly.iloc[train_idx]
                df_test_fold = df_weekly.iloc[test_idx]

                # Build train matrix
                X_train, y_train, feature_state = build_design_matrix(
                    df_train_fold,
                    spend_cols,
                    model_mode=model_mode,
                    diagnostics=diagnostics,
                    channel_alphas=channel_alphas,
                )

                # Fit OLS on train fold
                result = fit_ols(X_train, y_train)

                # Build test matrix with feature_state for consistency
                X_test, y_test, _ = build_design_matrix(
                    df_test_fold,
                    spend_cols,
                    model_mode=model_mode,
                    diagnostics=diagnostics,
                    feature_state=feature_state,
                    channel_alphas=channel_alphas,
                )

                # Predict on test fold
                y_pred = result.model.predict(X_test)
                y_actual = y_test.values

                # Compute R² for this fold
                ss_res = float(np.sum((y_actual - y_pred) ** 2))
                ss_tot = float(np.sum((y_actual - np.mean(y_actual)) ** 2))
                r2_fold = (1.0 - ss_res / ss_tot) if ss_tot > 0 else -np.inf
                fold_r2_scores.append(r2_fold)

            # Average R² across all folds
            cv_r2 = float(np.mean(fold_r2_scores))

            if cv_r2 > best_cv_r2:
                best_cv_r2 = cv_r2
                best_alpha = alpha

        selected[target_col] = best_alpha

    return selected
