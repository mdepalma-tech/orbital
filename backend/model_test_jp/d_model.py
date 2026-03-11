import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error

def build_mmm_model(
    df: pd.DataFrame,
    response_col: str           = 'sales',
    spend_cols: List[str]       = None,
    saturated_cols: List[str]   = None,
    seasonality_cols: List[str] = None,
) -> Dict:
    """
    Fit the Marketing Mix Model on training data.

    Feature matrix = saturated adstocked spend + seasonality controls.
    Elasticities and contributions are computed on spend channels only;

    Args:
        df               : Training DataFrame (from time_based_split).
        response_col     : Target column name.
        spend_cols       : Original raw spend column names (for elasticity calc).
        saturated_cols   : Transformed spend features (adstocked then saturated).
        seasonality_cols : Seasonality/trend feature columns (appended after spend).

    Returns:
        Dictionary with fitted model, scalers, elasticities, contributions, diagnostics.
    """
    if spend_cols is None:
        spend_cols = ['google_spend', 'meta_spend', 'tiktok_spend']
    if saturated_cols is None:
        saturated_cols = []
    if seasonality_cols is None:
        seasonality_cols = []

    all_feature_cols = saturated_cols + seasonality_cols

    X = df[all_feature_cols].values
    y = df[response_col].values

    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

    model = LinearRegression()
    model.fit(X_scaled, y_scaled)

    y_mean = df[response_col].mean()

    # Elasticities in saturated feature space (use compute_raw_elasticities for raw spend space)
    elasticities = {}
    for i, col in enumerate(spend_cols):
        channel = col.replace('_spend', '')
        sat_col = saturated_cols[i]
        elasticities[channel] = (
            model.coef_[i] * scaler_X.scale_[i] / scaler_y.scale_[0]
        ) * (df[sat_col].mean() / y_mean)

    # Contributions — un-scaled coefficient × mean saturated feature, normalised to 100%
    contributions = {}
    for i, col in enumerate(spend_cols):
        channel       = col.replace('_spend', '')
        sat_col       = saturated_cols[i]
        coef_unscaled = model.coef_[i] * scaler_X.scale_[i] / scaler_y.scale_[0]
        contributions[channel] = coef_unscaled * df[sat_col].mean()

    total = sum(v for v in contributions.values() if v > 0)
    contributions = {k: (v / total if total != 0 else 0) for k, v in contributions.items()}

    return {
        'model'            : model,
        'scaler_X'         : scaler_X,
        'scaler_y'         : scaler_y,
        'coefficients'     : {spend_cols[i].replace('_spend', ''): model.coef_[i] for i in range(len(spend_cols))},
        'seasonality_coefs': {seasonality_cols[i]: model.coef_[len(saturated_cols) + i] for i in range(len(seasonality_cols))},
        'elasticities'     : elasticities,
        'contributions'    : contributions,
        'r2_score'         : model.score(X_scaled, y_scaled),
        'intercept'        : model.intercept_,
        'spend_cols'       : spend_cols,
        'saturated_cols'   : saturated_cols,
        'seasonality_cols' : seasonality_cols,
        'all_feature_cols' : all_feature_cols,
        'response_col'     : response_col,
        'means'            : {'spend': df[spend_cols].mean(), 'response': y_mean},
    }
