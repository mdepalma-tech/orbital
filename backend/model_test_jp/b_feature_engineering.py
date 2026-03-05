import numpy as np
import pandas as pd
from typing import List, Dict, Tuple

# ============================================================================
# SEASONALITY
# ============================================================================

def add_seasonality_features(df: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
    """
    Add trend + Fourier terms to capture seasonality.

    Returns:
        df               : DataFrame with new seasonality columns added.
        seasonality_cols : Column names to pass into build_mmm_model().

    Note:
        Month dummies excluded — too many parameters for 160 training rows.
        2 Fourier harmonics + trend = 5 seasonality features total.
    """
    df = df.copy()
    seasonality_cols = []

    df['t'] = np.arange(len(df))
    seasonality_cols.append('t')

    for k in [1, 2]:
        df[f'sin_{k}'] = np.sin(2 * np.pi * k * df['t'] / 52)
        df[f'cos_{k}'] = np.cos(2 * np.pi * k * df['t'] / 52)
        seasonality_cols.extend([f'sin_{k}', f'cos_{k}'])

    return df, seasonality_cols


# ============================================================================
# ADSTOCK
# ============================================================================

def geometric_adstock(x: np.ndarray, decay_rate: float = 0.5, max_lag: int = 13) -> np.ndarray:
    """
    Geometric adstock: models the carry-over effect of advertising spend.

    Each past week's spend contributes decay_rate^lag to the current week's
    effective exposure. E.g. decay_rate=0.5 means last week contributes 50%,
    two weeks ago 25%, three weeks ago 12.5%, etc.

    Args:
        x          : Raw spend array (weekly).
        decay_rate : How fast the effect fades. 0 = no carry-over, 1 = never fades.
        max_lag    : Number of past weeks to consider.

    Returns:
        Array of adstocked spend values (same length as x).
    """
    adstock = np.zeros_like(x, dtype=float)
    for lag in range(max_lag):
        weight = decay_rate ** lag
        if lag == 0:
            adstock += x * weight
        else:
            adstock[lag:] += x[:-lag] * weight
    return adstock


def apply_adstock(
    df: pd.DataFrame,
    spend_cols: List[str],
    decay_params: Dict[str, float] = None,
) -> pd.DataFrame:
    """
    Apply geometric adstock to each spend column.

    Args:
        df           : DataFrame with raw spend columns.
        spend_cols   : Column names to transform.
        decay_params : Per-channel decay rates, e.g. {'google': 0.4, 'meta': 0.6}.
                       Defaults to 0.5 for every channel if not provided.

    Returns:
        DataFrame with additional '<col>_adstocked' columns.
    """
    df_out = df.copy()

    if decay_params is None:
        decay_params = {col.replace('_spend', ''): 0.5 for col in spend_cols}

    for col in spend_cols:
        if col in df.columns:
            decay_rate = decay_params.get(col.replace('_spend', ''), 0.5)
            df_out[f"{col}_adstocked"] = geometric_adstock(df[col].values, decay_rate=decay_rate)

    return df_out


# ============================================================================
# SATURATION (HILL TRANSFORMATION)
# ============================================================================

def hill_saturation(
    x: np.ndarray,
    alpha: float = 2.0,
    gamma: float = 0.5,
    x_ref: float = None,
) -> np.ndarray:
    """
    Hill function: models diminishing returns on advertising spend.

    Applied AFTER adstock: raw spend → adstock (lag effect) → saturation (diminishing returns).

    Args:
        x     : Adstocked spend array.
        alpha : Steepness of the S-curve. Higher = sharper inflection point.
        gamma : Half-saturation point as a fraction of the normalised spend range.
        x_ref : Fixed reference maximum for normalisation. Must be the TRAINING max
                when transforming holdout or perturbed data — otherwise each array
                normalises by its own max and perturbations cancel out entirely.
                Defaults to x.max() (correct only for the initial training fit).

    Returns:
        Saturated response array normalised to [0, 1].
    """
    x_max = x_ref if x_ref is not None else x.max()
    if x_max == 0:
        return np.zeros_like(x, dtype=float)

    x_norm = x / x_max
    return x_norm ** alpha / (x_norm ** alpha + gamma ** alpha)


def apply_saturation(
    df: pd.DataFrame,
    adstocked_cols: List[str],
    alpha_params: Dict[str, float] = None,
    gamma_params: Dict[str, float] = None,
    ref_maxes: Dict[str, float] = None,
) -> tuple[pd.DataFrame, List[str], Dict[str, float]]:
    """
    Apply Hill saturation to adstocked spend columns.

    Must be called AFTER apply_adstock(). Pipeline:
        raw spend → adstock → saturation → regression features

    On the TRAINING set, call without ref_maxes — it computes and returns them.
    On holdout / perturbed data, pass the training ref_maxes to ensure consistent
    normalisation (otherwise perturbations cancel out and elasticities are zero).

    Args:
        df             : DataFrame containing adstocked spend columns.
        adstocked_cols : Columns to saturate (produced by apply_adstock).
        alpha_params   : Per-channel alpha values. Defaults to 2.0.
        gamma_params   : Per-channel gamma values. Defaults to 0.5.
        ref_maxes      : Fixed normalisation maxes per column. Pass training maxes
                         for holdout / perturbed data. Computed from data if None.

    Returns:
        df_out         : DataFrame with new '<col>_saturated' columns added.
        saturated_cols : Column names to use as model features.
        ref_maxes_out  : Per-column maxes used — store and reuse for holdout/perturbation.
    """
    df_out        = df.copy()
    saturated_cols = []
    ref_maxes_out  = {}

    alpha_params = alpha_params or {}
    gamma_params = gamma_params or {}
    ref_maxes    = ref_maxes    or {}

    for col in adstocked_cols:
        channel    = col.replace('_spend_adstocked', '').replace('_adstocked', '')
        alpha      = alpha_params.get(channel, 2.0)
        gamma      = gamma_params.get(channel, 0.5)
        x_ref      = ref_maxes.get(col, None)
        sat_col    = f"{col}_saturated"
        values     = df[col].values
        x_ref_used = x_ref if x_ref is not None else values.max()

        ref_maxes_out[col]  = x_ref_used
        df_out[sat_col]     = hill_saturation(values, alpha=alpha, gamma=gamma, x_ref=x_ref_used)
        saturated_cols.append(sat_col)

    return df_out, saturated_cols, ref_maxes_out