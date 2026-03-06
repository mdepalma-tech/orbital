"""Per-channel adstock alpha selection via grid search."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.matrix import build_design_matrix, geometric_adstock
from pipeline.modeling import fit_ols


def select_adstock_alphas(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: str,
    diagnostics: dict,
    alpha_grid: list[float] | None = None,
) -> dict[str, float]:
    """
    For each spend channel, grid-search over alpha_grid to find the adstock
    decay rate that maximises out-of-sample R² on a time-based 80/20 split.

    Each channel is evaluated independently — all other channels are held at
    alpha=0.0 during that channel's sweep. This keeps the search O(C * G)
    rather than O(G^C).

    Returns a dict mapping each spend column to its selected alpha, e.g.
        {"meta_spend": 0.6, "google_spend": 0.1, "tiktok_spend": 0.3}
    """
    if alpha_grid is None:
        alpha_grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    # Time-based 80/20 split
    split_idx = int(len(df_weekly) * 0.8)
    df_train = df_weekly.iloc[:split_idx]
    df_test = df_weekly.iloc[split_idx:]

    if len(df_test) < 2:
        # Not enough test data — fall back to no adstock
        return {col: 0.0 for col in spend_cols}

    selected: dict[str, float] = {}

    for target_col in spend_cols:
        best_alpha = 0.0
        best_r2 = -np.inf

        for alpha in alpha_grid:
            # Build channel_alphas: only the target channel gets the candidate alpha
            channel_alphas = {col: 0.0 for col in spend_cols}
            channel_alphas[target_col] = alpha

            # Build train matrix
            X_train, y_train, feature_state = build_design_matrix(
                df_train,
                spend_cols,
                model_mode=model_mode,
                diagnostics=diagnostics,
                channel_alphas=channel_alphas,
            )

            # Fit OLS on train
            result = fit_ols(X_train, y_train)

            # Build test matrix with feature_state for consistency
            X_test, y_test, _ = build_design_matrix(
                df_test,
                spend_cols,
                model_mode=model_mode,
                diagnostics=diagnostics,
                feature_state=feature_state,
                channel_alphas=channel_alphas,
            )

            # Predict on test
            y_pred = result.model.predict(X_test)
            y_actual = y_test.values

            # Compute OOS R²
            ss_res = float(np.sum((y_actual - y_pred) ** 2))
            ss_tot = float(np.sum((y_actual - np.mean(y_actual)) ** 2))
            r2_oos = (1.0 - ss_res / ss_tot) if ss_tot > 0 else -np.inf

            if r2_oos > best_r2:
                best_r2 = r2_oos
                best_alpha = alpha

        selected[target_col] = best_alpha

    return selected
