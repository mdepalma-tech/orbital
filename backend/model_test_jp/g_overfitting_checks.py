import sklearn
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from scipy.optimize import minimize

"""
MMM Overfitting Diagnostic Plots
=================================
Run this after the main model to generate 4 overfitting diagnostic charts:

  1. Predicted vs Actual (train + holdout overlay)
  2. Residuals over time
  3. Residual distribution (histogram + normal curve)
  4. Learning curve — train vs holdout R² as training size grows

Usage:
    from mmm_plots import plot_overfitting_diagnostics
    plot_overfitting_diagnostics(mmm_results, holdout_metrics, df_train, df_test)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from scipy import stats
from typing import Dict
from typing import List

# ── colour palette ────────────────────────────────────────────────────────────
C_TRAIN   = "#4C72B0"
C_HOLDOUT = "#DD8452"
C_ZERO    = "#999999"
C_SHADE   = "#F0F4FF"


def _get_train_predictions(mmm_results: Dict, df_train: pd.DataFrame) -> np.ndarray:
    """Re-predict on training data in original sales units."""
    model    = mmm_results['model']
    scaler_X = mmm_results['scaler_X']
    scaler_y = mmm_results['scaler_y']
    all_cols = mmm_results['all_feature_cols']

    X_scaled  = scaler_X.transform(df_train[all_cols].values)
    y_pred    = scaler_y.inverse_transform(model.predict(X_scaled).reshape(-1, 1)).ravel()
    return y_pred


def plot_overfitting_diagnostics(
    mmm_results: Dict,
    holdout_metrics: Dict,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    save_path: str = "backend/model_test_jp/mmm_diagnostics.png",
) -> None:
    """
    Generate 4-panel overfitting diagnostic plot.

    Panels:
        1. Predicted vs Actual over time (train + holdout)
        2. Residuals over time
        3. Residual distribution vs normal curve
        4. Learning curve: train R² and holdout R² as training size grows

    Args:
        mmm_results     : Output of build_mmm_model().
        holdout_metrics : Output of evaluate_holdout().
        df_train        : Training DataFrame (must have all feature + date cols).
        df_test         : Holdout DataFrame (must have all feature + date cols).
        save_path       : Where to save the image.
    """
    response_col = mmm_results['response_col']

    # ── gather predictions ────────────────────────────────────────────────────
    y_train_actual = df_train[response_col].values
    y_train_pred   = _get_train_predictions(mmm_results, df_train)

    y_test_actual  = holdout_metrics['actuals']
    y_test_pred    = holdout_metrics['predictions']

    train_dates    = pd.to_datetime(df_train['date'])
    test_dates     = pd.to_datetime(df_test['date'])

    train_resid    = y_train_actual - y_train_pred
    test_resid     = y_test_actual  - y_test_pred

    train_r2       = mmm_results['r2_score']
    holdout_r2     = holdout_metrics['r2']
    holdout_mape   = holdout_metrics['mape']

    # ── layout ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 12), facecolor="white")
    fig.suptitle("MMM Overfitting Diagnostics", fontsize=16, fontweight='bold', y=0.98)
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)

    ax1 = fig.add_subplot(gs[0, :])   # full-width top
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])

    # ── PANEL 1 : Predicted vs Actual over time ───────────────────────────────
    ax1.set_facecolor(C_SHADE)
    ax1.axvspan(test_dates.iloc[0], test_dates.iloc[-1], alpha=0.12, color=C_HOLDOUT, label="_holdout region")

    ax1.plot(train_dates, y_train_actual, color=C_TRAIN,   lw=1.5, label="Actual (train)")
    ax1.plot(train_dates, y_train_pred,   color=C_TRAIN,   lw=1.5, ls="--", alpha=0.8, label="Predicted (train)")
    ax1.plot(test_dates,  y_test_actual,  color=C_HOLDOUT, lw=1.5, label="Actual (holdout)")
    ax1.plot(test_dates,  y_test_pred,    color=C_HOLDOUT, lw=1.5, ls="--", alpha=0.8, label="Predicted (holdout)")

    ax1.axvline(test_dates.iloc[0], color=C_ZERO, lw=1.2, ls=":", alpha=0.7)
    ax1.text(test_dates.iloc[0], ax1.get_ylim()[1] if ax1.get_ylim()[1] != 0 else 1,
             "  holdout →", fontsize=9, color=C_ZERO, va='top')

    ax1.set_title(
        f"Predicted vs Actual  |  Train R²={train_r2:.3f}  ·  Holdout R²={holdout_r2:.3f}  ·  Holdout MAPE={holdout_mape:.1%}",
        fontsize=11, pad=8
    )
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Sales")
    ax1.legend(fontsize=9, ncol=4, loc='upper left')
    ax1.grid(axis='y', alpha=0.3)
    ax1.tick_params(axis='x', rotation=30)

    # ── PANEL 2 : Residuals over time ─────────────────────────────────────────
    ax2.set_facecolor(C_SHADE)
    ax2.axhline(0, color=C_ZERO, lw=1, ls="--")
    ax2.scatter(train_dates, train_resid, color=C_TRAIN,   s=18, alpha=0.7, label="Train")
    ax2.scatter(test_dates,  test_resid,  color=C_HOLDOUT, s=18, alpha=0.9, label="Holdout")
    ax2.axvline(test_dates.iloc[0], color=C_ZERO, lw=1, ls=":", alpha=0.7)

    # flag if residuals have a trend (potential systematic bias)
    slope, _, r, p, _ = stats.linregress(np.arange(len(train_resid)), train_resid)
    if abs(r) > 0.3:
        ax2.set_title("Residuals over Time  ⚠ trend detected", fontsize=11, color="#CC4400")
    else:
        ax2.set_title("Residuals over Time  ✓ no clear trend", fontsize=11)

    ax2.set_xlabel("Date")
    ax2.set_ylabel("Actual − Predicted")
    ax2.legend(fontsize=9)
    ax2.grid(axis='y', alpha=0.3)
    ax2.tick_params(axis='x', rotation=30)

    # ── PANEL 3 : Residual distribution ───────────────────────────────────────
    ax3.set_facecolor(C_SHADE)
    all_resid = np.concatenate([train_resid, test_resid])

    ax3.hist(train_resid, bins=20, color=C_TRAIN,   alpha=0.6, density=True, label="Train")
    ax3.hist(test_resid,  bins=10, color=C_HOLDOUT, alpha=0.6, density=True, label="Holdout")

    # overlay normal curve fitted to training residuals
    mu, sigma = train_resid.mean(), train_resid.std()
    x_range   = np.linspace(all_resid.min(), all_resid.max(), 200)
    ax3.plot(x_range, stats.norm.pdf(x_range, mu, sigma),
             color=C_TRAIN, lw=2, label=f"Normal fit (train)\nμ={mu:.0f}, σ={sigma:.0f}")

    # Shapiro-Wilk normality test on training residuals
    _, p_sw = stats.shapiro(train_resid)
    normal_flag = "✓ approx. normal" if p_sw > 0.05 else "⚠ non-normal (p={:.3f})".format(p_sw)
    ax3.set_title(f"Residual Distribution  {normal_flag}", fontsize=11,
                  color="black" if p_sw > 0.05 else "#CC4400")

    ax3.set_xlabel("Residual")
    ax3.set_ylabel("Density")
    ax3.legend(fontsize=9)
    ax3.grid(axis='y', alpha=0.3)

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Diagnostics saved to: {save_path}")
    plt.close()


def plot_learning_curve(
    df_train_raw: pd.DataFrame,
    df_test_raw: pd.DataFrame,
    spend_cols: List,
    seasonality_cols: List,
    best_decay_params: Dict,
    response_col: str = 'sales',
    save_path: str = "backend/model_test_jp/mmm_learning_curve.png",
    n_steps: int = 15,
) -> None:
    """
    Learning curve: fit model on growing fractions of training data,
    plot train R² and holdout R² at each step.

    A healthy model shows train R² decreasing and holdout R² increasing
    as more data is added, converging toward each other.
    Persistent large gap → overfitting.
    Holdout R² not improving → model has hit its ceiling.

    Args:
        df_train_raw      : Full training set (pre-adstock).
        df_test_raw       : Holdout set (pre-adstock).
        spend_cols        : Raw spend column names.
        seasonality_cols  : Seasonality column names.
        best_decay_params : Tuned decay rates from tune_decay_rates().
        response_col      : Target column name.
        save_path         : Where to save the PNG.
        n_steps           : Number of training-size steps to evaluate.
    """
    # These imports are needed here since this file is standalone
    from model_test_jp.h_mmm_analysis import (
        apply_adstock, apply_saturation, build_mmm_model, evaluate_holdout
    )
    import sklearn.metrics

    adstocked_cols = [f"{col}_adstocked" for col in spend_cols]

    # Pre-transform test set once (fixed)
    df_test_ads              = apply_adstock(df_test_raw, spend_cols, best_decay_params)

    # Pre-transform full training set to get ref_maxes from full data
    df_train_full_ads        = apply_adstock(df_train_raw, spend_cols, best_decay_params)
    _, _, full_ref_maxes     = apply_saturation(df_train_full_ads, adstocked_cols)
    df_test_sat, test_sat_cols, _ = apply_saturation(
        df_test_ads, adstocked_cols, ref_maxes=full_ref_maxes
    )

    min_rows  = max(20, len(adstocked_cols) + len(seasonality_cols) + 5)
    fractions = np.linspace(min_rows / len(df_train_raw), 1.0, n_steps)

    train_r2s   = []
    holdout_r2s = []
    n_rows      = []

    for frac in fractions:
        n = int(frac * len(df_train_raw))
        df_sub     = df_train_raw.iloc[:n].copy()
        df_sub_ads = apply_adstock(df_sub, spend_cols, best_decay_params)
        df_sub_sat, sat_cols, ref_maxes = apply_saturation(df_sub_ads, adstocked_cols)

        # Re-saturate test with this subset's ref_maxes for fair comparison
        df_te_sat, _, _ = apply_saturation(df_test_ads, adstocked_cols, ref_maxes=ref_maxes)

        results = build_mmm_model(df_sub_sat, response_col, spend_cols, sat_cols, seasonality_cols)
        metrics = evaluate_holdout(results, df_te_sat, sat_cols, seasonality_cols, silent=True)

        train_r2s.append(results['r2_score'])
        holdout_r2s.append(metrics['r2'])
        n_rows.append(n)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='white')
    ax.set_facecolor(C_SHADE)

    ax.plot(n_rows, train_r2s,   color=C_TRAIN,   lw=2, marker='o', ms=5, label="Train R²")
    ax.plot(n_rows, holdout_r2s, color=C_HOLDOUT, lw=2, marker='o', ms=5, label="Holdout R²")
    ax.fill_between(n_rows, train_r2s, holdout_r2s,
                    alpha=0.12, color=C_ZERO, label="Gap (overfit risk)")

    ax.axvline(len(df_train_raw), color=C_ZERO, lw=1, ls=":", alpha=0.6, label="Full training set")
    ax.set_title("Learning Curve  —  Train vs Holdout R² as Training Size Grows",
                 fontsize=12, fontweight='bold')
    ax.set_xlabel("Training rows")
    ax.set_ylabel("R²")
    ax.set_ylim(-0.1, 1.05)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Learning curve saved to: {save_path}")
    plt.close()


