import pandas as pd
import numpy as np
import os
from typing import Dict, List
from scipy.optimize import minimize
from model_test_jp.a_data_prep import _load_local_series, _clean_data, _merge_data
from model_test_jp.b_feature_engineering import add_seasonality_features, apply_adstock, apply_saturation, hill_saturation  
from model_test_jp.c_train_test_split import time_based_split
from model_test_jp.d_model import build_mmm_model
from model_test_jp.f_metrics import evaluate_holdout
from model_test_jp.g_overfitting_checks import plot_overfitting_diagnostics, plot_learning_curve
from model_test_jp.h_mmm_analysis import compute_raw_elasticities

# ============================================================================
# DECAY RATE TUNING
# ============================================================================

def tune_decay_rates(
    df_train_raw: pd.DataFrame,
    df_test_raw: pd.DataFrame,
    spend_cols: List[str],
    seasonality_cols: List[str],
    response_col: str = 'sales',
    n_restarts: int = 5,
) -> Dict:
    """
    Find the per-channel adstock decay rates that minimise holdout MAPE.

    A default decay of 0.5 for all channels is arbitrary, while Meta might have a
    short memory (decay=0.1), TikTok a longer one (decay=0.7). Wrong decay rates
    mean the adstocked feature doesn't reflect true exposure, directly hurting
    both train and holdout R².

    Args:
        df_train_raw     : Training DataFrame with RAW (pre-adstock) spend columns.
        df_test_raw      : Holdout DataFrame with RAW (pre-adstock) spend columns.
        spend_cols       : Raw spend column names.
        seasonality_cols : Seasonality feature columns (already added to both dfs).
        response_col     : Target column name.
        n_restarts       : Number of random restarts for the optimiser.

    Returns:
        Dictionary with best_decay_params, best_mape, and full optimisation history.
    """
    adstocked_cols = [f"{col}_adstocked" for col in spend_cols]
    channel_names  = [col.replace('_spend', '') for col in spend_cols]

    def objective(params: np.ndarray) -> float:
        decay_params = dict(zip(channel_names, params))

        df_tr = apply_adstock(df_train_raw, spend_cols, decay_params)
        df_te = apply_adstock(df_test_raw,  spend_cols, decay_params)

        df_tr, saturated_cols, ref_maxes = apply_saturation(df_tr, adstocked_cols)
        df_te, _,              _         = apply_saturation(df_te, adstocked_cols, ref_maxes=ref_maxes)

        results = build_mmm_model(df_tr, response_col, spend_cols, saturated_cols, seasonality_cols)
        metrics = evaluate_holdout(results, df_te, saturated_cols, seasonality_cols, silent=True)

        return metrics['mape']

    best_mape   = np.inf
    best_params = None
    history     = []

    rng = np.random.default_rng(seed=42)

    for i in range(n_restarts):
        # Random starting point, with first restart anchored at default 0.5
        x0 = np.array([0.5] * len(spend_cols)) if i == 0 else rng.uniform(0.05, 0.95, len(spend_cols))

        result = minimize(
            objective,
            x0      = x0,
            bounds  = [(0.05, 0.95)] * len(spend_cols),
            method  = 'L-BFGS-B',
            options = {'ftol': 1e-9, 'maxiter': 500},
        )

        history.append({'params': result.x, 'mape': result.fun, 'converged': result.success})

        if result.fun < best_mape:
            best_mape   = result.fun
            best_params = result.x

        print(f"  Restart {i+1}/{n_restarts} | MAPE: {result.fun:.4f} | "
              + " | ".join(f"{ch}: {v:.3f}" for ch, v in zip(channel_names, result.x)))

    best_decay_params = dict(zip(channel_names, best_params))

    print(f"\n✅ Best decay rates found (MAPE: {best_mape:.2%}):")
    for ch, v in best_decay_params.items():
        print(f"   {ch:15} : {v:.4f}")

    return {
        'best_decay_params': best_decay_params,
        'best_mape'        : best_mape,
        'history'          : history,
    }
