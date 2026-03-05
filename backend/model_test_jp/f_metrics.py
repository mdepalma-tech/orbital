import pandas as pd
import numpy as np
import os
import sklearn
from typing import Dict, List, Tuple
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error

def evaluate_holdout(
    mmm_results: Dict,
    df_test: pd.DataFrame,
    saturated_cols: List[str],
    seasonality_cols: List[str],
    silent: bool = False,
) -> Dict:
    """
    Evaluate a fitted MMM on the holdout set and report MAPE, RMSE, and R².

    Args:
        mmm_results      : Output dict from build_mmm_model().
        df_test          : Holdout DataFrame (must have saturated + seasonality cols).
        saturated_cols   : Spend feature columns used during training.
        seasonality_cols : Seasonality feature columns used during training.
        silent           : If True, suppress printed output (used during optimisation).

    Returns:
        Dictionary with mape, rmse, r2, actuals, and predictions arrays.
    """
    model    = mmm_results['model']
    scaler_X = mmm_results['scaler_X']
    scaler_y = mmm_results['scaler_y']
    all_cols = saturated_cols + seasonality_cols

    X_test        = df_test[all_cols].values
    y_test_actual = df_test[mmm_results['response_col']].values

    X_test_scaled = scaler_X.transform(X_test)
    y_pred_scaled = model.predict(X_test_scaled)
    y_pred_actual = scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()

    mape       = mean_absolute_percentage_error(y_test_actual, y_pred_actual)
    rmse       = np.sqrt(mean_squared_error(y_test_actual, y_pred_actual))
    r2_holdout = sklearn.metrics.r2_score(y_test_actual, y_pred_actual)

    if not silent:
        print(f"\n📊 Holdout MAPE : {mape:.2%}   (lower is better; <15% is good for MMM)")
        print(f"📊 Holdout RMSE : {rmse:,.0f}")
        print(f"📊 Holdout R²   : {r2_holdout:.4f}  ({r2_holdout*100:.1f}% of holdout variance explained)")

    return {
        'mape'       : mape,
        'rmse'       : rmse,
        'r2'         : r2_holdout,
        'actuals'    : y_test_actual,
        'predictions': y_pred_actual,
    }