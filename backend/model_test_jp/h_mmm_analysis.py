import sklearn
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from scipy.optimize import minimize
from typing import Dict, List, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from scipy.optimize import minimize

from model_test_jp.a_data_prep import _load_local_series, _clean_data, _merge_data
from model_test_jp.b_feature_engineering import add_seasonality_features, apply_adstock, apply_saturation, hill_saturation  
from model_test_jp.c_train_test_split import time_based_split
from model_test_jp.d_model import build_mmm_model
from model_test_jp.f_metrics import evaluate_holdout
from model_test_jp.g_overfitting_checks import plot_overfitting_diagnostics, plot_learning_curve

# ============================================================================
# ELASTICITY IN RAW SPEND SPACE (NUMERICAL PERTURBATION)
# ============================================================================

def compute_raw_elasticities(
    mmm_results: Dict,
    df_train_adstocked: pd.DataFrame,
    spend_cols: List[str],
    sat_ref_maxes: Dict[str, float],
    alpha_params: Dict[str, float] = None,
    gamma_params: Dict[str, float] = None,
    perturbation: float = 0.01,
) -> Dict:
    """
    Compute elasticity in adstocked spend space via numerical perturbation.

    For each channel: increase its adstocked spend by 1%, apply saturation
    with FIXED training ref_maxes, predict sales, measure % change vs baseline.

    Perturbation is applied to adstocked columns (not raw spend) because the
    model was trained on adstocked features. Perturbing raw spend and re-running
    adstock would spread the signal across lags, understating the effect.

    Args:
        mmm_results        : Output of build_mmm_model().
        df_train_adstocked : Training DataFrame AFTER apply_adstock() has been called.
        spend_cols         : Raw spend column names (used to derive adstocked col names).
        sat_ref_maxes      : Training adstock maxes from apply_saturation() — REQUIRED
                             so Hill normalisation is consistent across perturbations.
        perturbation       : Fractional increase to simulate (default 0.01 = 1%).

    Returns:
        Dict of channel → elasticity (% change in sales per 1% change in adstocked spend).
    """
    model            = mmm_results['model']
    scaler_X         = mmm_results['scaler_X']
    scaler_y         = mmm_results['scaler_y']
    adstocked_cols   = [f"{col}_adstocked" for col in spend_cols]
    seasonality_cols = mmm_results['seasonality_cols']

    def _predict_mean(df: pd.DataFrame) -> float:
        df_sat, _, __ = apply_saturation(
            df, adstocked_cols, alpha_params, gamma_params, ref_maxes=sat_ref_maxes
        )
        all_cols = mmm_results['saturated_cols'] + seasonality_cols
        X        = scaler_X.transform(df_sat[all_cols].values)
        y_pred   = scaler_y.inverse_transform(model.predict(X).reshape(-1, 1)).ravel()
        return y_pred.mean()

    baseline = _predict_mean(df_train_adstocked)

    elasticities = {}
    for col in spend_cols:
        channel       = col.replace('_spend', '')
        adstocked_col = f"{col}_adstocked"

        df_perturbed = df_train_adstocked.copy()
        df_perturbed[adstocked_col] = df_perturbed[adstocked_col] * (1 + perturbation)

        perturbed = _predict_mean(df_perturbed)
        elasticities[channel] = (perturbed - baseline) / baseline / perturbation

    return elasticities